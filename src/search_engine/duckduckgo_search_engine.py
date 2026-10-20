"""
src/search_engine/duckduckgo_search_engine.py

DuckDuckGo Search implementation using duckduckgo-search library
"""
import time
from typing import List, Dict, Optional
from duckduckgo_search import DDGS
from src.logger import get_formatted_logger
from src.search_engine.base_search_engine import BaseSearchEngine
from src.utils import get_region_code, normalize_language_code

logger = get_formatted_logger()


class DuckDuckGoSearchEngine(BaseSearchEngine):
    """DuckDuckGo Search implementation using duckduckgo-search library"""

    supports_date_range: bool = False      # chỉ timelimit thô (d/w/m/y)
    supports_country_lang: bool = True     # region param native (region=vn-vi)
    supports_domain_filter: bool = False   # dùng `site:` trong query string
    requires_api_key: bool = False
    
    def __init__(self, api_key: str = None):
        """
        Initialize DuckDuckGo Search Engine
        
        Note: DuckDuckGo doesn't require an API key, but we keep the parameter
        for consistency with the base class interface.
        
        Args:
            api_key: Not used for DuckDuckGo (optional for interface consistency)
        """
        # DuckDuckGo không cần API key
        super().__init__(api_key or "no_key_required")
        
    
    def _validate_config(self):
        """Validate DuckDuckGo-specific configuration"""
        pass
    def start_ts_to_timelimit(self,start_ts: int) -> str | None:
        """
        Map start_time (timestamp) → DuckDuckGo timelimit
        end_time = now()
        """
        now = int(time.time())
        delta = now - start_ts

        if delta <= 0:
            return None

        if delta <= 24 * 3600:
            return "d"
        elif delta <= 7 * 24 * 3600:
            return "w"
        elif delta <= 30 * 24 * 3600:
            return "m"
        else:
            return "y"
    def search(
        self,
        query: str,
        num_results: int = 10,
        lang: str = "all",
        start_date: str = None,
        end_date: str = None,
        safesearch: str = "moderate",   # was "strict" -> invalid; valid: on/moderate/off
        backend: str = "google,bing,brave,yandex,mojeek",
        max_retries: int = 3,
        **kwargs
    ) -> List[Dict]:
        """
        Search using DuckDuckGo
        
        Args:
            query: Search query
            num_results: Number of results to return
            lang: Language filter (not fully supported by DDG)
            start_date: Start date (not supported by DDG, use timelimit instead)
            end_date: End date (not supported by DDG, use timelimit instead)
            safesearch: Safe search level ("off", "moderate", "strict")
            timelimit: Time limit filter ("d", "w", "m", "y")
            backend: Backend to use
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of search results
        """
        region = "wt-wt"
        if lang != "all":
            country_code = get_region_code(lang).lower()
            language_code = normalize_language_code(lang).lower()
            region = f"{country_code}-{language_code}"
        logger.info(f"[DuckDuckGo] Searching for: {query} (results: {num_results}, region: {region})")
        results = []
        _SAFESEARCH_MAP = {"strict": "on", "on": "on", "moderate": "moderate", "off": "off"}
        safesearch = _SAFESEARCH_MAP.get(str(safesearch).lower(), "moderate")
        for attempt in range(max_retries):
            try:
                # DuckDuckGo text search
                with DDGS() as ddgs:
                    ddg_results = ddgs.text(
                        query=query,
                        region=region,
                        safesearch=safesearch,
                        timelimit=self.start_ts_to_timelimit(int(start_date)) if start_date else None,
                        backend=backend,
                        max_results=num_results
                    )
                    
                    # Convert to standardized format
                    for item in ddg_results:
                        results.append({
                            'title': item.get('title', ''),
                            'link': item.get('href', item.get('link', '')),
                            'snippet': item.get('body', item.get('snippet', '')),
                            'displayLink': self._extract_domain(item.get('href', '')),
                        })
                    
                    logger.info(f"[DuckDuckGo] Found {len(results)} results")
                return results[:num_results]
                
            except Exception as e:
                err_msg = str(e)
                logger.error(f"[DuckDuckGo] Error on attempt {attempt + 1}: {e}")

                if "encoding declaration" in err_msg or "wikipedia.org" in err_msg:
                    # known-bad backend/parser issue: drop the problematic engine
                    # from the list instead of retrying identically
                    if "google" not in backend:
                        backend = "google," + backend
                    logger.warning(f"[DuckDuckGo] Adjusting backend to: {backend}")

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    return results if results else []
        
        return results
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