"""
Redis-backed cache for CustomerProfile objects.
Falls back silently when Redis is unavailable — callers always get a result.
"""
from __future__ import annotations

from typing import Optional

import structlog

from customer_context.models import CustomerProfile

logger = structlog.get_logger()

_TTL_SECONDS = 86_400  # 24 hours


class CustomerContextStore:
    def __init__(self, redis_url: str = "") -> None:
        self._client = None
        if redis_url:
            try:
                import redis as _redis
                self._client = _redis.from_url(redis_url, decode_responses=True)
                self._client.ping()
                logger.info("customer_context_store_connected")
            except Exception as exc:
                logger.warning("customer_context_store_unavailable", error=str(exc))
                self._client = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def get(self, customer_id: str) -> Optional[CustomerProfile]:
        if not self._client:
            return None
        try:
            import json
            raw = self._client.get(self._key(customer_id))
            if raw is None:
                return None
            return CustomerProfile.model_validate_json(raw)
        except Exception as exc:
            logger.warning("customer_context_get_error", customer_id=customer_id, error=str(exc))
            return None

    def set(self, profile: CustomerProfile) -> None:
        if not self._client:
            return
        try:
            self._client.setex(
                self._key(profile.customer_id),
                _TTL_SECONDS,
                profile.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("customer_context_set_error", customer_id=profile.customer_id, error=str(exc))

    def invalidate(self, customer_id: str) -> None:
        if not self._client:
            return
        try:
            self._client.delete(self._key(customer_id))
        except Exception as exc:
            logger.warning("customer_context_invalidate_error", customer_id=customer_id, error=str(exc))

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _key(customer_id: str) -> str:
        return f"customer_context:{customer_id}"
