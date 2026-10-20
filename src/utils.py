"""Shared utility functions for search engines and tools.

Functions:
  - format_timestamp: normalize date values to ISO 8601 (for Exa publishedDate)
  - get_region_code: map language name/code to DuckDuckGo region country code
  - normalize_language_code: map language name/code to ISO 639-1 language code
"""

import datetime
from typing import Optional

# ── Language mapping ────────────────────────────────────────────────────
# key: language name (lowercase) hoặc ISO 639-1 code
# value: (region_country_code, language_code)
_LANGUAGE_MAP = {
    "english": ("US", "en"),
    "en": ("US", "en"),
    "vietnamese": ("VN", "vi"),
    "vi": ("VN", "vi"),
    "japanese": ("JP", "ja"),
    "ja": ("JP", "ja"),
    "korean": ("KR", "ko"),
    "ko": ("KR", "ko"),
    "chinese": ("CN", "zh"),
    "zh": ("CN", "zh"),
    "french": ("FR", "fr"),
    "fr": ("FR", "fr"),
    "german": ("DE", "de"),
    "de": ("DE", "de"),
    "spanish": ("ES", "es"),
    "es": ("ES", "es"),
    "russian": ("RU", "ru"),
    "ru": ("RU", "ru"),
    "italian": ("IT", "it"),
    "it": ("IT", "it"),
    "portuguese": ("BR", "pt"),
    "pt": ("BR", "pt"),
    "thai": ("TH", "th"),
    "th": ("TH", "th"),
}

DEFAULT_REGION = "US"
DEFAULT_LANGUAGE = "en"


def get_region_code(lang: str) -> str:
    """Map language name/code to DuckDuckGo region country code.

    Args:
        lang: Language name (e.g. "vietnamese") or ISO code (e.g. "vi")

    Returns:
        Two-letter uppercase country code (e.g. "VN"), default "US".
    """
    if not lang or str(lang).lower() in ("all", ""):
        return DEFAULT_REGION
    key = str(lang).lower().strip()
    if key in _LANGUAGE_MAP:
        return _LANGUAGE_MAP[key][0]
    # Fallback: nếu lang là ISO-3166 country code dạng 2 chữ cái (vd "vn", "jp")
    if len(key) == 2 and key.isalpha():
        return key.upper()
    return DEFAULT_REGION


def normalize_language_code(lang: str) -> str:
    """Map language name/code to ISO 639-1 language code.

    Args:
        lang: Language name (e.g. "vietnamese") or ISO code (e.g. "vi")

    Returns:
        Two-letter lowercase language code (e.g. "vi"), default "en".
    """
    if not lang or str(lang).lower() in ("all", ""):
        return DEFAULT_LANGUAGE
    key = str(lang).lower().strip()
    if key in _LANGUAGE_MAP:
        return _LANGUAGE_MAP[key][1]
    if len(key) == 2 and key.isalpha():
        return key.lower()
    return DEFAULT_LANGUAGE


def format_timestamp(value) -> Optional[str]:
    """Normalize a date value into Exa's ISO 8601 format (YYYY-MM-DDTHH:MM:SS.000Z).

    Accepts: datetime/date objects, unix timestamps (int/float or numeric
    string — seconds or milliseconds), ISO/ISO-date strings, or
    already-formatted ISO 8601 strings (returned unchanged).

    Returns None if the value can't be safely converted.
    """
    if value is None:
        return None

    try:
        # datetime / date objects
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%dT00:00:00.000Z")

        # Unix timestamps (seconds or milliseconds)
        if isinstance(value, (int, float)) or (
            isinstance(value, str) and value.strip().replace(".", "", 1).isdigit()
        ):
            ts = float(value)
            # Sanity range: 1970-01-01 .. 2100-01-01 (in seconds)
            if ts > 4102444800:  # looks like milliseconds
                ts = ts / 1000.0
            if not (0 <= ts <= 4102444800):
                return None
            return datetime.datetime.fromtimestamp(
                ts, datetime.UTC
            ).strftime("%Y-%m-%dT00:00:00.000Z")

        if isinstance(value, str):
            s = value.strip()
            # Already full ISO 8601 (has 'T' and time part) → pass through
            if "T" in s and len(s) >= 20:
                return s
            # ISO date "YYYY-MM-DD" → append midnight
            if len(s) == 10:
                return f"{s}T00:00:00.000Z"
            # Try parsing other common formats (e.g. "2024/01/15")
            parsed = datetime.datetime.fromisoformat(s.replace("/", "-"))
            return parsed.strftime("%Y-%m-%dT00:00:00.000Z")

    except (OSError, OverflowError, ValueError) as e:
        import logging
        logging.getLogger(__name__).warning(
            f"format_timestamp failed for value {value!r}: {e}"
        )

    return None
