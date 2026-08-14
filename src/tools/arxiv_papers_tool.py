#!/usr/bin/env python3
"""
arXiv Paper Search Tool — Free RSS, no API key needed.

Dual-mode:
  • As a BaseTool subclass (ArxivSearchTool) for the agent pipeline.
  • As a standalone CLI script: python3 arxiv_papers_tool.py [--days 1] [--keyword agent]
"""
import sys
import json
import re
import argparse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)

ARXIV_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG"]
HEADERS = {"User-Agent": "Mozilla/5.0 (research-bot/1.0)"}

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "dc": "http://purl.org/dc/elements/1.0/",
}


def _fetch_category(category: str, since: datetime, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch papers from a single arXiv RSS category (internal helper)."""
    url = f"https://export.arxiv.org/rss/{category}"
    papers: List[Dict[str, Any]] = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()

        root = ET.fromstring(data)
        items = root.findall(".//item")

        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()

            authors = [a.text.strip() for a in item.findall("dc:creator", NS) if a.text]

            pub_raw = item.findtext("pubDate") or ""
            pub_dt = None
            if pub_raw:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_dt = parsedate_to_datetime(pub_raw)
                except Exception:
                    pass

            if pub_dt and pub_dt < since:
                continue

            abstract = re.sub(r"<[^>]+>", "", desc).strip()[:500]

            if keyword:
                combined = (title + " " + abstract).lower()
                if keyword.lower() not in combined:
                    continue

            papers.append({
                "title": title,
                "url": link,
                "authors": authors[:5],
                "abstract": abstract,
                "category": category,
                "published": pub_dt.isoformat() if pub_dt else "unknown",
            })
    except Exception as e:
        logger.warning("arxiv_fetch_failed", category=category, error=str(e))
    return papers


class ArxivSearchTool(BaseTool):
    """Search recent arXiv papers by category and keyword (free, no API key)."""

    def get_name(self) -> str:
        return "arxiv_search"

    def get_description(self) -> str:
        return (
            "Search recent academic papers on arXiv (cs.AI, cs.CL, cs.LG by default). "
            "Free RSS endpoint — no API key needed. "
            "Use for AI/ML/NLP research topics. Returns title, authors, abstract, URL, published date."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Keyword to filter papers (e.g. 'agent', 'rag', 'transformer')",
                },
                "categories": {
                    "type": "string",
                    "description": "Comma-separated arXiv categories (default: 'cs.AI,cs.CL,cs.LG')",
                    "default": "cs.AI,cs.CL,cs.LG",
                },
                "days": {
                    "type": "integer",
                    "description": "Look back N days (default: 7)",
                    "default": 7,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max papers to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["keyword"],
        }

    def execute(
        self,
        keyword: str,
        categories: str = "cs.AI,cs.CL,cs.LG",
        days: int = 7,
        limit: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Execute arXiv search.

        Args:
            keyword: Keyword to filter papers.
            categories: Comma-separated arXiv categories.
            days: Look-back window in days.
            limit: Maximum number of papers to return.

        Returns:
            ToolResult with list of paper dicts.
        """
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            cats = [c.strip() for c in categories.split(",") if c.strip()] or ARXIV_CATEGORIES

            all_papers: List[Dict[str, Any]] = []
            seen = set()

            for cat in cats:
                papers = _fetch_category(cat, since, keyword=keyword)
                for p in papers:
                    if p["url"] not in seen:
                        seen.add(p["url"])
                        all_papers.append(p)

            all_papers.sort(key=lambda x: x["published"], reverse=True)
            all_papers = all_papers[:limit]

            logger.info("arxiv_search_done", keyword=keyword, found=len(all_papers))

            if not all_papers:
                return ToolResult(
                    success=True,
                    result={"papers": [], "message": f"No arXiv papers found for '{keyword}' in last {days} days."},
                    metadata={"keyword": keyword, "categories": cats, "days": days},
                )

            return ToolResult(
                success=True,
                result={"papers": all_papers, "count": len(all_papers)},
                metadata={"keyword": keyword, "categories": cats, "days": days},
            )
        except Exception as e:
            logger.error("arxiv_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))


# ─────────────────────────────────────────────
# Standalone CLI mode (kept for backward compat)
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--topics", default=",".join(ARXIV_CATEGORIES))
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    categories = [c.strip() for c in args.topics.split(",")]

    all_papers = []
    seen = set()

    for cat in categories:
        papers = _fetch_category(cat, since, keyword=args.keyword)
        for p in papers:
            if p["url"] not in seen:
                seen.add(p["url"])
                all_papers.append(p)
        print(f"[INFO] {cat}: {len(papers)} papers", file=sys.stderr)

    all_papers.sort(key=lambda x: x["published"], reverse=True)

    result = json.dumps({"papers": all_papers, "count": len(all_papers)}, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(result)
    else:
        with open(args.output, "w") as f:
            f.write(result)


if __name__ == "__main__":
    main()
