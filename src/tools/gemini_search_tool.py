"""Gemini Search Grounding tool — uses Google Search via Gemini's built-in grounding.

Unlike traditional search APIs (Tavily, DuckDuckGo) that return raw result snippets,
Gemini Search Grounding lets the model search Google *during inference* and returns
a synthesized answer **with citation sources**. This is useful when the agent needs
a high-quality, real-time, cited answer rather than raw snippets to process manually.

This tool delegates to `GeminiClient.search_grounding()` (src/llm/gemini_client.py),
keeping the google-genai SDK logic inside the LLM client layer — consistent with how
`src.llm.llm_manager` is the single gateway for multi-provider LLM clients.

Requires: `google-genai` SDK + `GEMINI_API_KEY` env var.
Falls back gracefully (returns ToolResult(success=False)) if not configured.
"""

from typing import Dict, Any, Optional

from src.tools.base_tool import BaseTool, ToolResult
from src.llm.gemini_client import get_gemini_client
from src.logger import get_logger

logger = get_logger(__name__)


class GeminiSearchTool(BaseTool):
    """Search the web using Google Search Grounding via Gemini.

    Returns a synthesized answer + grounding citations (title, url).
    This complements `WebSearchTool` (Tavily/DuckDuckGo) — use it when you need
    a grounded, cited answer rather than raw search snippets.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(name, description, **kwargs)

    # ------------------------------------------------------------------ #
    # BaseTool interface
    # ------------------------------------------------------------------ #
    def get_name(self) -> str:
        return "gemini_search"

    def get_description(self) -> str:
        return (
            "Search the web using Google Search Grounding (via Gemini). "
            "Returns a synthesized answer with citation sources. "
            "Best for questions needing real-time, accurate, cited information. "
            "Returns: {answer: str, results: [{title, url, content}], queries: [str]}."
        )

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query / question to ground.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max citation sources to return (default: 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def execute(self, query: str, max_results: int = 5, **kwargs) -> ToolResult:
        """Execute Google Search Grounding via GeminiClient.

        Args:
            query: Search query / question.
            max_results: Max citation sources to return.

        Returns:
            ToolResult with {answer, results, queries, source: "gemini_grounding"}.
        """
        client = get_gemini_client()
        if client is None:
            logger.warning("gemini_search_skipped_no_client")
            return ToolResult(
                success=False,
                error="GeminiClient not available — GEMINI_API_KEY not configured.",
            )

        try:
            grounded = client.search_grounding(
                query=query,
                max_citations=max_results,
            )

            answer = grounded.get("answer", "")
            citations = grounded.get("citations", [])
            queries = grounded.get("queries", [])

            if not answer and not citations:
                logger.warning("gemini_search_empty_response", query=query)
                return ToolResult(
                    success=False,
                    error="Gemini returned no answer and no grounding citations.",
                )

            return ToolResult(
                success=True,
                result={
                    "query": query,
                    "answer": answer,
                    "results": citations,  # same shape as WebSearchTool results
                    "citations": citations,
                    "queries": queries,
                    "source": "gemini_grounding",
                },
                metadata={
                    "result_count": len(citations),
                    "model": grounded.get("model", ""),
                    "search_queries": queries,
                },
            )

        except Exception as e:
            logger.error("gemini_search_failed", error=str(e), query=query)
            return ToolResult(success=False, error=str(e))
