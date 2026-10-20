"""
src/search_engine/tavily_search_engine.py

Tavily Search API implementation
"""
import datetime
import time
import requests
from typing import List, Dict, Optional
from src.logger import get_formatted_logger
from src.config import TAVILY_CONFIG
from src.search_engine.errors import (
    SearchAuthError,
    SearchQuotaExceededError,
    SearchError,
)
from src.search_engine.base_search_engine import BaseSearchEngine

logger = get_formatted_logger()


class TavilySearchEngine(BaseSearchEngine):
    """Tavily Search API implementation"""

    supports_date_range: bool = False      # chỉ khi topic=news + days (không chính xác từ-đến)
    supports_country_lang: bool = False
    supports_domain_filter: bool = True    # include_domains/exclude_domains native
    requires_api_key: bool = True

    def __init__(self, api_key: str = None):
        """
        Initialize Tavily Search Engine
        
        Args:
            api_key: Tavily API key
        """
        self.base_url = "https://api.tavily.com/search"
        super().__init__(api_key or TAVILY_CONFIG.get('api_key'))
        self._validate_config()
    @staticmethod
    def _normalize_date(value) -> Optional[str]:
        """
        Normalize a date value into Tavily's required 'YYYY-MM-DD' string format.
        Accepts: datetime/date objects, unix timestamps (int/float or numeric
        string), or already-formatted/ISO date strings.
        Returns None (instead of raising) if the value can't be safely converted.
        """
        if value is None:
            return None

        try:
            if isinstance(value, (datetime.datetime, datetime.date)):
                return value.strftime("%Y-%m-%d")

            if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
                ts = float(value)
                # Sanity range: 1970-01-01 .. 2100-01-01 (in seconds).
                # Anything outside this is almost certainly a bad/garbage timestamp,
                # or one given in milliseconds instead of seconds.
                if ts > 4102444800:       # looks like milliseconds, not seconds
                    ts = ts / 1000.0
                if not (0 <= ts <= 4102444800):
                    logger.warning(f"[Tavily] Timestamp out of safe range, ignoring date filter: {value}")
                    return None
                return datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%Y-%m-%d")

            if isinstance(value, str):
                return value.strip()[:10]

            return str(value)[:10]

        except (OSError, OverflowError, ValueError) as e:
            logger.warning(f"[Tavily] Failed to normalize date value {value!r}: {e}")
            return None
    def _validate_config(self):
        """Validate Tavily-specific configuration"""
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.warning("Tavily API key not configured properly")
    
    def search(
        self, 
        query: str, 
        num_results: int = 10,
        lang: str = "all",
        start_date: str = None,
        end_date: str = None,
        search_depth: str = "basic",  # "basic" or "advanced"
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
        timeout: int = 30,
        **kwargs
    ) -> List[Dict]:
        """
        Search using Tavily API
        
        Args:
            query: Search query
            num_results: Number of results to return (max 20)
            lang: Language filter (not fully supported by Tavily)
            start_date: Start date (not supported by Tavily)
            end_date: End date (not supported by Tavily)
            search_depth: "basic" (faster) or "advanced" (more thorough)
            include_domains: List of domains to include
            exclude_domains: List of domains to exclude
            timeout: Request timeout
            
        Returns:
            List of search results
        """
        if not self.is_configured():
            return self._demo_search(query)
        
        # Tavily giới hạn max_results = 20
        num_results = min(num_results, 20)
        
        payload = {
            "query": query,
            "max_results": num_results,
            "search_depth": search_depth,
            "include_answer": False,  # We only need search results
            "include_raw_content": False,
        }
        
        # Add domain filters if provided (native param)
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        
        # Time range: Tavily chỉ hỗ trợ chính xác khi topic=news
        # general topic có thể dùng days (thô) — chỉ thêm nếu caller yêu cầu
        if start_date or end_date:
            norm_start = self._normalize_date(start_date)
            norm_end = self._normalize_date(end_date)
            if norm_start or norm_end:
                payload["topic"] = "news"
                if norm_start:
                    payload["start_date"] = norm_start
                if norm_end:
                    payload["end_date"] = norm_end
        
        logger.info(f"[Tavily] Searching for: {query} (depth: {search_depth})")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    json=payload,
                    timeout=timeout,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                if 'results' in data:
                    results = []
                    for item in data['results']:
                        results.append({
                            'title': item.get('title', ''),
                            'link': item.get('url', ''),
                            'snippet': item.get('content', ''),
                            'displayLink': self._extract_domain(item.get('url', '')),
                        })
                    
                    logger.info(f"[Tavily] Found {len(results)} results")
                    return results
                else:
                    logger.warning(f"[Tavily] No results found")
                    return []
                
            except requests.exceptions.HTTPError as e:
                body = ""
                try:
                    body = e.response.text
                except Exception:
                    pass
                logger.error(f"[Tavily] HTTP Error: {e} | body: {body}")
                status = e.response.status_code if e.response is not None else 0
                if status in (401, 403):
                    raise SearchAuthError(f"[Tavily] Invalid API key") from e
                if status == 429:
                    if attempt < max_retries - 1:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"[Tavily] Rate limit exceeded. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("[Tavily] Rate limit exceeded on final attempt")
                        raise SearchQuotaExceededError("[Tavily] Rate limit on final attempt") from e
                if status == 402:
                    raise SearchQuotaExceededError("[Tavily] API quota exceeded") from e
                raise SearchError(f"[Tavily] HTTP {status}: {e}") from e
            
            except requests.exceptions.RequestException as e:
                logger.error(f"[Tavily] Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 ** attempt)
                else:
                    raise SearchError(f"[Tavily] Request failed: {e}") from e
        
        return []
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL
        
        Args:
            url: Full URL
            
        Returns:
            Domain name
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return url