import logging
import sys
from typing import Any

import structlog

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "supabase_secret_key",
    "database_url",
    "direct_database_url",
    "redis_url",
    "webhook_signing_secret",
    "portal_token_pepper",
    "encryption_key",
}


def _mask_sensitive_values(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(level: str) -> None:
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _mask_sensitive_values,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=level.upper())
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
