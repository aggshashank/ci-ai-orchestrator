"""
logging_config.py
-----------------
Single source of truth for structured JSON logging across the orchestrator.

Every log line produced by structlog or stdlib logging will contain:
  - timestamp   ISO-8601 UTC
  - level       info / warning / error / ...
  - service     ai-orchestrator
  - correlation_id  request-scoped (empty string if not yet bound)
  - logger      module name

PII fields are scrubbed before any line reaches the appender.
"""
import logging
import sys
from typing import Callable
from uuid import uuid4

import structlog

CORRELATION_HEADER = "X-Correlation-Id"
SERVICE_NAME = "ai-orchestrator"

# Canonical PII field names (camelCase + snake_case variants).
# Any log event that accidentally includes these keys will have the value replaced.
_PII_KEYS: frozenset[str] = frozenset({
    "name",
    "applicant_name",
    "annualIncome",
    "annual_income",
    "income",
    "ssn",
    "social_security_number",
    "dob",
    "date_of_birth",
    "email",
    "phone",
    "phone_number",
    "address",
    "street_address",
    "account_number",
    "card_number",
    "pan",
})


# ── Structlog processors ───────────────────────────────────────────────────────

def _add_service(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    event_dict.setdefault("service", SERVICE_NAME)
    return event_dict


def _ensure_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    event_dict.setdefault("correlation_id", "")
    return event_dict


def _scrub_pii(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Remove known PII fields before the event is serialised to JSON."""
    for key in _PII_KEYS:
        if key in event_dict:
            event_dict[key] = "[REDACTED]"

    # Belt-and-suspenders: if an 'application' sub-dict slips through, scrub it.
    app = event_dict.get("application")
    if isinstance(app, dict):
        for key in _PII_KEYS:
            if key in app:
                app[key] = "[REDACTED]"

    return event_dict


# ── Public API ─────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """
    Wire up structlog + stdlib so every line (including uvicorn / kafka-python)
    is emitted as a single JSON object to stdout.

    Call once at process startup before any logger is used.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service,
        _ensure_correlation_id,
        _scrub_pii,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Let uvicorn propagate through our root handler instead of its own formatter.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def bind_correlation_id(correlation_id: str | None) -> str:
    """Bind correlation_id to the current async context; generate one if absent."""
    resolved = correlation_id or generate_correlation_id()
    structlog.contextvars.bind_contextvars(correlation_id=resolved)
    return resolved


def clear_log_context() -> None:
    """Clear all context vars at the end of a request / Kafka message."""
    structlog.contextvars.clear_contextvars()


def generate_correlation_id() -> str:
    return f"orch-{uuid4().hex[:12]}"


async def correlation_middleware(request, call_next: Callable):
    """
    FastAPI middleware that:
      1. Reads X-Correlation-Id from the inbound request (or generates one)
      2. Binds it to structlog context vars for the duration of the request
      3. Echoes it back in the response header
    """
    correlation_id = bind_correlation_id(request.headers.get(CORRELATION_HEADER))
    request.state.correlation_id = correlation_id

    try:
        response = await call_next(request)
    finally:
        clear_log_context()

    response.headers[CORRELATION_HEADER] = correlation_id
    return response
