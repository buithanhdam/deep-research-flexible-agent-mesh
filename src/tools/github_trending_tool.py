#!/usr/bin/env python3
"""
GitHub Repo Search Tool — Free Search API (optional GITHUB_TOKEN for higher rate limit).

Dual-mode:
  • As a BaseTool subclass (GitHubRepoTool) for the agent pipeline.
  • As a standalone CLI script: python3 github_trending_tool.py [--days 1] [--stars 50]
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "research-bot/1.0",
    "Accept": "application/vnd.github.v3+json",
}

# Default trending queries (used by CLI mode + when no query provided)
DEFAULT_SEARCH_QUERIES = [
    "language:python topic:llm",
    "language:python topic:agent",
    "language:python topic:rag",
    "topic:mcp",
    "topic:langchain",
    "topic:n8n",
    "topic:ai-agent",
    "language:python topic:openai",
]


def _build_headers() -> Dict[str, str]:
    """Build request headers, inject GITHUB_TOKEN if available."""
    headers = dict(DEFAULT_HEADERS)
    token = config.GITHUB_TOKEN or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _search_github(query: str, since_date: str, min_stars: int, per_page: int = 10) -> List[Dict[str, Any]]:
    """Search GitHub repos (internal helper)."""
    full_query = f"{query} created:>{since_date} stars:>{min_stars}"
    params = urllib.parse.urlencode({
        "q": full_query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
    })
    url = f"https://api.github.com/search/repositories?{params}"

    try:
        req = urllib.request.Request(url, headers=_build_headers())
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        repos = []
        for item in data.get("items", []):
            repos.append({
                "name": item["full_name"],
                "url": item["html_url"],
                "description": item.get("description") or "",
                "stars": item["stargazers_count"],
                "language": item.get("language") or "unknown",
                "topics": item.get("topics", [])[:8],
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
            })
        return repos
    except urllib.error.HTTPError as e:
        if e.code == 403:
            logger.warning("github_rate_limited", hint="Set GITHUB_TOKEN env var for higher limits")
        else:
            logger.warning("github_api_error", code=e.code, query=query)
    except Exception as e:
        logger.warning("github_search_failed", query=query, error=str(e))
    return []


class GitHubRepoTool(BaseTool):
    """Search GitHub repositories by query/keyword (free API, optional token)."""

    def get_name(self) -> str:
        return "github_search"

    def get_description(self) -> str:
        return (
            "Search GitHub repositories by keyword, language, or topic. "
            "Free Search API (60 req/h without token, 5000 with GITHUB_TOKEN). "
            "Returns repo name, url, description, stars, language, topics. "
            "Use to find reference code, trending AI/agent repos, or libraries."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query — GitHub search syntax. "
                        "Examples: 'multi-agent', 'topic:langchain', 'language:python rag'. "
                        "If omitted, fetches trending AI/agent repos."
                    ),
                },
                "min_stars": {
                    "type": "integer",
                    "description": "Minimum star count filter (default: 50)",
                    "default": 50,
                },
                "days": {
                    "type": "integer",
                    "description": "Only repos created in last N days (default: 30)",
                    "default": 30,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max repos to return (default: 10)",
                    "default": 10,
                },
            },
            "required": [],
        }

    def execute(
        self,
        query: Optional[str] = None,
        min_stars: int = 50,
        days: int = 30,
        limit: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Execute GitHub repo search.

        Args:
            query: GitHub search query. If None, uses default trending queries.
            min_stars: Minimum stars filter.
            days: Look-back window for repo creation.
            limit: Max repos to return.

        Returns:
            ToolResult with list of repo dicts.
        """
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

            # If user provides a specific query, search just that.
            # Otherwise fall back to the default trending query set.
            queries = [query] if query and query.strip() else DEFAULT_SEARCH_QUERIES

            all_repos: List[Dict[str, Any]] = []
            seen = set()

            for i, q in enumerate(queries):
                per_page = min(limit, 10)
                repos = _search_github(q, since, min_stars, per_page=per_page)
                for r in repos:
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        all_repos.append(r)
                # Rate-limit safety between multiple queries
                if i < len(queries) - 1:
                    time.sleep(2)
                # Early exit if we have enough
                if len(all_repos) >= limit:
                    break

            all_repos.sort(key=lambda x: x["stars"], reverse=True)
            all_repos = all_repos[:limit]

            logger.info("github_search_done", query=query, found=len(all_repos))

            if not all_repos:
                return ToolResult(
                    success=True,
                    result={"repos": [], "message": f"No GitHub repos found for '{query or 'trending'}'."},
                    metadata={"query": query, "min_stars": min_stars, "days": days},
                )

            return ToolResult(
                success=True,
                result={"repos": all_repos, "count": len(all_repos)},
                metadata={"query": query, "min_stars": min_stars, "days": days},
            )
        except Exception as e:
            logger.error("github_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))


# ─────────────────────────────────────────────
# Standalone CLI mode (kept for backward compat)
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--stars", type=int, default=50)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    all_repos = []
    seen = set()

    for i, query in enumerate(DEFAULT_SEARCH_QUERIES):
        repos = _search_github(query, since, args.stars)
        for r in repos:
            if r["url"] not in seen:
                seen.add(r["url"])
                all_repos.append(r)
        print(f"[INFO] '{query}': {len(repos)} repos", file=sys.stderr)

        if i < len(DEFAULT_SEARCH_QUERIES) - 1:
            time.sleep(2)

    all_repos.sort(key=lambda x: x["stars"], reverse=True)

    result = json.dumps(all_repos, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(result)
    else:
        with open(args.output, "w") as f:
            f.write(result)

    print(f"[INFO] Total unique repos: {len(all_repos)}", file=sys.stderr)


if __name__ == "__main__":
    main()
