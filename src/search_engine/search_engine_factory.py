"""
src/search_engine/search_engine_factory.py

Factory + rotation layer cho search engines.

Thiết kế rotation:
  - SearchEngineFactory.build_chain(): build dict engines từ SEARCH_ENGINE_CHAIN
    trong config, chỉ GIỮ engine có API key được cấu hình (trừ DDG không cần key).
  - MultiSearchEngine:
      * search_with_topup(): thử engine theo order, nếu kết quả chưa đủ num_results
        thì "top-up" từ engine kế (dedup URL) — dùng cho nhu cầu "chưa đủ limit".
      * search_fallback(): trả kết quả engine thành công đầu tiên.
      * Circuit breaker: engine nào báo SearchQuotaExceededError / SearchAuthError
        sẽ bị DISABLE cho cả run (không thử lại từng lần search), chờ reset tháng
        hoặc gọi reset_circuit_breaker().
      * Capability promotion: tự sắp xếp order theo feature yêu cầu
        (date range → ưu tiên Exa; country/lang → ưu tiên DDG/Gemini; ...).
  - SearchEngineClient: wrapper tiện dùng cho search_tool các platform,
    tự build chain từ config theo tên platform.
"""
from typing import Dict, Optional, List, Set, Callable
from enum import Enum
import re
from src.logger import get_formatted_logger
from src.config import config
from src.search_engine.base_search_engine import BaseSearchEngine
from src.search_engine.exa_search_engine import ExaSearchEngine
from src.search_engine.gemini_search_engine import GeminiSearchEngine
from src.search_engine.tavily_search_engine import TavilySearchEngine
from src.search_engine.duckduckgo_search_engine import DuckDuckGoSearchEngine
from src.search_engine.errors import (
    SearchAuthError,
    SearchQuotaExceededError,
    SearchError,
)

logger = get_formatted_logger()

# Token `site:xxx` trong query string (Gemini/DDG không có include_domains native
# nên phải dính `site:` vào query; Exa/Tavily có native → sẽ được strip và truyền
# qua include_domains).
_SITE_RE = re.compile(r"site:\S+", re.IGNORECASE)


class SearchEngineType(Enum):
    """Enum cho các loại search engine đang được dùng"""
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    GEMINI = "gemini"
    EXA = "exa"


class SearchEngineFactory:
    """Factory class để tạo search engine instances"""

    # Registry của các search engine classes (không còn Google PSE / Serper)
    _engines: Dict[SearchEngineType, type] = {
        SearchEngineType.TAVILY: TavilySearchEngine,
        SearchEngineType.EXA: ExaSearchEngine,
        SearchEngineType.GEMINI: GeminiSearchEngine,
        SearchEngineType.DUCKDUCKGO: DuckDuckGoSearchEngine,
    }

    @classmethod
    def create_engine(
        cls,
        engine_type: SearchEngineType,
        api_key: str = None,
        **kwargs
    ) -> BaseSearchEngine:
        """
        Tạo search engine instance

        Args:
            engine_type: Loại search engine (GEMINI, TAVILY, EXA, DUCKDUCKGO)
            api_key: API key cho engine
            **kwargs: Additional configuration cho engine cụ thể

        Returns:
            Search engine instance

        Raises:
            ValueError: Nếu engine_type không hợp lệ
        """
        if engine_type not in cls._engines:
            raise ValueError(f"Unknown search engine type: {engine_type}")

        engine_class = cls._engines[engine_type]
        logger.info(f"Creating {engine_type.value} search engine")
        return engine_class(api_key=api_key)

    @classmethod
    def create_from_string(
        cls,
        engine_name: str,
        api_key: str = None,
        **kwargs
    ) -> BaseSearchEngine:
        """
        Tạo search engine từ string name

        Args:
            engine_name: Tên engine ("gemini", "tavily", "exa", "duckduckgo")
            api_key: API key
            **kwargs: Additional configuration

        Returns:
            Search engine instance
        """
        try:
            engine_type = SearchEngineType(engine_name.lower())
            return cls.create_engine(engine_type, api_key, **kwargs)
        except ValueError:
            logger.error(f"Invalid engine name: {engine_name}")
            raise

    @classmethod
    def get_available_engines(cls) -> list:
        """
        Lấy danh sách các engine có sẵn

        Returns:
            List of engine names
        """
        return [engine.value for engine in cls._engines.keys()]

    @classmethod
    def register_engine(
        cls,
        engine_type: SearchEngineType,
        engine_class: type
    ):
        """
        Đăng ký engine mới (để mở rộng trong tương lai)

        Args:
            engine_type: Engine type
            engine_class: Engine class (phải extend BaseSearchEngine)
        """
        if not issubclass(engine_class, BaseSearchEngine):
            raise ValueError("Engine class must extend BaseSearchEngine")

        cls._engines[engine_type] = engine_class
        logger.info(f"Registered new search engine: {engine_type.value}")

    @classmethod
    def build_chain(
        cls,
        chain_name: str = "default",
        preferred_order: list = None,
    ) -> Dict[str, BaseSearchEngine]:
        """
        Build dict engines theo chain trong config (hoặc preferred_order).

        Chỉ giữ những engine có API key được cấu hình hợp lệ.
        DuckDuckGo (không cần key) luôn được đảm bảo xuất hiện làm backup cuối.

        Args:
            chain_name: Tên chain trong config.SEARCH_ENGINE_CHAIN (default/x/telegram/...)
            preferred_order: Override order từng engine (ví dụ ["exa", "ddg"])

        Returns:
            Dict mapping engine name → instance (theo thứ tự ưu tiên)
        """
        chain = (preferred_order or
                 config.SEARCH_ENGINE_CHAIN.get(chain_name) or
                 config.SEARCH_ENGINE_CHAIN.get("default"))

        engines: Dict[str, BaseSearchEngine] = {}
        for name in chain:
            if name in engines:
                continue
            try:
                engine_type = SearchEngineType(name.lower())
            except ValueError:
                logger.warning(f"Unknown engine in chain: {name}")
                continue
            try:
                engine = cls.create_engine(engine_type)
                if engine.requires_api_key and not engine.is_configured():
                    logger.info(f"[{name}] Skipped: no valid API key")
                    continue
                engines[name] = engine
            except Exception as e:
                logger.warning(f"[{name}] Failed to init engine: {e}")
                continue

        # Backup cuối luôn có DDG (không cần key)
        if "duckduckgo" not in engines:
            try:
                engines["duckduckgo"] = cls.create_engine(SearchEngineType.DUCKDUCKGO)
            except Exception as e:
                logger.warning(f"[duckduckgo] Failed to init backup engine: {e}")

        logger.info(
            f"[chain:{chain_name}] Active engines: {list(engines.keys())}"
        )
        return engines


class MultiSearchEngine:
    """
    Wrapper để sử dụng nhiều search engines với:
      - preferred order + capability promotion
      - circuit breaker (disable engine hết quota cho cả run)
      - top-up strategy (gom kết quả tới khi đủ limit)
    """

    def __init__(self, engines: Dict[str, BaseSearchEngine]):
        """
        Initialize với dictionary của engines

        Args:
            engines: Dict mapping engine names to instances (đã theo thứ tự ưu tiên)
        """
        self.engines = engines
        self._disabled_engines: Set[str] = set()
        self._last_success_engine: Optional[str] = None

    # ── Circuit breaker ─────────────────────────────────────────────────
    def _disable(self, engine_name: str, reason: str = "quota exceeded"):
        if engine_name not in self._disabled_engines:
            self._disabled_engines.add(engine_name)
            logger.error(
                f"[{engine_name}] DISABLED for this run ({reason}). "
                f"Will retry on next run / after monthly reset."
            )

    def reset_circuit_breaker(self, engine_name: str = None):
        """
        Reset trạng thái disabled (gọi khi reset tháng / muốn thử lại).

        Args:
            engine_name: Chỉ reset 1 engine; None = reset tất cả
        """
        if engine_name:
            self._disabled_engines.discard(engine_name)
            logger.info(f"[{engine_name}] Circuit breaker reset")
        else:
            self._disabled_engines.clear()
            logger.info("All circuit breakers reset")

    @property
    def disabled_engines(self) -> List[str]:
        """Danh sách engine đang bị disable trong run này."""
        return list(self._disabled_engines)

    # ── Per-engine query adaptation ──────────────────────────────────────
    def _prepare(
        self,
        engine_name: str,
        query: str,
        kwargs: dict,
    ) -> tuple:
        """
        Điều chỉnh query/kwargs cho phù hợp năng lực từng engine.

        - Engine có supports_domain_filter (Exa/Tavily):
            strip `site:xxx` khỏi query string và truyền include_domains native.
        - Engine không có (Gemini/DDG):
            giữ `site:xxx` trong query, bỏ include_domains khỏi kwargs.
        """
        engine = self.engines[engine_name]
        kwargs = dict(kwargs)
        include = kwargs.pop("include_domains", None) or kwargs.pop("includeDomain", None)
        exclude = kwargs.pop("exclude_domains", None) or kwargs.pop("excludeDomain", None)

        if include or exclude:
            if engine.supports_domain_filter:
                if include:
                    query = _SITE_RE.sub("", query).strip()
                    kwargs["include_domains"] = include
                if exclude:
                    kwargs["exclude_domains"] = exclude
            else:
                # Đảm bảo site: tokens tồn tại trong query cho engine không native
                if include:
                    tokens = " ".join(f"site:{d}" for d in include)
                    query = f"{query} {tokens}".strip()

        return query, kwargs

    # ── Capability-aware ordering ───────────────────────────────────────
    @staticmethod
    def _feature_score(engine: BaseSearchEngine, kwargs: dict) -> int:
        """
        Tính điểm hỗ trợ feature cho engine dựa trên kwargs của query.

        Date range là ràng buộc mạnh nhất (chỉ Exa hỗ trợ từ-đến chính xác),
        nên trọng số cao hơn.
        """
        score = 0
        if kwargs.get("lang") and kwargs.get("lang") != "all":
            if engine.supports_country_lang:
                score += 1
        if kwargs.get("start_date") or kwargs.get("end_date"):
            if engine.supports_date_range:
                score += 2
        if kwargs.get("include_domains") or kwargs.get("exclude_domains"):
            if engine.supports_domain_filter:
                score += 1
        return score

    def _ordered_engine_names(
        self,
        preferred_order: list = None,
        **kwargs
    ) -> List[str]:
        """
        Trả về danh sách engine names theo thứ tự gọi:
          1. preferred_order? hay thứ tự engines gốc
          2. Bỏ engine đang bị disable (circuit breaker)
          3. Sắp xếp lại theo feature_score (capability promotion, stable)
        """
        if preferred_order:
            names = [n for n in preferred_order if n in self.engines]
        else:
            names = list(self.engines.keys())

        names = [n for n in names if n not in self._disabled_engines]

        names.sort(
            key=lambda n: self._feature_score(self.engines[n], kwargs),
            reverse=True,
        )
        return names

    # ── Search single engine (circuit-aware) ────────────────────────────
    def search(
        self,
        query: str,
        engine_name: str = None,
        **kwargs
    ) -> list:
        """
        Search sử dụng một engine cụ thể hoặc engine đầu tiên khả dụng.

        Args:
            query: Search query
            engine_name: Tên engine cụ thể (optional)
            **kwargs: Search parameters

        Returns:
            Search results
        """
        if engine_name:
            if engine_name not in self.engines:
                raise ValueError(f"Engine {engine_name} not found")
            if engine_name in self._disabled_engines:
                raise SearchError(f"Engine {engine_name} is disabled (quota exceeded)")
            q, kw = self._prepare(engine_name, query, kwargs)
            return self.engines[engine_name].search(q, **kw)
        else:
            names = self._ordered_engine_names(**kwargs)
            if not names:
                return []
            q, kw = self._prepare(names[0], query, kwargs)
            return self.engines[names[0]].search(q, **kw)

    # ── Search tất cả engines (gom kết quả) ─────────────────────────────
    def search_all(
        self,
        query: str,
        preferred_order: list = None,
        **kwargs
    ) -> Dict[str, list]:
        """
        Search với tất cả engines và trả về kết quả từ mỗi engine.

        Args:
            query: Search query
            preferred_order: List of engine names in preferred order
            **kwargs: Search parameters

        Returns:
            Dict mapping engine names to their results
        """
        results = {}
        for name in self._ordered_engine_names(preferred_order, **kwargs):
            engine = self.engines[name]
            try:
                q, kw = self._prepare(name, query, kwargs)
                results[name] = engine.search(q, **kw)
                logger.info(f"[{name}] returned {len(results[name])} results")
            except SearchQuotaExceededError:
                self._disable(name)
                results[name] = []
            except SearchAuthError:
                self._disable(name, reason="auth failed")
                results[name] = []
            except Exception as e:
                logger.error(f"Error searching with {name}: {e}")
                results[name] = []
        return results

    # ── Fallback: engine thành công đầu tiên ─────────────────────────────
    def search_fallback(
        self,
        query: str,
        preferred_order: list = None,
        **kwargs
    ) -> list:
        """
        Search với fallback mechanism - thử engines theo thứ tự
        (kèm capability promotion + circuit breaker).

        Args:
            query: Search query
            preferred_order: List of engine names in preferred order
            **kwargs: Search parameters

        Returns:
            Results from first successful engine
        """
        for engine_name in self._ordered_engine_names(preferred_order, **kwargs):
            engine = self.engines[engine_name]
            try:
                q, kw = self._prepare(engine_name, query, kwargs)
                results = engine.search(q, **kw)
                if results:
                    self._last_success_engine = engine_name
                    logger.info(f"Successfully got results from {engine_name}")
                    return results
            except SearchQuotaExceededError:
                self._disable(engine_name)
            except SearchAuthError:
                self._disable(engine_name, reason="auth failed")
            except Exception as e:
                logger.warning(f"Failed to search with {engine_name}: {e}")
                continue

        logger.error("All search engines failed")
        return []

    # ── Top-up strategy: gom tới khi đủ limit ────────────────────────────
    @staticmethod
    def _dedup_key(url: str) -> str:
        """Normalize URL để dedup (bỏ trailing slash, lower)."""
        key = (url or "").strip().rstrip("/").lower()
        if not key:
            key = url
        return key

    def search_with_topup(
        self,
        query: str,
        num_results: int = 10,
        preferred_order: list = None,
        **kwargs
    ) -> List[dict]:
        """
        Search theo preferred order; nếu engine đầu chưa đủ num_results thì
        gom thêm ("top-up") từ các engine kế tiếp, dedup theo URL.

        Engine hết quota → disable (circuit breaker) và bỏ qua.

        Args:
            query: Search query
            num_results: Tổng số kết quả tối đa cần gom
            preferred_order: List of engine names in preferred order
            **kwargs: Search parameters

        Returns:
            List of (deduplicated) results tối đa num_results
        """
        collected: List[dict] = []
        seen: Set[str] = set()
        order = self._ordered_engine_names(preferred_order, **kwargs)

        if not order:
            logger.error("[topup] No search engines available")
            return []

        logger.info(f"[topup] Query='{query}' need={num_results} order={order}")

        for engine_name in order:
            if len(collected) >= num_results:
                break

            engine = self.engines[engine_name]
            needed = num_results - len(collected)
            # Lấy dư ~3x để bù việc lọc trùng giữa các engine
            fetch = min(max(needed * 3, num_results), 50)

            try:
                q, kw = self._prepare(engine_name, query, kwargs)
                raw_results = engine.search(
                    q, num_results=fetch, **kw
                ) or []
            except SearchQuotaExceededError:
                self._disable(engine_name)
                continue
            except SearchAuthError:
                self._disable(engine_name, reason="auth failed")
                continue
            except Exception as e:
                logger.warning(f"[topup] {engine_name} failed: {e}")
                continue

            added = 0
            for r in raw_results:
                if len(collected) >= num_results:
                    break
                url = r.get("link", "") or r.get("url", "")
                key = self._dedup_key(url)
                if not key or key in seen:
                    continue
                seen.add(key)
                r.setdefault("_engine", engine_name)
                collected.append(r)
                added += 1

            if raw_results:
                self._last_success_engine = engine_name

            logger.info(
                f"[topup] {engine_name}: +{added} new "
                f"(total {len(collected)}/{num_results})"
            )
            if added == 0:
                # Engine này không đóng góp gì (hết kết quả mới) → thử engine kế
                continue

        logger.info(f"[topup] Final: {len(collected)}/{num_results} results")
        return collected[:num_results]


class SearchEngineClient:
    """
    Client tiện dùng cho search_tool các platform.

    Tự động:
      - build chain engines từ config theo tên platform (chain_name)
      - xoay tua + circuit breaker + top-up qua MultiSearchEngine

    Usage:
        client = SearchEngineClient(chain_name="x")        # hoặc "telegram"
        results = client.search('site:x.com "bitcoin"', num_results=20)
    """

    def __init__(
        self,
        chain_name: str = "default",
        preferred_order: list = None,
        **engine_kwargs
    ):
        """
        Init SearchEngineClient.

        Args:
            chain_name: Tên chain trong config.SEARCH_ENGINE_CHAIN
                        (default / x / telegram / ...)
            preferred_order: Override order engines (optional)
        """
        engines = SearchEngineFactory.build_chain(
            chain_name=chain_name,
            preferred_order=preferred_order,
        )
        self.multi = MultiSearchEngine(engines)
        self.name = chain_name

    def search(
        self,
        query: str,
        num_results: int = 10,
        **kwargs
    ) -> List[dict]:
        """
        Search với top-up strategy (gom kết quả tới khi đủ num_results).

        Args:
            query: Search query
            num_results: Tổng kết quả mong muốn
            **kwargs: start_date/end_date/lang/include_domains/exclude_domains...

        Returns:
            List of deduplicated results
        """
        return self.multi.search_with_topup(
            query,
            num_results=num_results,
            **kwargs,
        )

    def search_fallback(
        self,
        query: str,
        **kwargs
    ) -> list:
        """Search trả về kết quả engine thành công đầu tiên."""
        return self.multi.search_fallback(query, **kwargs)

    @property
    def available_engines(self) -> List[str]:
        return list(self.multi.engines.keys())

    @property
    def disabled_engines(self) -> List[str]:
        return list(self.multi.disabled_engines)

    def reset(self):
        """Reset circuit breaker (gọi khi reset tháng / muốn thử lại)."""
        self.multi.reset_circuit_breaker()

    def __repr__(self):
        return (
            f"<SearchEngineClient chain={self.name} "
            f"engines={self.available_engines} disabled={self.disabled_engines}>"
        )