"""Web scraping tool to extract content from URLs.

Fallback chain: Tavily Extract → Gemini URL Context → Traditional (BeautifulSoup).
"""

from typing import Dict, Any
import os
import requests
from bs4 import BeautifulSoup
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger
from src.config import config

logger = get_logger(__name__)


class WebScrapeTool(BaseTool):
    """Extract and parse content from a webpage."""
    
    def get_name(self) -> str:
        return "web_scrape"
    
    def get_description(self) -> str:
        return """Extract content from a webpage URL. Returns clean text content, title, and metadata.
        
Use this when you have a specific URL and need to read its full content."""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to scrape"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum content length in characters (default: 10000)",
                    "default": 10000
                }
            },
            "required": ["url"]
        }
    
    def execute(self, url: str, max_length: int = 10000) -> ToolResult:
        """Scrape webpage content with fallback: Tavily → Gemini URL Context → BS4.
        
        Args:
            url: URL to scrape
            max_length: Maximum content length
        
        Returns:
            ToolResult with extracted content
        """
        # 1. Try Tavily extract first (cleaner extraction)
        tavily_result = self._try_tavily_extract(url)
        if tavily_result:
            # Truncate if too long
            content = tavily_result.get('content', '')
            if len(content) > max_length:
                content = content[:max_length] + "..."
                tavily_result['content'] = content
                tavily_result['length'] = len(content)
            
            logger.info("web_scrape_success", url=url, method="tavily", length=len(content))
            return ToolResult(
                success=True,
                result=tavily_result,
                metadata={"method": "tavily"}
            )

        # 2. Fallback to Gemini URL Context (handles JS-rendered pages)
        gemini_result = self._try_gemini_url_context(url, max_length)
        if gemini_result:
            logger.info(
                "web_scrape_success", url=url, method="gemini_url_context",
                length=len(gemini_result.get('content', '')),
            )
            return ToolResult(
                success=True,
                result=gemini_result,
                metadata={"method": "gemini_url_context"}
            )

        # 3. Final fallback to traditional scraping (BeautifulSoup)
        logger.info("web_scrape_fallback", url=url, method="traditional")
        return self._traditional_scrape(url, max_length)

    def _try_gemini_url_context(self, url: str, max_length: int) -> Dict[str, Any] | None:
        """Try to extract content using Gemini's URL Context tool.

        Handles JS-rendered pages that Tavily/BeautifulSoup can't process.
        Returns None if Gemini is not configured or fails.
        """
        try:
            if not config.GEMINI_API_KEY:
                return None

            from src.llm.gemini_client import get_gemini_client

            client = get_gemini_client()
            if client is None:
                return None

            extracted = client.url_context(
                url=url,
                instruction=(
                    "Extract and return the full main text content of this page. "
                    "Include the title. Exclude navigation, ads, and boilerplate."
                ),
            )

            content = extracted.get("content", "")
            if not content:
                logger.warning("gemini_url_context_empty", url=url)
                return None

            # Truncate if too long
            if len(content) > max_length:
                content = content[:max_length] + "..."

            return {
                "url": url,
                "title": "",  # Gemini URL context doesn't separate title
                "content": content,
                "description": "",
                "length": len(content),
            }

        except Exception as e:
            logger.warning("gemini_url_context_error", url=url, error=str(e))
            return None
    
    def _try_tavily_extract(self, url: str) -> Dict[str, Any] | None:
        """Try to extract content using Tavily API.
        
        Args:
            url: URL to extract
        
        Returns:
            Extracted content dict or None if failed
        """
        try:
            api_key = config.TAVILY_API_KEY
            if not api_key:
                logger.debug("tavily_api_key_not_found", url=url)
                return None
            
            # Use Tavily extract API
            response = requests.post(
                "https://api.tavily.com/extract",
                json={"urls": [url]},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                timeout=15
            )
            
            if response.status_code != 200:
                logger.warning("tavily_extract_failed", url=url, status=response.status_code)
                return None
            
            data = response.json()
            if not data or "results" not in data or not data["results"]:
                logger.warning("tavily_extract_empty", url=url)
                return None
            
            result = data["results"][0]
            raw_content = result.get("raw_content", "")
            
            if not raw_content:
                logger.warning("tavily_extract_no_content", url=url)
                return None
            
            return {
                "url": url,
                "title": result.get("title", ""),
                "content": raw_content,
                "description": "",  # Tavily doesn't provide meta description
                "length": len(raw_content)
            }
            
        except Exception as e:
            logger.warning("tavily_extract_error", url=url, error=str(e))
            return None
    
    def _traditional_scrape(self, url: str, max_length: int) -> ToolResult:
        """Traditional web scraping using requests and BeautifulSoup.
        
        Args:
            url: URL to scrape
            max_length: Maximum content length
        
        Returns:
            ToolResult with extracted content
        """
        try:
            # Fetch page
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Extract title
            title = soup.title.string if soup.title else ""
            
            # Extract main content
            # Try to find main content area
            main_content = (
                soup.find('main') or 
                soup.find('article') or 
                soup.find('div', class_='content') or
                soup.find('body')
            )
            
            # Get text
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
            
            # Clean up text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            # Truncate if too long
            if len(clean_text) > max_length:
                clean_text = clean_text[:max_length] + "..."
            
            # Extract metadata
            meta_description = ""
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag:
                meta_description = meta_tag.get('content', '')
            
            return ToolResult(
                success=True,
                result={
                    "url": url,
                    "title": title.strip(),
                    "content": clean_text,
                    "description": meta_description,
                    "length": len(clean_text)
                },
                metadata={
                    "method": "traditional",
                    "status_code": response.status_code,
                    "content_type": response.headers.get('content-type', '')
                }
            )
            
        except Exception as e:
            logger.error("web_scrape_failed", url=url, error=str(e))
            return ToolResult(success=False, error=f"Failed to scrape {url}: {str(e)}")
