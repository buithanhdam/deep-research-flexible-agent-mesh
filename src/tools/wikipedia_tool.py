"""Wikipedia tool — search & fetch article summaries (free REST API, no key)."""

import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)

HEADERS = {"User-Agent": "research-bot/1.0 (multi-agent-system)"}
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/"


class WikipediaTool(BaseTool):
    """Search Wikipedia and fetch article summaries.

    Free MediaWiki REST/API — no API key needed.
    Supports multiple languages via the 'language' param.
    """

    def get_name(self) -> str:
        return "wikipedia_search"

    def get_description(self) -> str:
        return (
            "Search Wikipedia and fetch article summaries. "
            "Free — no API key (MediaWiki REST API). "
            "Input: query, language (default 'en'), limit. "
            "Returns title, summary, URL for each matching article. "
            "Use for encyclopedic / factual background on any topic."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "language": {"type": "string", "default": "en", "description": "ISO-639-1 language code"},
                "limit": {"type": "integer", "default": 5, "description": "Max results"},
            },
            "required": ["query"],
        }

    def execute(
        self,
        query: str,
        language: str = "en",
        limit: int = 5,
        **kwargs,
    ) -> ToolResult:
        """Search Wikipedia."""
        try:
            api_url = f"https://{language}.wikipedia.org/w/api.php"
            params = urllib.parse.urlencode({
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
            })
            url = f"{api_url}?{params}"

            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                return ToolResult(
                    success=True,
                    result={"articles": [], "message": f"No Wikipedia articles found for '{query}'."},
                    metadata={"query": query, "language": language},
                )

            # Fetch summary for top results
            articles = []
            for item in search_results[:limit]:
                title = item.get("title", "")
                page_id = item.get("pageid")
                snippet = item.get("snippet", "")
                # Clean HTML tags from snippet
                import re
                clean_snippet = re.sub(r"<[^>]+>", "", snippet)

                article = {
                    "title": title,
                    "url": f"https://{language}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "snippet": clean_snippet,
                    "pageid": page_id,
                }

                # Try to fetch full summary via REST
                try:
                    summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ', '_'))}"
                    sreq = urllib.request.Request(summary_url, headers=HEADERS)
                    with urllib.request.urlopen(sreq, timeout=10) as sresp:
                        sdata = json.loads(sresp.read())
                    article["summary"] = sdata.get("extract", clean_snippet)
                    article["thumbnail"] = (sdata.get("thumbnail") or {}).get("source")
                except Exception:
                    article["summary"] = clean_snippet

                articles.append(article)

            logger.info("wikipedia_search_done", query=query, found=len(articles))

            return ToolResult(
                success=True,
                result={"articles": articles, "count": len(articles)},
                metadata={"query": query, "language": language, "limit": limit},
            )
        except Exception as e:
            logger.error("wikipedia_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
