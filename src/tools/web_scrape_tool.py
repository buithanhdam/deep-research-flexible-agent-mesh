"""Web scraping tool to extract content from URLs."""

from typing import Dict, Any
import requests
from bs4 import BeautifulSoup
from src.tools.base_tool import BaseTool, ToolResult
from src.logger import get_logger

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
        """Scrape webpage content.
        
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
                    "status_code": response.status_code,
                    "content_type": response.headers.get('content-type', '')
                }
            )
            
        except Exception as e:
            logger.error("web_scrape_failed", url=url, error=str(e))
            return ToolResult(success=False, error=f"Failed to scrape {url}: {str(e)}")
