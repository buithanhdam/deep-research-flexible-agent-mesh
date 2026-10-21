"""OCR tool — extract text from images: RapidOCR primary + Gemini vision fallback.

Engine chain (auto mode):
  1. RapidOCR (https://github.com/RapidAI/RapidOCR) — lightweight ONNX runtime,
     text detection (DBNet) + recognition (CRNN). Nhanh, free, chạy local.
     Tốt với: scanned docs, screenshots, ảnh chữ dày.
  2. LLM vision fallback (Gemini) — khi RapidOCR trả text rỗng/thưa
     (ảnh không phải văn bản: sinh vật học, diagram, ảnh khoa học...),
     Gemini vision extract thông tin theo prompt linh hoạt.

Modes: 'auto' (default — RapidOCR, fallback LLM) | 'rapidocr' | 'llm'
Input: local image path hoặc URL (png/jpg/jpeg/webp/bmp/gif).
"""

import os
import tempfile
from typing import Dict, Any, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)

_SUPPORTED = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif")

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

# Ngưỡng: RapidOCR text ngắn hơn này coi là "không có text đủ ý nghĩa" → fallback LLM
_MIN_TEXT_LEN = 30


def _download_image(url: str) -> str:
    import requests
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    suffix = os.path.splitext(url.split("?")[0])[1].lower() or ".png"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    return path


class OCRTool(BaseTool):
    """Extract text from images — RapidOCR (local, fast) with Gemini vision fallback."""

    def get_name(self) -> str:
        return "ocr"

    def get_description(self) -> str:
        return (
            "Extract text from images using OCR. Primary engine: RapidOCR "
            "(local, lightweight, text detection + recognition — great for "
            "scanned docs & screenshots). Automatic fallback to Gemini vision "
            "LLM for non-text images (photos, biology, diagrams, scientific "
            "visuals) where classic OCR fails. Modes: 'auto' (default), "
            "'rapidocr', 'llm'. Input: local image path or URL "
            "(png/jpg/webp/bmp/gif). "
            "Returns: {text, engine, boxes?, confidence?, fallback_used}."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Local image file path or URL",
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "rapidocr", "llm"],
                    "description": "auto = RapidOCR then LLM fallback; rapidocr = local only; llm = Gemini vision only",
                    "default": "auto",
                },
                "prompt": {
                    "type": "string",
                    "description": "Extraction instruction for LLM mode (e.g. 'transcribe all text', 'describe this organism')",
                },
                "language_hint": {
                    "type": "string",
                    "description": "Language hint for RapidOCR ordering (e.g. 'vi', 'en')",
                },
            },
            "required": ["image_path"],
        }

    def execute(
        self,
        image_path: str,
        mode: str = "auto",
        prompt: Optional[str] = None,
        language_hint: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        tmp_path = None
        try:
            src = image_path.strip()
            if src.startswith(("http://", "https://")):
                tmp_path = _download_image(src)
                src = tmp_path
            elif not os.path.isfile(src):
                return ToolResult(success=False, error=f"Image not found: {image_path}")

            ext = os.path.splitext(src)[1].lower()
            if ext not in _SUPPORTED:
                return ToolResult(
                    success=False,
                    error=f"Unsupported image format '{ext}'. Supported: {', '.join(_SUPPORTED)}",
                )

            if mode not in ("auto", "rapidocr", "llm"):
                return ToolResult(success=False, error=f"Invalid mode: {mode}")

            # ── Mode: LLM only ──────────────────────────────────────────
            if mode == "llm":
                return self._llm_ocr(src, ext, prompt)

            # ── Mode: RapidOCR (primary) ───────────────────────────────
            ocr_result = self._rapidocr(src, language_hint)

            if ocr_result.get("ok"):
                if mode == "rapidocr":
                    return ocr_result["tool_result"]

                # auto: text đủ dài → trả luôn RapidOCR result
                text_len = len(ocr_result["text"])
                if text_len >= _MIN_TEXT_LEN:
                    return ocr_result["tool_result"]

                logger.info("ocr_sparse_text_fallback_llm", text_len=text_len)

            # ── Mode auto: RapidOCR fail/thưa → LLM vision fallback ──────
            fallback = self._llm_ocr(src, ext, prompt)
            if fallback.success:
                fallback.result["fallback_used"] = ocr_result.get("ok", False)
                fallback.result["rapidocr_text"] = ocr_result.get("text", "")
                return fallback

            # Cả 2 fail → trả kết quả RapidOCR (nếu có) hoặc lỗi LLM
            if ocr_result.get("ok") and ocr_result["text"]:
                tr = ocr_result["tool_result"]
                tr.result["fallback_used"] = False
                return tr

            return fallback

        except Exception as e:
            logger.error("ocr_failed", image=image_path, error=str(e))
            return ToolResult(success=False, error=str(e))
        finally:
            if tmp_path and os.path.isfile(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ── Engine 1: RapidOCR ─────────────────────────────────────────────
    def _rapidocr(self, image_path: str, language_hint: Optional[str]) -> Dict[str, Any]:
        """Run RapidOCR. Trả {'ok': bool, 'text': str, 'tool_result': ToolResult}."""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            return {
                "ok": False,
                "text": "",
                "tool_result": ToolResult(
                    success=False,
                    error="rapidocr-onnxruntime not installed. Run: pip install rapidocr-onnxruntime",
                ),
            }

        try:
            engine = RapidOCR()
            result, _elapsed = engine(image_path)

            texts = []
            boxes = []
            scores = []
            if result:
                for item in result:
                    box, text, score = item[0], item[1], item[2]
                    if text:
                        texts.append(str(text))
                        boxes.append(
                            [[round(p[0]), round(p[1])] for p in box]
                        )
                        scores.append(round(float(score or 0), 3))

            full_text = "\n".join(texts)
            tool_result = ToolResult(
                success=bool(full_text.strip()),
                result={
                    "text": full_text,
                    "engine": "rapidocr",
                    "lines": len(texts),
                    "boxes": boxes[:50],
                    "confidence": round(sum(scores) / len(scores), 3) if scores else 0.0,
                } if full_text.strip() else {"text": "", "engine": "rapidocr", "lines": 0},
                error=None if full_text.strip() else "No text detected by RapidOCR",
                metadata={"engine": "rapidocr"},
            )
            return {"ok": True, "text": full_text, "tool_result": tool_result}

        except Exception as e:
            logger.error("rapidocr_failed", error=str(e))
            return {
                "ok": False,
                "text": "",
                "tool_result": ToolResult(success=False, error=f"RapidOCR failed: {e}"),
            }

    # ── Engine 2: Gemini vision ─────────────────────────────────────────
    def _llm_ocr(self, image_path: str, ext: str, prompt: Optional[str]) -> ToolResult:
        """OCR/analysis via Gemini vision — cho ảnh không phải text thuần."""
        try:
            from src.llm.gemini_client import get_gemini_client

            client = get_gemini_client()
            if client is None:
                return ToolResult(
                    success=False,
                    error="LLM vision fallback unavailable — GEMINI_API_KEY not configured.",
                )

            with open(image_path, "rb") as f:
                image_bytes = f.read()

            mime = _MIME_BY_EXT.get(ext, "image/png")
            instruction = (
                prompt
                or (
                    "Extract ALL text visible in this image (OCR). Preserve "
                    "layout and reading order. If the image is not text-based "
                    "(e.g. a photo, organism, diagram), describe what you see "
                    "in detail including any labels, captions, data, or "
                    "scientific content."
                )
            )

            vision = client.analyze_image(
                image_bytes=image_bytes,
                mime_type=mime,
                prompt=instruction,
            )
            content = vision.get("content", "").strip()

            if not content:
                return ToolResult(success=False, error="Gemini vision returned empty result")

            return ToolResult(
                success=True,
                result={
                    "text": content,
                    "engine": "gemini_vision",
                    "model": vision.get("model", ""),
                },
                metadata={"engine": "gemini_vision"},
            )

        except Exception as e:
            logger.error("llm_ocr_failed", error=str(e))
            return ToolResult(success=False, error=f"LLM vision OCR failed: {e}")
