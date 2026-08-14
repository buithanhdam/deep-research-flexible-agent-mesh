#!/usr/bin/env python3
"""
HuggingFace Hub Tool — Free Hub API, no key needed.

Dual-mode:
  • As a BaseTool subclass (HuggingFaceTool) for the agent pipeline.
  • As a standalone CLI script: python3 hf_tool.py [--limit 20] [--sort trending]
"""
import sys
import json
import argparse
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

logger = get_logger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (research-bot/1.0)"}
BASE = "https://huggingface.co/api"


def _fetch_models(limit: int, sort: str) -> List[Dict[str, Any]]:
    """Fetch trending/recent models from HuggingFace Hub (internal helper)."""
    params = urllib.parse.urlencode({
        "sort": sort,
        "direction": -1,
        "limit": limit,
        "full": "false",
        "config": "false",
    })
    url = f"{BASE}/models?{params}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        return [{
            "id": m.get("modelId") or m.get("id"),
            "url": f"https://huggingface.co/{m.get('modelId') or m.get('id')}",
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "pipeline_tag": m.get("pipeline_tag") or "unknown",
            "last_modified": m.get("lastModified") or m.get("updatedAt") or "",
            "tags": m.get("tags", [])[:5],
        } for m in data]
    except Exception as e:
        logger.warning("hf_models_failed", error=str(e))
        return []


def _fetch_spaces(limit: int, sort: str) -> List[Dict[str, Any]]:
    """Fetch trending/recent Spaces from HuggingFace Hub (internal helper)."""
    params = urllib.parse.urlencode({
        "sort": sort,
        "direction": -1,
        "limit": limit,
        "full": "false",
    })
    url = f"{BASE}/spaces?{params}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        return [{
            "id": s.get("id"),
            "url": f"https://huggingface.co/spaces/{s.get('id')}",
            "likes": s.get("likes", 0),
            "sdk": s.get("sdk") or "unknown",
            "last_modified": s.get("lastModified") or s.get("updatedAt") or "",
        } for s in data]
    except Exception as e:
        logger.warning("hf_spaces_failed", error=str(e))
        return []


class HuggingFaceTool(BaseTool):
    """Fetch trending models & spaces from HuggingFace Hub (free, no API key)."""

    def get_name(self) -> str:
        return "huggingface_search"

    def get_description(self) -> str:
        return (
            "Search HuggingFace Hub for trending/recent AI models and Spaces. "
            "Free API — no key needed. "
            "Use to discover popular LLMs, diffusion models, demos. "
            "Returns model id, url, downloads, likes, pipeline_tag."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "enum": ["models", "spaces", "both"],
                    "description": "What to fetch: models, spaces, or both (default: both)",
                    "default": "both",
                },
                "sort": {
                    "type": "string",
                    "enum": ["trending", "likes", "downloads", "createdAt"],
                    "description": "Sort order (default: trending)",
                    "default": "trending",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max items per resource (default: 10)",
                    "default": 10,
                },
            },
            "required": [],
        }

    def execute(
        self,
        resource_type: str = "both",
        sort: str = "trending",
        limit: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Execute HuggingFace Hub search.

        Args:
            resource_type: 'models', 'spaces', or 'both'.
            sort: Sort order.
            limit: Max items per resource.

        Returns:
            ToolResult with models and/or spaces.
        """
        try:
            result: Dict[str, Any] = {}

            if resource_type in ("models", "both"):
                models = _fetch_models(limit, sort)
                result["models"] = models
                result["models_count"] = len(models)

            if resource_type in ("spaces", "both"):
                spaces = _fetch_spaces(limit, sort)
                result["spaces"] = spaces
                result["spaces_count"] = len(spaces)

            logger.info(
                "hf_search_done",
                resource_type=resource_type,
                models=result.get("models_count", 0),
                spaces=result.get("spaces_count", 0),
            )

            if not result.get("models") and not result.get("spaces"):
                return ToolResult(
                    success=True,
                    result={**result, "message": "HuggingFace Hub returned no results."},
                    metadata={"resource_type": resource_type, "sort": sort},
                )

            return ToolResult(
                success=True,
                result=result,
                metadata={"resource_type": resource_type, "sort": sort, "limit": limit},
            )
        except Exception as e:
            logger.error("hf_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))


# ─────────────────────────────────────────────
# Standalone CLI mode (kept for backward compat)
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sort", default="trending", choices=["trending", "likes", "downloads", "createdAt"])
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    models = _fetch_models(args.limit, args.sort)
    spaces = _fetch_spaces(args.limit, args.sort)

    print(f"[INFO] Models: {len(models)}, Spaces: {len(spaces)}", file=sys.stderr)

    result = json.dumps({"models": models, "spaces": spaces}, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(result)
    else:
        with open(args.output, "w") as f:
            f.write(result)


if __name__ == "__main__":
    main()
