"""Text-to-Speech tool — synthesize speech from text via edge-tts (free, no API key).

Engine: edge-tts (Microsoft Edge online voices — high quality, supports 100+ languages,
no API key, no local model). Runs async internally (edge-tts is asyncio-based).

Output: MP3 file saved to output dir (or custom path) — ready for Drive upload / playback.
Long text: auto-split vào các block ~3000 chars (giới hạn an toàn của edge-tts stream)
rồi ghép các chunk audio lại thành 1 file.
"""

import asyncio
import os
import tempfile
from typing import Dict, Any, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)

_CHUNK_LIMIT = 3000  # edge-tts stream an toàn với block ~3k chars


def _split_text(text: str, limit: int = _CHUNK_LIMIT) -> list:
    """Split text vào các block ~limit chars, không cắt giữa câu."""
    chunks = []
    while len(text) > limit:
        cut = text.rfind(". ", 0, limit)
        cut = cut if cut > limit // 2 else limit
        chunks.append(text[: cut + 1].strip())
        text = text[cut + 1 :].strip()
    if text.strip():
        chunks.append(text.strip())
    return chunks


async def _synthesize_chunk(voice: str, text: str, rate: str, pitch: str, out_path: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


class TextToSpeechTool(BaseTool):
    """Convert text to speech (MP3) using edge-tts — free, no API key, 100+ voices."""

    def get_name(self) -> str:
        return "text_to_speech"

    def get_description(self) -> str:
        return (
            "Convert text into a spoken MP3 audio file using edge-tts "
            "(Microsoft voices — free, no API key, 100+ languages). "
            "Voice configurable via TTS_VOICE env (default en-US-AriaNeural; "
            "vi-VN-HoaiMyNeural for Vietnamese). Long text auto-split into chunks. "
            "Returns: {audio_path, voice, chars, duration_estimate_sec}. "
            "Use for generating podcast/audio versions of reports, reading documents aloud."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize",
                },
                "voice": {
                    "type": "string",
                    "description": "Edge-tts voice (default from TTS_VOICE env, e.g. en-US-AriaNeural, vi-VN-HoaiMyNeural)",
                },
                "output_path": {
                    "type": "string",
                    "description": "Output MP3 path (default: auto temp file)",
                },
                "rate": {
                    "type": "string",
                    "description": "Speech rate (e.g. '+10%' faster, '-10%' slower)",
                    "default": "+0%",
                },
                "pitch": {
                    "type": "string",
                    "description": "Pitch adjust (e.g. '+5Hz')",
                    "default": "+0Hz",
                },
            },
            "required": ["text"],
        }

    def execute(
        self,
        text: str,
        voice: Optional[str] = None,
        output_path: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs,
    ) -> ToolResult:
        text = (text or "").strip()
        if not text:
            return ToolResult(success=False, error="text is empty")

        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return ToolResult(
                success=False,
                error="edge-tts not installed. Run: pip install edge-tts",
            )

        voice = voice or config.TTS_VOICE or "en-US-AriaNeural"

        # ── Output path ────────────────────────────────────────────────
        if output_path:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(out_dir, exist_ok=True)
            final_path = output_path if output_path.endswith(".mp3") else output_path + ".mp3"
        else:
            final_path = os.path.join(
                tempfile.gettempdir(), f"tts_{asyncio.get_event_loop().time():.0f}.mp3"
            )

        try:
            chunks = _split_text(text)
            logger.info("tts_synthesizing", chars=len(text), chunks=len(chunks), voice=voice)

            if len(chunks) == 1:
                asyncio.run(_synthesize_chunk(voice, chunks[0], rate, pitch, final_path))
            else:
                # Synthesize từng chunk rồi ghép file
                part_paths = []
                try:
                    for i, chunk in enumerate(chunks):
                        part = f"{final_path}.part{i}"
                        asyncio.run(_synthesize_chunk(voice, chunk, rate, pitch, part))
                        part_paths.append(part)

                    with open(final_path, "wb") as out:
                        for part in part_paths:
                            with open(part, "rb") as pf:
                                out.write(pf.read())
                finally:
                    for part in part_paths:
                        try:
                            os.unlink(part)
                        except OSError:
                            pass

            size = os.path.getsize(final_path)
            # Ước lượng: edge-tts ~ 16kb/s ở default rate → chars/15 ≈ sec
            duration_est = round(len(text) / 15, 1)

            logger.info("tts_success", path=final_path, size=size, chunks=len(chunks))
            return ToolResult(
                success=True,
                result={
                    "audio_path": os.path.abspath(final_path),
                    "voice": voice,
                    "chars": len(text),
                    "chunks": len(chunks),
                    "size_bytes": size,
                    "duration_estimate_sec": duration_est,
                },
                metadata={"voice": voice, "size_bytes": size},
            )

        except Exception as e:
            logger.error("tts_failed", error=str(e), voice=voice)
            return ToolResult(success=False, error=str(e))
