"""Web search tool with Tavily + Gemini Grounding + DuckDuckGo fallback chain.

Fallback order:
  1. Tavily API        (if TAVILY_API_KEY configured) — raw snippets
  2. Gemini Grounding  (if GEMINI_API_KEY configured)  — synthesized answer + citations
  3. DuckDuckGo        (free, no key)                   — raw snippets
"""

import random
import time
from typing import Dict, Any, List, Optional
import requests
from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using Tavily → Gemini Grounding → DuckDuckGo fallback chain."""
    
    def __init__(self, name: str = None, description: str = None, target_domains: list = None, **config):
        """Initialize web search tool.
        
        Args:
            name: Custom tool name
            description: Custom description
            target_domains: List of domains to restrict search (e.g., ['larksuite.com'])
            **config: Additional config
        """
        super().__init__(name, description, target_domains=target_domains, **config)
        self.target_domains = target_domains
    
    def get_name(self) -> str:
        return "web_search"
    
    def get_description(self) -> str:
        return """Search the web for information. Use this when you need current information, facts, or data from the internet.
        
Returns: List of search results with title, url, content snippet."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    
    def execute(self, query: str, max_results: int = 5, **kwargs) -> ToolResult:
        """Execute web search with fallback chain: Tavily → Gemini → DuckDuckGo.
        
        Args:
            query: Search query
            max_results: Maximum results
        
        Returns:
            ToolResult with search results
        """
        # 1. Try Tavily first (raw snippets)
        if config.TAVILY_API_KEY:
            result = self._search_tavily(query, max_results)
            if result.success:
                return result
            logger.warning("tavily_failed_trying_gemini", error=result.error)

        # 2. Fallback to Gemini Search Grounding (synthesized answer + citations)
        if config.GEMINI_API_KEY:
            result = self._search_gemini(query, max_results)
            if result.success:
                return result
            logger.warning("gemini_failed_trying_duckduckgo", error=result.error)

        # 3. Final fallback to DuckDuckGo (free, no key)
        return self._search_duckduckgo(query, max_results)

    def _search_gemini(self, query: str, max_results: int) -> ToolResult:
        """Search using Google Search Grounding via GeminiClient.

        Returns a synthesized answer + citation sources, normalized to the same
        result shape as Tavily/DuckDuckGo (list of {title, url, content}).
        """
        try:
            from src.llm.gemini_client import get_gemini_client

            client = get_gemini_client()
            if client is None:
                return ToolResult(
                    success=False,
                    error="GeminiClient not available — GEMINI_API_KEY not configured.",
                )

            grounded = client.search_grounding(
                query=query,
                max_citations=max_results,
            )

            answer = grounded.get("answer", "")
            citations = grounded.get("citations", [])

            if not answer and not citations:
                return ToolResult(
                    success=False,
                    error="Gemini returned no answer and no grounding citations.",
                )

            return ToolResult(
                success=True,
                result={
                    "query": query,
                    "answer": answer,
                    "results": citations,
                    "source": "gemini_grounding",
                },
                metadata={
                    "result_count": len(citations),
                    "search_queries": grounded.get("queries", []),
                },
            )

        except Exception as e:
            logger.error("gemini_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
    
    def _search_tavily(self, query: str, max_results: int) -> ToolResult:
        """Search using Tavily API."""
        try:
            search_params = {
                "api_key": config.TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False
            }
            
            # Add domain filter if configured
            if self.target_domains:
                search_params["include_domains"] = self.target_domains
            
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "query": query,
                    "max_results": max_results,
                    "include_answer": True,
                    "include_raw_content": False,
                    **({"include_domains": self.target_domains} if self.target_domains else {})
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.TAVILY_API_KEY}"
                },
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0)
                })
            
            return ToolResult(
                success=True,
                result={
                    "query": query,
                    "answer": data.get("answer"),
                    "results": results,
                    "source": "tavily"
                },
                metadata={"result_count": len(results)}
            )
            
        except Exception as e:
            logger.error("tavily_search_failed", error=str(e))
            return ToolResult(success=False, error=str(e))
    
    def _search_duckduckgo(self, query: str, max_results: int, retries: int = 3) -> ToolResult:
        """Search using DuckDuckGo (free, no API key needed), with retry on rate limit."""
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import RatelimitException

        last_error = None
        for attempt in range(retries):
            try:
                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.text(query, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "content": r.get("body", ""),
                            "score": 0
                        })

                return ToolResult(
                    success=True,
                    result={
                        "query": query,
                        "answer": None,
                        "results": results,
                        "source": "duckduckgo"
                    },
                    metadata={"result_count": len(results)}
                )

            except RatelimitException as e:
                last_error = e
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning("duckduckgo_ratelimited_retrying", attempt=attempt, wait=wait)
                time.sleep(wait)
            except Exception as e:
                logger.error("duckduckgo_search_failed", error=str(e))
                return ToolResult(success=False, error=f"All search methods failed: {str(e)}")

        logger.error("duckduckgo_search_failed", error=str(last_error))
        return ToolResult(success=False, error=f"All search methods failed: {str(last_error)}")
