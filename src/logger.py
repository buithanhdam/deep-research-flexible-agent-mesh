"""Logging configuration for the multi-agent system.

- Luôn ghi ra FILE (JSON, có rotate theo ngày) — phục vụ tra cứu/audit lâu dài.
- Console (stderr):
    dev  (APP_ENV=dev)  -> màu, dễ đọc, cho người
    prod (APP_ENV=prod) -> JSON, cho máy/n8n đọc (giữ đúng thiết kế cũ: stdout luôn
                            sạch để n8n parse @@JSON_START@@, log debug nằm ở stderr)
- stdout KHÔNG bao giờ bị đụng tới ở đây.
"""

import sys
import logging
import os
from pathlib import Path
from datetime import datetime

import structlog
from src.config import config

_IS_PROD = os.environ.get("APP_ENV", "dev").lower() == "prod"

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / f"app_{datetime.now().strftime('%Y-%m-%d')}.log"

_SHARED_PROCESSORS = [
    structlog.stdlib.filter_by_level,
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
    structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
]


def setup_logging():
    """Configure structured logging: file (always) + stderr (JSON in prod, colorized in dev)."""

    structlog.configure(
        processors=_SHARED_PROCESSORS,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    root_logger.handlers.clear()

    # ── File handler: luôn JSON, luôn ghi (cả prod lẫn dev) ─────────
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer())
    )
    root_logger.addHandler(file_handler)

    # ── Stderr handler: format khác nhau theo môi trường ────────────
    stderr_handler = logging.StreamHandler(sys.stderr)
    if _IS_PROD:
        stderr_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer())
        )
    else:
        stderr_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(colors=True)
            )
        )
    root_logger.addHandler(stderr_handler)


def get_logger(name: str):
    """Get a logger instance for a specific module."""
    return structlog.get_logger(name)


def get_formatted_logger(name: str = "app"):
    """Alias of get_logger — kept for search_engine call sites."""
    return structlog.get_logger(name)


# Initialize logging on import
setup_logging()