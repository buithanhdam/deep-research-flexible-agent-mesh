"""Web search tool with Tavily + DuckDuckGo fallback."""

from typing import Dict, Any, List, Optional
import requests
from src.tools.base_tool import BaseTool, ToolResult
from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using Tavily API (with DuckDuckGo fallback)."""
    
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
        """Execute web search.
        
        Args:
            query: Search query
            max_results: Maximum results
        
        Returns:
            ToolResult with search results
        """
        # Try Tavily first
        if config.TAVILY_API_KEY:
            result = self._search_tavily(query, max_results)
            if result.success:
                return result
            logger.warning("tavily_failed_trying_duckduckgo", error=result.error)
        
        # Fallback to DuckDuckGo
        return self._search_duckduckgo(query, max_results)
    
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
    
    def _search_duckduckgo(self, query: str, max_results: int) -> ToolResult:
        """Search using DuckDuckGo (free, no API key needed)."""
        try:
            from duckduckgo_search import DDGS
            
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
            
        except Exception as e:
            logger.error("duckduckgo_search_failed", error=str(e))
            return ToolResult(success=False, error=f"All search methods failed: {str(e)}")
