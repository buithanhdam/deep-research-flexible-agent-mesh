"""News search tool — search recent news via GDELT DOC API (free, no API key).

GDELT (Global Database of Events, Language, and Tone) provides a free
article search API covering worldwide news — no key required.
"""

import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)

HEADERS = {"User-Agent": "research-bot/1.0 (multi-agent-system)"}
GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class NewsSearchTool(BaseTool):
    """Search recent news articles via GDELT DOC API (free, no key).

    Covers worldwide news in 15+ languages. Good for current events,
    tech news, and topic monitoring.
    """

    def get_name(self) -> str:
        return "news_search"

    def get_description(self) -> str:
        return (
            "Search recent news articles worldwide via GDELT DOC API. "
            "Free — no API key needed. Covers 15+ languages. "
            "Input: query, mode (ArtList|ArtRank), max_records, timespan. "
            "Returns title, url, domain, date, language for each article. "
            "Use for current events, tech news, breaking developments."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (keywords)"},
                "max_records": {"type": "integer", "default": 10, "description": "Max articles (default 10)"},
                "timespan": {
                    "type": "string",
                    "default": "1week",
                    "description": "Lookback: 1day, 1week, 1month (default 1week)",
                },
                "language": {
                    "type": "string",
                    "default": "",
                    "description": "Filter by language (e.g. 'english', 'vietnamese'). Empty = all.",
                },
            },
            "required": ["query"],
        }

    def execute(
        self,
        query: str,
        max_records: int = 10,
        timespan: str = "1week",
        language: str = "",
        **kwargs,
    ) -> ToolResult:
        """Search news via GDELT."""
        try:
            params = {
                "query": query,
                "mode": "ArtList",
                "maxrecords": str(max_records),
                "format": "json",
                "sort": "DateDesc",
                "timespan": timespan,
            }
            if language:
                params["sourcelang"] = language

            url = f"{GDELT_API}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()

            data = json.loads(raw)
            articles = data.get("articles", [])

            if not articles:
                return ToolResult(
                    success=True,
                    result={"articles": [], "message": f"No news articles found for '{query}' in {timespan}."},
                    metadata={"query": query, "timespan": timespan},
                )

            results = []
            for art in articles[:max_records]:
                results.append({
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "domain": art.get("domain", ""),
                    "language": art.get("language", ""),
                    "published_date": art.get("seendate", ""),
                    "social_image": art.get("socialimage", ""),
                })

            logger.info("news_search_done", query=query, found=len(results))

            return ToolResult(
                success=True,
                result={"articles": results, "count": len(results)},
                metadata={"query": query, "timespan": timespan, "language": language},
            )
        except json.JSONDecodeError:
            # GDELT sometimes returns empty/non-JSON when no results
            return ToolResult(
                success=True,
                result={"articles": [], "message": f"No results or API returned non-JSON for '{query}'."},
                metadata={"query": query},
            )
        except Exception as e:
            logger.error("news_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
