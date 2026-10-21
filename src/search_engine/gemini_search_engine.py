"""
src/search_engine/gemini_search_engine.py

Gemini Search Grounding engine (Google Search via Gemini native tool).

Đặc điểm:
  - Gemini search Google *during inference* → trả synthesized answer + citations.
  - KHÔNG hỗ trợ native date-range / domain filter → SearchEngineClient sẽ
    hạ priority engine này khi query cần feature đó.
  - Dùng google-genai SDK (lazy import) + GEMINI_API_KEY từ config.

Error mapping:
  - Auth/Key sai   → SearchAuthError
  - Quota / 429    → SearchQuotaExceededError (circuit breaker disable)
  - Khác           → SearchError
"""
import time
from typing import List, Dict, Optional
from src.logger import get_formatted_logger
from src.config import config
from src.search_engine.errors import (
    SearchAuthError,
    SearchQuotaExceededError,
    SearchError,
)
from src.search_engine.base_search_engine import BaseSearchEngine

logger = get_formatted_logger()


class GeminiSearchEngine(BaseSearchEngine):
    """Gemini Search Grounding engine implementation"""

    supports_date_range: bool = False
    supports_country_lang: bool = False
    supports_domain_filter: bool = False
    requires_api_key: bool = True

    def __init__(self, api_key: str = None, model: Optional[str] = None):
        """
        Initialize Gemini Search Grounding Engine

        Args:
            api_key: Gemini API key (mặc định lấy từ config.GEMINI_API_KEY)
            model: Gemini model (mặc định lấy từ config.GEMINI_MODEL)
        """
        self.model = model or config.GEMINI_MODEL
        self._client = None
        super().__init__(api_key or config.GEMINI_API_KEY)
        self._validate_config()

    def _validate_config(self):
        """Validate Gemini-specific configuration"""
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.warning("Gemini API key not configured properly")

    def _get_client(self):
        """Lazy-load google-genai client (optional dependency)."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError as e:
                raise SearchError(
                    "google-genai SDK not installed. Run: pip install google-genai"
                ) from e
        return self._client

    def search(
        self,
        query: str,
        num_results: int = 10,
        lang: str = "all",
        start_date: str = None,
        end_date: str = None,
        timeout: int = 30,
        **kwargs
    ) -> List[Dict]:
        """
        Search using Gemini Search Grounding.

        Gemini trả về 1 synthesized answer + grounding citations.
        Ta convert citations thành list kết quả chuẩn (title/link/snippet).
        Nếu không có citations → trả answer như 1 result duy nhất.

        Args:
            query: Search query / question
            num_results: Max citations trả về
            lang: (không hỗ trợ native — bỏ qua)
            start_date / end_date: (không hỗ trợ native — bỏ qua)
            timeout: Request timeout (giây)

        Returns:
            List of search results (chuẩn BaseSearchEngine format)
        """
        if not self.is_configured():
            return self._demo_search(query)

        client = self._get_client()

        logger.info(f"[Gemini] Grounding search: {query}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                from google.genai import types

                response = client.models.generate_content(
                    model=self.model,
                    contents=query,
                    config=types.GenerateContentConfig(
                        tools=[
                            types.Tool(
                                google_search=types.GoogleSearch()
                            )
                        ],
                        temperature=0.2,
                    ),
                )

                # ── Extract grounding metadata ────────────────────────────
                results: List[Dict] = []
                seen_urls = set()
                candidate = response.candidates[0] if response.candidates else None
                grounding = getattr(candidate, "grounding_metadata", None) if candidate else None

                if grounding:
                    chunks = grounding.grounding_chunks or []
                    for chunk in chunks[:num_results]:
                        web = getattr(chunk, "web", None)
                        if not web:
                            continue
                        url = getattr(web, "uri", "") or ""
                        title = getattr(web, "title", None) or url
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            results.append({
                                'title': title,
                                'link': url,
                                'snippet': response.text or '',
                                'displayLink': self._extract_domain(url),
                                'source': 'gemini_grounding',
                            })

                # Không có citations → fallback dùng answer text như 1 result
                if not results and response.text:
                    results.append({
                        'title': f'[Gemini Grounding] {query}',
                        'link': '',
                        'snippet': response.text,
                        'displayLink': 'gemini.google.com',
                        'source': 'gemini_grounding',
                    })

                logger.info(f"[Gemini] Found {len(results)} grounded results")
                return results

            except Exception as e:
                err_str = str(e).lower()

                # Auth / key sai
                if "api key" in err_str or "permission" in err_str or "401" in err_str or "403" in err_str:
                    logger.error(f"[Gemini] Invalid API key: {e}")
                    raise SearchAuthError(f"[Gemini] Invalid API key: {e}") from e

                # Quota / rate limit
                if "quota" in err_str or "429" in err_str or "resource_exhausted" in err_str:
                    if attempt < max_retries - 1:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"[Gemini] Rate limit. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    logger.error("[Gemini] Quota exceeded on final attempt")
                    raise SearchQuotaExceededError(
                        f"[Gemini] Quota / rate limit exceeded: {e}"
                    ) from e

                logger.error(f"[Gemini] Search error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(3 ** attempt)
                else:
                    raise SearchError(f"[Gemini] Search failed: {e}") from e

        return []

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return url
