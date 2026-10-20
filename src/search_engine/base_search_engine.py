"""
src/search_engine/base_search_engine.py

Base class cho tất cả search engines
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from src.logger import get_formatted_logger

logger = get_formatted_logger()


class BaseSearchEngine(ABC):
    """Abstract base class cho search engines"""
    
    # ── Capability flags ────────────────────────────────────────────────────
    # SearchEngineClient dùng các flag này để tự sắp xếp preferred_order
    # sao cho engine hỗ trợ feature được yêu cầu chạy trước.
    supports_date_range: bool = False      # lọc khoảng thời gian từ-đến chính xác
    supports_country_lang: bool = False    # lọc country/language native (param)
    supports_domain_filter: bool = False   # include_domains/exclude_domains native
    requires_api_key: bool = True
    
    def __init__(self, api_key: str = None, **kwargs):
        """
        Initialize search engine
        
        Args:
            api_key: API key cho search engine
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """Validate configuration - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def search(
        self, 
        query: str, 
        num_results: int = 10,
        lang: str = "all",
        start_date: str = None,
        end_date: str = None,
        **kwargs
    ) -> List[Dict]:
        """
        Perform search operation
        
        Args:
            query: Search query string
            num_results: Number of results to return
            lang: Language filter
            start_date: Start date for date range filter
            end_date: End date for date range filter
            **kwargs: Additional search parameters
            
        Returns:
            List of search results with standardized format:
            [
                {
                    'title': str,
                    'link': str,
                    'snippet': str,
                    'displayLink': str,
                },
                ...
            ]
        """
        pass
    
    def _normalize_results(self, raw_results: List[Dict]) -> List[Dict]:
        """
        Normalize results to standardized format
        
        Args:
            raw_results: Raw results from search engine
            
        Returns:
            Normalized results
        """
        normalized = []
        for result in raw_results:
            normalized.append({
                'title': result.get('title', ''),
                'link': result.get('link', result.get('url', '')),
                'snippet': result.get('snippet', result.get('description', '')),
                'displayLink': result.get('displayLink', result.get('domain', '')),
            })
        return normalized
    
    def _demo_search(self, query: str) -> List[Dict]:
        """
        Raise SearchAuthError khi API key chưa cấu hình — để SearchEngineClient
        hiểu engine này không khả dụng và bỏ qua (không trả dữ liệu giả gây nhiễu).
        """
        logger.warning(f"{self.__class__.__name__}: Running in demo mode")
        from src.search_engine.errors import SearchAuthError
        raise SearchAuthError(
            f"{self.__class__.__name__}: API key not configured"
        )

    def is_configured(self) -> bool:
        """Engine có key hợp lệ không (dùng để prune trước khi gọi)."""
        return bool(self.api_key) and self.api_key != "YOUR_API_KEY_HERE"
    
    def get_engine_name(self) -> str:
        """Return the name of the search engine"""
        return self.__class__.__name__.replace('SearchEngine', '')