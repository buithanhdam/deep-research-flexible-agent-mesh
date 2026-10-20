"""
src/search_engine/brave_search_engine.py

Brave Search API implementation
"""
import time
import requests
from typing import List, Dict, Optional
from src.logger import get_formatted_logger
from src.config import BRAVE_CONFIG
from src.search_engine.errors import (
    SearchAuthError,
    SearchQuotaExceededError,
    SearchError,
)
from src.search_engine.base_search_engine import BaseSearchEngine

logger = get_formatted_logger()


class BraveSearchEngine(BaseSearchEngine):
    """Brave Search API implementation"""

    supports_date_range: bool = False      # chỉ freshness thô (d/w/m/y)
    supports_country_lang: bool = True     # country + search_lang native params
    supports_domain_filter: bool = False   # dùng `site:` trong query string
    requires_api_key: bool = True
    
    def __init__(self, api_key: str = None):
        """
        Initialize Brave Search Engine
        
        Args:
            api_key: Brave Search API key
        """
        self.base_url = "https://api.search.brave.com/res/v1"
        super().__init__(api_key or BRAVE_CONFIG.get('api_key'))
        self._validate_config()
    
    def _validate_config(self):
        """Validate Brave-specific configuration"""
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.warning("Brave API key not configured properly")
    
    def search(
        self, 
        query: str, 
        num_results: int = 10,
        lang: str = "all",
        start_date: str = None,
        end_date: str = None,
        country: str = "US",  # Country code (US, GB, FR, etc.)
        search_lang: str = "en",  # Search language
        safesearch: str = "moderate",  # off, moderate, strict
        freshness: str = None,  # pd (past day), pw (past week), pm (past month), py (past year)
        text_decorations: bool = True,
        spellcheck: bool = True,
        offset: int = 0,  # Offset for pagination (0-9 for first page, 10-19 for second, etc.)
        timeout: int = 30,
        **kwargs
    ) -> List[Dict]:
        """
        Search using Brave Search API
        
        Args:
            query: Search query
            num_results: Number of results to return (max 20 per request)
            lang: Language filter (used as search_lang if not "all")
            start_date: Start date (not directly supported, use freshness instead)
            end_date: End date (not directly supported, use freshness instead)
            country: Country code for search results
            search_lang: Language for search
            safesearch: Safe search level ("off", "moderate", "strict")
            freshness: Freshness filter ("pd", "pw", "pm", "py")
            text_decorations: Enable text decorations (bold, highlighting)
            spellcheck: Enable spellcheck
            offset: Offset for pagination
            timeout: Request timeout
            
        Returns:
            List of search results
        """
        if not self.is_configured():
            return self._demo_search(query)
        
        # Brave limits count to 20 per request
        count_per_request = min(num_results, 20)
        
        # Override search_lang if lang is specified
        if lang != "all":
            search_lang = lang
        
        params = {
            'q': query,
            'count': count_per_request,
            'country': country,
            'search_lang': search_lang,
            'safesearch': safesearch,
            'text_decorations': text_decorations,
            'spellcheck': spellcheck,
            'offset': offset,
        }
        
        # Add freshness filter if specified
        if freshness:
            params['freshness'] = freshness
        
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': self.api_key,
        }
        
        logger.info(f"[Brave] Searching for: {query} (count: {count_per_request}, offset: {offset})")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.base_url}/web/search",
                    params=params,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()
                
                data = response.json()
                
                results = []
                
                # Process web results
                if 'web' in data and 'results' in data['web']:
                    for item in data['web']['results']:
                        results.append({
                            'title': item.get('title', ''),
                            'link': item.get('url', ''),
                            'snippet': item.get('description', ''),
                            'displayLink': self._extract_domain(item.get('url', '')),
                            'age': item.get('age', ''),  # Extra field from Brave
                            'language': item.get('language', ''),  # Extra field
                        })
                
                # Also process featured snippet if available
                if 'infobox' in data and results:
                    infobox = data['infobox']
                    # Add as first result if relevant
                    if infobox.get('title') and infobox.get('url'):
                        results.insert(0, {
                            'title': infobox.get('title', ''),
                            'link': infobox.get('url', ''),
                            'snippet': infobox.get('description', ''),
                            'displayLink': self._extract_domain(infobox.get('url', '')),
                        })
                
                logger.info(f"[Brave] Found {len(results)} results")
                return results[:num_results]
                
            except requests.exceptions.HTTPError as e:
                logger.error(f"[Brave] HTTP Error: {e}")
                
                # Handle unauthorized (401)
                if e.response.status_code == 401:
                    logger.error("[Brave] Invalid API key")
                    raise SearchAuthError(f"[Brave] Invalid API key") from e
                
                # Handle quota exceeded (402) → disable engine cho cả run
                elif e.response.status_code == 402:
                    logger.error("[Brave] API quota exceeded")
                    raise SearchQuotaExceededError(f"[Brave] API quota exceeded") from e
                
                # Handle rate limiting (429)
                elif e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Get retry-after header if available
                        retry_after = int(e.response.headers.get('Retry-After', 60))
                        logger.warning(f"[Brave] Rate limit exceeded. Waiting {retry_after}s...")
                        time.sleep(retry_after)
                        continue
                    else:
                        logger.error("[Brave] Rate limit exceeded on final attempt")
                        raise SearchQuotaExceededError(f"[Brave] Rate limit on final attempt") from e
                
                else:
                    raise SearchError(f"[Brave] HTTP {e.response.status_code}: {e}") from e
            
            except requests.exceptions.RequestException as e:
                logger.error(f"[Brave] Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 ** attempt)
                else:
                    raise SearchError(f"[Brave] Request failed: {e}") from e
        
        return []
    
    def search_with_pagination(
        self,
        query: str,
        total_results: int = 50,
        **kwargs
    ) -> List[Dict]:
        """
        Search with automatic pagination
        
        Args:
            query: Search query
            total_results: Total number of results needed
            **kwargs: Additional search parameters
            
        Returns:
            List of all search results
        """
        all_results = []
        offset = 0
        
        while len(all_results) < total_results:
            remaining = total_results - len(all_results)
            count = min(remaining, 20)  # Brave max is 20 per request
            
            results = self.search(
                query=query,
                num_results=count,
                offset=offset,
                **kwargs
            )
            
            if not results:
                logger.info(f"[Brave] No more results at offset {offset}")
                break
            
            all_results.extend(results)
            offset += 20  # Increment offset for next page
            
            # Add delay between requests to respect rate limits
            if len(all_results) < total_results:
                time.sleep(1)
        
        logger.info(f"[Brave] Total results collected: {len(all_results)}")
        return all_results[:total_results]
    
    def search_news(
        self,
        query: str,
        num_results: int = 10,
        country: str = "US",
        search_lang: str = "en",
        freshness: str = None,
        offset: int = 0,
        timeout: int = 30,
        **kwargs
    ) -> List[Dict]:
        """
        Search news using Brave Search API
        
        Args:
            query: Search query
            num_results: Number of results
            country: Country code
            search_lang: Search language
            freshness: Freshness filter
            offset: Offset for pagination
            timeout: Request timeout
            
        Returns:
            List of news results
        """
        if not self.is_configured():
            logger.warning("Brave API key not configured.")
            return []
        
        count_per_request = min(num_results, 20)
        
        params = {
            'q': query,
            'count': count_per_request,
            'country': country,
            'search_lang': search_lang,
            'offset': offset,
        }
        
        if freshness:
            params['freshness'] = freshness
        
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': self.api_key,
        }
        
        logger.info(f"[Brave News] Searching for: {query}")
        
        try:
            response = requests.get(
                f"{self.base_url}/news/search",
                params=params,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'results' in data:
                for item in data['results']:
                    results.append({
                        'title': item.get('title', ''),
                        'link': item.get('url', ''),
                        'snippet': item.get('description', ''),
                        'displayLink': item.get('source', self._extract_domain(item.get('url', ''))),
                        'age': item.get('age', ''),
                        'thumbnail': item.get('thumbnail', {}).get('src', '') if item.get('thumbnail') else '',
                    })
            
            logger.info(f"[Brave News] Found {len(results)} results")
            return results[:num_results]
            
        except Exception as e:
            logger.error(f"[Brave News] Error: {e}")
            return []
    
    def search_images(
        self,
        query: str,
        num_results: int = 10,
        country: str = "US",
        search_lang: str = "en",
        safesearch: str = "moderate",
        spellcheck: bool = True,
        offset: int = 0,
        timeout: int = 30,
        **kwargs
    ) -> List[Dict]:
        """
        Search images using Brave Search API
        
        Note: Image search may require a higher tier API subscription
        
        Args:
            query: Search query
            num_results: Number of results
            country: Country code
            search_lang: Search language
            safesearch: Safe search level
            spellcheck: Enable spellcheck
            offset: Offset for pagination
            timeout: Request timeout
            
        Returns:
            List of image results
        """
        if not self.is_configured():
            logger.warning("Brave API key not configured.")
            return []
        
        count_per_request = min(num_results, 20)
        
        params = {
            'q': query,
            'count': count_per_request,
            'country': country,
            'search_lang': search_lang,
            'safesearch': safesearch,
            'spellcheck': spellcheck,
            'offset': offset,
        }
        
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': self.api_key,
        }
        
        logger.info(f"[Brave Images] Searching for: {query}")
        
        try:
            response = requests.get(
                f"{self.base_url}/images/search",
                params=params,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'results' in data:
                for item in data['results']:
                    results.append({
                        'title': item.get('title', ''),
                        'link': item.get('url', ''),
                        'snippet': item.get('title', ''),
                        'displayLink': item.get('source', ''),
                        'thumbnail': item.get('thumbnail', {}).get('src', '') if item.get('thumbnail') else '',
                        'properties': item.get('properties', {}),
                    })
            
            logger.info(f"[Brave Images] Found {len(results)} results")
            return results[:num_results]
            
        except Exception as e:
            logger.error(f"[Brave Images] Error: {e}")
            return []
    
    def get_suggestions(
        self,
        query: str,
        country: str = "US",
        search_lang: str = "en",
        timeout: int = 30
    ) -> List[str]:
        """
        Get search suggestions for a query
        
        Args:
            query: Partial search query
            country: Country code
            search_lang: Search language
            timeout: Request timeout
            
        Returns:
            List of suggestions
        """
        if not self.is_configured():
            return []
        
        params = {
            'q': query,
            'country': country,
            'search_lang': search_lang,
        }
        
        headers = {
            'Accept': 'application/json',
            'X-Subscription-Token': self.api_key,
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/suggest/search",
                params=params,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'results' in data:
                return [item.get('query', '') for item in data['results']]
            
            return []
            
        except Exception as e:
            logger.error(f"[Brave] Error getting suggestions: {e}")
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