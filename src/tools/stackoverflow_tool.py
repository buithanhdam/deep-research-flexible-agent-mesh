"""Stack Overflow search tool — free Stack Exchange API, no key required."""

import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)

HEADERS = {"User-Agent": "research-bot/1.0 (multi-agent-system)"}
SO_API = "https://api.stackexchange.com/2.3/search/advanced"


class StackOverflowTool(BaseTool):
    """Search Stack Overflow Q&A via the free Stack Exchange API.

    No API key required (anonymous tier: 300 req/day without key).
    Returns questions with accepted answers, scores, and tags.
    """

    def get_name(self) -> str:
        return "stackoverflow_search"

    def get_description(self) -> str:
        return (
            "Search Stack Overflow for Q&A threads. "
            "Free — no API key (Stack Exchange API, 300 req/day anonymous). "
            "Input: query, tags (optional, e.g. 'python;fastapi'), limit, accepted_only. "
            "Returns title, link, score, answer_count, tags, is_answered. "
            "Use for technical debugging, code solutions, best practices."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "tags": {
                    "type": "string",
                    "description": "Semicolon-separated tags (e.g. 'python;fastapi')",
                    "default": "",
                },
                "limit": {"type": "integer", "default": 10, "description": "Max results"},
                "accepted_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only return questions with accepted answers",
                },
            },
            "required": ["query"],
        }

    def execute(
        self,
        query: str,
        tags: str = "",
        limit: int = 10,
        accepted_only: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Search Stack Overflow."""
        try:
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": str(min(limit, 50)),
                "filter": "withbody",
            }
            if tags:
                params["tagged"] = tags
            if accepted_only:
                params["accepted"] = "True"

            url = f"{SO_API}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                # Stack Exchange API returns gzip — urllib handles it transparently in most cases,
                # but add Accept-Encoding to be safe
                data = json.loads(resp.read())

            items = data.get("items", [])

            if not items:
                return ToolResult(
                    success=True,
                    result={"questions": [], "message": f"No Stack Overflow results for '{query}'."},
                    metadata={"query": query, "tags": tags},
                )

            results = []
            for item in items[:limit]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "score": item.get("score", 0),
                    "answer_count": item.get("answer_count", 0),
                    "is_answered": item.get("is_answered", False),
                    "has_accepted_answer": bool(item.get("accepted_answer_id")),
                    "tags": item.get("tags", [])[:5],
                    "body_excerpt": (item.get("body", "") or "")[:500],
                    "creation_date": item.get("creation_date"),
                })

            logger.info("stackoverflow_search_done", query=query, found=len(results))

            return ToolResult(
                success=True,
                result={"questions": results, "count": len(results)},
                metadata={"query": query, "tags": tags, "accepted_only": accepted_only},
            )
        except Exception as e:
            logger.error("stackoverflow_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
