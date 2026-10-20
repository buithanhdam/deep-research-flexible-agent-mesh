"""
src/search_engine/errors.py

Các exception dùng chung cho search engines.

Logic rotation dựa trên phân biệt lỗi:
  - SearchQuotaExceededError → engine hết quota tháng (402/429 vĩnh viễn).
    SearchEngineClient sẽ circuit-breaker: disable engine này cho CẢ RUN,
    không thử lại từng lần search nữa (chờ reset tháng).
  - SearchAuthError → key sai/thiếu (401), disable luôn.
  - SearchError → lỗi khác (network, server...) → chỉ bỏ qua engine này lần đó,
    vẫn thử ở lần search sau.
"""


class SearchError(Exception):
    """Base error cho mọi lỗi search engine."""
    pass


class SearchQuotaExceededError(SearchError):
    """
    Hết quota / rate-limit vĩnh viễn của engine (HP: 402/429 sau retry).
    Circuit breaker sẽ disable engine cho cả run.
    """
    pass


class SearchAuthError(SearchError):
    """API key sai / thiếu (401/403 hay demo-mode)."""
    pass


class SearchEmptyResultsError(SearchError):
    """Engine trả rỗng — không phải lỗi, chỉ để phân biệt khi cần."""
    pass