"""
src/search_engine/exa_search_engine.py

Exa AI Search API implementation (https://exa.ai).

Mạnh nhất về:
  - startPublishedDate / endPublishedDate → lọc khoảng thời gian từ-đến chính xác
  - includeDomains / excludeDomains native (được truyền thẳng từ search_tools)
Kém hơn về country/language native → SearchEngineClient sẽ ưu tiên Exa
khi query có date range, và hạ xuống khi cần country/language.

Error mapping:
  401/403 → SearchAuthError (key sai)
  402/429 → SearchQuotaExceededError (hết quota tháng — circuit breaker disable)
  khác    → SearchError (bỏ qua engine lần này, thử lần sau)
"""
import time
import requests
from typing import List, Dict, Optional
from src.logger import get_formatted_logger
from src.config import EXA_CONFIG
from src.utils import format_timestamp
from src.search_engine.errors import (
    SearchAuthError,
    SearchQuotaExceededError,
    SearchError,
)
from src.search_engine.base_search_engine import BaseSearchEngine

logger = get_formatted_logger()


class ExaSearchEngine(BaseSearchEngine):
    """Exa AI Search API implementation"""

    supports_date_range: bool = True
    supports_country_lang: bool = False
    supports_domain_filter: bool = True
    requires_api_key: bool = True

    def __init__(self, api_key: str = None):
        """
        Initialize Exa Search Engine

        Args:
            api_key: Exa API key
        """
        self.base_url = "https://api.exa.ai/search"
        super().__init__(api_key or EXA_CONFIG.get('api_key'))
        self._validate_config()

    def _validate_config(self):
        """Validate Exa-specific configuration"""
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.warning("Exa API key not configured properly")

    def search(
        self,
        query: str,
        num_results: int = 10,
        lang: str = "all",
        start_date: str = None,
        end_date: str = None,
        search_type: str = "keyword",  # "keyword" | "neural" | "auto"
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
        include_text: List[str] = None,
        exclude_text: List[str] = None,
        category: str = None,
        timeout: int = 30,
        **kwargs
    ) -> List[Dict]:
        """
        Search using Exa API

        Args:
            query: Search query
            num_results: Number of results (max 10 for search API)
            lang: Language filter (Exa không hỗ trợ native → append vào query)
            start_date: Start date (epoch / ISO) → startPublishedDate
            end_date: End date → endPublishedDate
            search_type: "keyword" (chính xác từ khoá) | "neural" (ngữ nghĩa) | "auto"
            include_domains: Chỉ search trong các domain này
            exclude_domains: Loại trừ domain
            include_text: Text bắt buộc có trong result
            exclude_text: Text không được có trong result
            category: Category filter (web, news, paper, company, pdf, ...)
            timeout: Request timeout

        Returns:
            List of search results
        """
        if not self.is_configured():
            return self._demo_search(query)

        num_results = min(num_results, 10)

        payload = {
            "query": query,
            "numResults": num_results,
            "type": search_type,
        }

        # ── Time range filter (native, chính xác từ-đến) ────────────────────
        if start_date:
            payload["startPublishedDate"] = format_timestamp(start_date) or start_date
        if end_date:
            payload["endPublishedDate"] = format_timestamp(end_date) or end_date

        # ── Domain filters (native) ─────────────────────────────────────────
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains

        # ── Text filters ────────────────────────────────────────────────────
        if include_text:
            payload["includeText"] = include_text
        if exclude_text:
            payload["excludeText"] = exclude_text

        if category:
            payload["category"] = category

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        logger.info(
            f"[Exa] Searching for: {query} "
            f"(type: {search_type}, results: {num_results})"
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()

                data = response.json()

                results = []
                for item in data.get('results', []):
                    results.append({
                        'title': item.get('title', ''),
                        'link': item.get('url', ''),
                        'snippet': item.get('text', item.get('highlights', '')),
                        'displayLink': self._extract_domain(item.get('url', '')),
                        'publishedDate': item.get('publishedDate', ''),
                        'author': item.get('author', ''),
                        'score': item.get('score'),
                    })

                logger.info(f"[Exa] Found {len(results)} results")
                return results[:num_results]

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0

                # Hết quota tháng (402 payment required / quota) → disable
                if status == 402:
                    logger.error("[Exa] API quota exceeded (402)")
                    raise SearchQuotaExceededError(
                        f"[Exa] API quota exceeded: {e}"
                    ) from e

                if status in (401, 403):
                    logger.error("[Exa] Invalid API key")
                    raise SearchAuthError(f"[Exa] Invalid API key: {e}") from e

                # Rate limit → retry vài lần, nếu vẫn 429 → coi như quota
                if status == 429:
                    if attempt < max_retries - 1:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"[Exa] Rate limit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    raise SearchQuotaExceededError(
                        f"[Exa] Rate limit on final attempt: {e}"
                    ) from e

                logger.error(f"[Exa] HTTP Error: {e}")
                raise SearchError(f"[Exa] HTTP {status}: {e}") from e

            except requests.exceptions.RequestException as e:
                logger.error(f"[Exa] Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 ** attempt)
                else:
                    raise SearchError(f"[Exa] Request failed: {e}") from e

        return []

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return url