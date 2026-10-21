"""Speech-to-Text tool — transcribe audio/video files via Whisper (local, free).

Engine: faster-whisper (CTranslate2 — lightweight, ~4x faster than openai-whisper,
no ffmpeg binary required — PyAV decodes audio/video).

Long-content handling (bắt buộc với audio dài):
  1. Transcribe full file (faster-whisper handles chunking internally)
  2. Nếu transcript dài hơn `max_chars`:
     → chunk transcript thành ~N char blocks
     → summarize từng block bằng LLM (multi-provider: get_llm_client)
     → ghép thành transcript tóm tắt có structure

YouTube flow: dùng `youtube_transcript` trước (free, không cần key) — chỉ dùng
STT khi video không có caption hoặc cần transcribe file audio/video local.
"""

import os
import tempfile
from typing import Dict, Any, List, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)

_SUPPORTED_AUDIO = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma")
_SUPPORTED_VIDEO = (".mp4", ".mkv", ".webm", ".avi", ".mov")

_SUMMARY_PROMPT = """You are a transcription summarizer. Summarize the following audio transcript chunk.
Keep: key points, decisions, numbers, names, action items, technical details.
Drop: filler words, repetitions, small talk.
Output: concise bullet points in the SAME LANGUAGE as the transcript.

Transcript chunk:
{chunk}
"""

_FULL_SUMMARY_PROMPT = """You are a transcription summarizer. Below are per-chunk summaries
of a long audio/video transcript. Merge them into ONE coherent structured summary
with sections: "Overview", "Key Points", "Action Items" (if any).
Use the SAME LANGUAGE as the content.

Chunk summaries:
{summaries}
"""


def _download_to_tempfile(url: str) -> str:
    import requests
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    suffix = os.path.splitext(url.split("?")[0])[1].lower() or ".mp3"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    return path


def _split_into_chunks(text: str, chunk_size: int = 6000) -> List[str]:
    """Split transcript vào các block ~chunk_size chars (không cắt giữa câu)."""
    chunks = []
    while len(text) > chunk_size:
        cut = text.rfind(". ", 0, chunk_size)
        cut = cut if cut > chunk_size // 2 else chunk_size
        chunks.append(text[: cut + 1].strip())
        text = text[cut + 1 :].strip()
    if text.strip():
        chunks.append(text.strip())
    return chunks


def _ensure_av_compat() -> None:
    """PyAV mới (>=15, builtin) đã xóa kwarg `metadata_errors` của av.open().

    faster-whisper (<=1.2.x) vẫn truyền kwarg này khi decode audio → TypeError
    trên PyAV mới. Wrap av.open: thử gọi như thường, nếu TypeError do
    `metadata_errors` thì bỏ kwarg và retry — an toàn cho mọi version PyAV
    (version cũ hỗ trợ kwarg vẫn gọi thành công ngay lần đầu).
    """
    try:
        import av
    except ImportError:
        return

    if getattr(av.open, "_drf_av_compat", False):
        return  # đã patch rồi

    _orig_open = av.open

    def _patched_open(*args, **kwargs):
        try:
            return _orig_open(*args, **kwargs)
        except TypeError as e:
            if "metadata_errors" in str(e):
                kwargs.pop("metadata_errors", None)
                return _orig_open(*args, **kwargs)
            raise

    _patched_open._drf_av_compat = True
    av.open = _patched_open
    logger.info("av_open_patched_for_faster_whisper_compat")


class SpeechToTextTool(BaseTool):
    """Transcribe audio/video files to text (Whisper local) with long-content LLM summarization."""

    def get_name(self) -> str:
        return "speech_to_text"

    def get_description(self) -> str:
        return (
            "Transcribe an audio or video file to text using local Whisper "
            "(faster-whisper, free, no API key). Supports mp3/wav/m4a/mp4/mkv... "
            "from local path or URL. If the transcript is very long, it is "
            "automatically chunked and summarized via LLM (keeps key points, "
            "drops filler). Use for meeting recordings, podcasts, lectures, "
            "videos without captions. "
            "Returns: {transcript, language, duration_sec, summarized: bool, summary?}."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local file path or URL of audio/video file",
                },
                "language": {
                    "type": "string",
                    "description": "ISO language hint (e.g. 'vi', 'en') — auto-detected if empty",
                },
                "summarize_if_long": {
                    "type": "boolean",
                    "description": "Summarize via LLM when transcript exceeds max_chars (default: true)",
                    "default": True,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max transcript chars before summarizing (default: 12000)",
                    "default": 12000,
                },
            },
            "required": ["file_path"],
        }

    def execute(
        self,
        file_path: str,
        language: Optional[str] = None,
        summarize_if_long: bool = True,
        max_chars: int = 12000,
        **kwargs,
    ) -> ToolResult:
        tmp_path = None
        try:
            # ── Resolve input (local path | URL) ─────────────────────────
            src = file_path.strip()
            if src.startswith(("http://", "https://")):
                tmp_path = _download_to_tempfile(src)
                src = tmp_path
            elif not os.path.isfile(src):
                return ToolResult(success=False, error=f"File not found: {file_path}")

            ext = os.path.splitext(src)[1].lower()
            if ext not in _SUPPORTED_AUDIO + _SUPPORTED_VIDEO:
                return ToolResult(
                    success=False,
                    error=f"Unsupported format '{ext}'. Supported: {', '.join(_SUPPORTED_AUDIO + _SUPPORTED_VIDEO)}",
                )

            # ── Transcribe with faster-whisper ───────────────────────────
            _ensure_av_compat()  # PyAV >=15 dropped metadata_errors kwarg
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                return ToolResult(
                    success=False,
                    error="faster-whisper not installed. Run: pip install faster-whisper",
                )

            model_name = config.WHISPER_MODEL or "base"
            logger.info("stt_transcribing", file=os.path.basename(src), model=model_name)

            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            segments, info = model.transcribe(
                src,
                language=language or None,
                vad_filter=True,          # skip silence → faster + cleaner
                vad_parameters={"min_silence_duration_ms": 500},
            )

            parts = []
            timestamps = []
            for seg in segments:
                text = seg.text.strip()
                if text:
                    parts.append(text)
                    timestamps.append({"start": round(seg.start, 1), "text": text})

            transcript = " ".join(parts)
            if not transcript:
                return ToolResult(success=False, error="No speech detected in the file")

            result: Dict[str, Any] = {
                "file": file_path,
                "transcript": transcript,
                "language": info.language if hasattr(info, "language") else (language or "unknown"),
                "duration_sec": round(getattr(info, "duration", 0) or 0, 1),
                "segment_count": len(timestamps),
                "segments": timestamps[:80],
                "summarized": False,
            }

            # ── Long transcript → chunked LLM summarization ──────────────
            if summarize_if_long and len(transcript) > max_chars:
                logger.info("stt_long_transcript_summarizing", length=len(transcript), max=max_chars)
                summary = self._summarize_long(transcript)
                if summary:
                    result["summary"] = summary
                    result["transcript"] = transcript[:max_chars] + "...[truncated — full content moved to summary]"
                    result["summarized"] = True

            return ToolResult(
                success=True,
                result=result,
                metadata={"model": model_name, "duration_sec": result["duration_sec"]},
            )

        except Exception as e:
            logger.error("stt_failed", file=file_path, error=str(e))
            return ToolResult(success=False, error=str(e))
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _summarize_long(self, transcript: str) -> Optional[str]:
        """Chunked summarization via LLM (multi-provider, fallback Gemini)."""
        try:
            from src.llm.llm_manager import get_llm_client

            llm = get_llm_client()  # LLM_PROVIDER env, fail → gemini fallback
            chunks = _split_into_chunks(transcript)

            # Pass 1: summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                out = llm.chat(
                    messages=[
                        {"role": "system", "content": _SUMMARY_PROMPT.format(chunk=chunk)},
                        {"role": "user", "content": f"Summarize chunk {i + 1}/{len(chunks)}."},
                    ],
                    temperature=0.2,
                )
                if out and out.strip():
                    chunk_summaries.append(f"[{i + 1}] {out.strip()}")

            if not chunk_summaries:
                return None

            # Pass 2: merge chunk summaries (chỉ khi > 1 chunk)
            if len(chunk_summaries) == 1:
                return chunk_summaries[0]

            merged = llm.chat(
                messages=[
                    {"role": "system", "content": _FULL_SUMMARY_PROMPT.format(summaries="\n\n".join(chunk_summaries))},
                    {"role": "user", "content": "Merge into the final structured summary."},
                ],
                temperature=0.2,
            )
            return merged.strip() if merged else "\n\n".join(chunk_summaries)

        except Exception as e:
            logger.warning("stt_summarize_failed", error=str(e))
            return None
