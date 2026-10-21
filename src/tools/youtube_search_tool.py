"""YouTube Data API v3 tool — search videos, get video/channel details.

Uses Google Cloud YouTube Data API v3 (official, stable, no scraping).
Requires: YOUTUBE_API_KEY env (Google Cloud Console → enable "YouTube Data API v3").

Complements `YouTubeTranscriptTool` (free, no key):
  - youtube_search  : find videos by keyword (title, channel, stats, duration)
  - video details   : views, likes, comments, duration, tags
  - channel details : subscriber count, video count

Free quota: 10,000 units/day (search = 100 units → ~100 searches/day).
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import requests

from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)

_YT_API_BASE = "https://www.googleapis.com/youtube/v3"

# ISO-8601 duration (PT1H2M3S) → seconds
def _parse_duration(iso_duration: str) -> int:
    import re
    if not iso_duration:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def _video_id_from(url_or_id: str) -> str:
    import re
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id
    m = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        url_or_id,
    )
    return m.group(1) if m else url_or_id


class YouTubeSearchTool(BaseTool):
    """Search YouTube videos & fetch video/channel details via YouTube Data API v3."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._session = requests.Session()

    def get_name(self) -> str:
        return "youtube_search"

    def get_description(self) -> str:
        return (
            "Search YouTube videos and get detailed info (title, channel, views, "
            "likes, duration, publish date) via official YouTube Data API v3. "
            "Actions: 'search' (find videos by keyword), 'video_details' (stats "
            "for one video), 'channel_details' (channel info). "
            "Best for finding recent tutorial/lecture/news videos. "
            "Returns: {videos: [{video_id, title, url, channel, published, duration_sec, views, description}]}."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "video_details", "channel_details"],
                    "description": "search = find videos; video_details = stats of one video; channel_details = channel info",
                    "default": "search",
                },
                "query": {
                    "type": "string",
                    "description": "Search keyword (action=search). Can also be a video/channel URL or ID.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results (default 10, max 50 for search)",
                    "default": 10,
                },
                "order": {
                    "type": "string",
                    "enum": ["date", "relevance", "viewCount", "rating"],
                    "description": "Result ordering for search (default: relevance)",
                    "default": "relevance",
                },
                "published_after_days": {
                    "type": "integer",
                    "description": "Only videos published within last N days (action=search)",
                },
            },
            "required": ["query"],
        }

    # ── API call helpers ────────────────────────────────────────────────
    def _api_get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params["key"] = config.YOUTUBE_API_KEY
        resp = self._session.get(f"{_YT_API_BASE}/{endpoint}", params=params, timeout=30)
        if resp.status_code in (401, 403):
            detail = resp.json().get("error", {}).get("message", "")
            return {"error": f"YouTube API auth failed (401/403): {detail}"}
        if resp.status_code == 403 and "quota" in resp.text.lower():
            return {"error": "YouTube API quota exceeded (10,000 units/day)"}
        resp.raise_for_status()
        return {"data": resp.json()}

    # ── Actions ─────────────────────────────────────────────────────────
    def execute(
        self,
        query: str,
        action: str = "search",
        max_results: int = 10,
        order: str = "relevance",
        published_after_days: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        if not config.YOUTUBE_API_KEY:
            return ToolResult(
                success=False,
                error=(
                    "YOUTUBE_API_KEY not configured. "
                    "Get one at https://console.cloud.google.com → enable 'YouTube Data API v3' → Credentials → API Key. "
                    "(For transcripts without a key, use youtube_transcript tool instead.)"
                ),
            )

        try:
            if action == "search":
                return self._search(query, max_results, order, published_after_days)
            if action == "video_details":
                return self._video_details(query)
            if action == "channel_details":
                return self._channel_details(query)
            return ToolResult(success=False, error=f"Unknown action: {action}")
        except requests.exceptions.HTTPError as e:
            logger.error("youtube_api_http_error", error=str(e))
            return ToolResult(success=False, error=f"YouTube API error: {e}")
        except Exception as e:
            logger.error("youtube_search_failed", action=action, error=str(e))
            return ToolResult(success=False, error=str(e))

    def _search(
        self,
        query: str,
        max_results: int,
        order: str,
        published_after_days: Optional[int],
    ) -> ToolResult:
        max_results = min(max(max_results, 1), 50)
        params: Dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": order,
        }
        if published_after_days:
            after = datetime.utcnow() - timedelta(days=published_after_days)
            params["publishedAfter"] = after.strftime("%Y-%m-%dT%H:%M:%SZ")

        res = self._api_get("search", params)
        if "error" in res:
            return ToolResult(success=False, error=res["error"])

        items = res["data"].get("items", [])

        # Batch video stats (1 extra call for up to 50 videos — cheap: 1 unit)
        video_ids = [it.get("id", {}).get("videoId", "") for it in items if it.get("id", {}).get("videoId")]
        stats_by_id = self._batch_stats(video_ids)

        videos = []
        for it in items:
            vid = it.get("id", {}).get("videoId", "")
            sn = it.get("snippet", {})
            stats = stats_by_id.get(vid, {})
            videos.append({
                "video_id": vid,
                "title": sn.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "channel": sn.get("channelTitle", ""),
                "channel_id": sn.get("channelId", ""),
                "published": sn.get("publishedAt", ""),
                "description": (sn.get("description", "") or "")[:500],
                "duration_sec": stats.get("duration_sec", 0),
                "views": stats.get("views", 0),
                "likes": stats.get("likes", 0),
                "comments": stats.get("comments", 0),
            })

        logger.info("youtube_search_success", query=query, count=len(videos))
        return ToolResult(
            success=True,
            result={"query": query, "order": order, "count": len(videos), "videos": videos},
            metadata={"query": query, "count": len(videos)},
        )

    def _video_details(self, url_or_id: str) -> ToolResult:
        vid = _video_id_from(url_or_id)
        res = self._api_get("videos", {"part": "snippet,statistics,contentDetails", "id": vid})
        if "error" in res:
            return ToolResult(success=False, error=res["error"])

        items = res["data"].get("items", [])
        if not items:
            return ToolResult(success=False, error=f"Video not found: {vid}")

        it = items[0]
        sn, st, cd = it.get("snippet", {}), it.get("statistics", {}), it.get("contentDetails", {})
        video = {
            "video_id": vid,
            "title": sn.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "channel": sn.get("channelTitle", ""),
            "published": sn.get("publishedAt", ""),
            "description": sn.get("description", ""),
            "duration_sec": _parse_duration(cd.get("duration", "")),
            "views": int(st.get("viewCount", 0)),
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "tags": sn.get("tags", [])[:20],
        }
        return ToolResult(success=True, result={"video": video}, metadata={"video_id": vid})

    def _channel_details(self, url_or_id: str) -> ToolResult:
        # URL → channel ID
        import re
        chan_id = url_or_id
        m = re.search(r"youtube\.com/channel/(UC[a-zA-Z0-9_-]+)", url_or_id)
        if m:
            chan_id = m.group(1)
        else:
            m = re.search(r"youtube\.com/@([\w.-]+)", url_or_id)
            if m:
                res = self._api_get("channels", {"part": "id", "forHandle": m.group(1)})
                if "error" in res:
                    return ToolResult(success=False, error=res["error"])
                items = res["data"].get("items", [])
                if items:
                    chan_id = items[0].get("id", "")
        params = (
            {"part": "snippet,statistics", "id": chan_id}
            if chan_id.startswith("UC")
            else {"part": "snippet,statistics", "forHandle": url_or_id.lstrip("@")}
        )
        res = self._api_get("channels", params)
        if "error" in res:
            return ToolResult(success=False, error=res["error"])

        items = res["data"].get("items", [])
        if not items:
            return ToolResult(success=False, error=f"Channel not found: {url_or_id}")

        it = items[0]
        sn, st = it.get("snippet", {}), it.get("statistics", {})
        channel = {
            "channel_id": it.get("id", ""),
            "title": sn.get("title", ""),
            "url": f"https://www.youtube.com/channel/{it.get('id', '')}",
            "description": (sn.get("description", "") or "")[:500],
            "subscribers": int(st.get("subscriberCount", 0)),
            "video_count": int(st.get("videoCount", 0)),
            "total_views": int(st.get("viewCount", 0)),
        }
        return ToolResult(success=True, result={"channel": channel})

    def _batch_stats(self, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch statistics for multiple videos in 1 call (costs 1 quota unit)."""
        if not video_ids:
            return {}
        try:
            res = self._api_get(
                "videos",
                {"part": "statistics,contentDetails", "id": ",".join(video_ids)},
            )
            if "error" in res:
                return {}
            out = {}
            for it in res["data"].get("items", []):
                st, cd = it.get("statistics", {}), it.get("contentDetails", {})
                out[it.get("id", "")] = {
                    "views": int(st.get("viewCount", 0) or 0),
                    "likes": int(st.get("likeCount", 0) or 0),
                    "comments": int(st.get("commentCount", 0) or 0),
                    "duration_sec": _parse_duration(cd.get("duration", "")),
                }
            return out
        except Exception as e:
            logger.warning("youtube_batch_stats_failed", error=str(e))
            return {}
