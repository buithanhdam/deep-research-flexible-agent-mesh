"""YouTube transcript tool — fetch video transcripts (free, no API key).

Uses youtube-transcript-api which scrapes YouTube's transcript endpoint
directly — no Google Cloud API key required.
"""

import re
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)


def _extract_video_id(url_or_id: str) -> str:
    """Extract 11-char video ID from a YouTube URL or return as-is if already an ID."""
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    # Common URL patterns
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    return url_or_id  # best-effort


class YouTubeTranscriptTool(BaseTool):
    """Fetch transcript / subtitles from a YouTube video.

    Free (youtube-transcript-api, no API key). Works for most public videos
    that have captions (auto-generated or manual).
    """

    def get_name(self) -> str:
        return "youtube_transcript"

    def get_description(self) -> str:
        return (
            "Fetch the transcript (subtitles) of a YouTube video. "
            "Free — no API key needed (uses youtube-transcript-api). "
            "Input: video_url or video_id. "
            "Returns full transcript text + segment timestamps. "
            "Use to extract content from tutorial / lecture videos."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "video_url": {
                    "type": "string",
                    "description": "YouTube video URL or 11-char video ID",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Preferred language codes (default: ['en', 'vi'])",
                    "default": ["en", "vi"],
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate transcript to N chars (default: 8000)",
                    "default": 8000,
                },
            },
            "required": ["video_url"],
        }

    def execute(
        self,
        video_url: str,
        languages: Optional[List[str]] = None,
        max_chars: int = 8000,
        **kwargs,
    ) -> ToolResult:
        """Fetch YouTube transcript."""
        if languages is None:
            languages = ["en", "vi"]

        try:
            from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        except ImportError as e:
            return ToolResult(
                success=False,
                error="youtube-transcript-api not installed. Run: pip install youtube-transcript-api",
            )

        video_id = _extract_video_id(video_url)
        logger.info("youtube_transcript_fetch", video_id=video_id)

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)

            # Build full text + segments
            full_text_parts = []
            segments = []
            for seg in transcript_list:
                text = seg.get("text", "").strip()
                start = seg.get("start", 0)
                full_text_parts.append(text)
                segments.append({"start": round(start, 1), "text": text})

            full_text = " ".join(full_text_parts)
            if len(full_text) > max_chars:
                full_text = full_text[:max_chars] + "...[truncated]"

            return ToolResult(
                success=True,
                result={
                    "video_id": video_id,
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "transcript": full_text,
                    "segments": segments[:50],  # limit segments for context
                    "segment_count": len(segments),
                    "languages_tried": languages,
                },
                metadata={"video_id": video_id, "segment_count": len(segments)},
            )
        except TranscriptsDisabled:
            return ToolResult(
                success=False,
                error=f"Transcripts are disabled for video {video_id}",
            )
        except NoTranscriptFound:
            return ToolResult(
                success=False,
                error=f"No transcript found for video {video_id} in languages {languages}",
            )
        except Exception as e:
            logger.error("youtube_transcript_failed", video_id=video_id, error=str(e))
            return ToolResult(success=False, error=str(e))
