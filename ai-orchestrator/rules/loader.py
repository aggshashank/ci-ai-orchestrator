"""
RulesLoader: reads YAML from disk (or Redis for hot-reload), validates, and caches.

Cache hierarchy:
  1. In-memory dict (process-local, instant)
  2. Redis string value keyed as  rules:{version}:{name}  (hot-reload without restart)
  3. YAML file on disk (source of truth, used as fallback)

To hot-reload a ruleset without restarting:
  redis-cli SET rules:v1.0.0:credit_rules "$(cat credit_rules.yaml)"
  Then call loader.invalidate("credit_rules") or loader.invalidate() for all.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import structlog
import yaml

from rules.schemas import (
    CreditRules,
    FraudRules,
    PolicyRules,
    StrategyMetadata,
    SynthesisWeights,
)
from rules.validator import validate_yaml

logger = structlog.get_logger()

T = TypeVar("T", CreditRules, FraudRules, PolicyRules, SynthesisWeights, StrategyMetadata)


class RulesLoader:
    def __init__(
        self,
        version: str,
        strategies_dir: Path,
        redis_url: str = "",
    ) -> None:
        self._version = version
        self._dir = strategies_dir / version
        self._cache: dict[str, Any] = {}
        self._redis: Any = None  # redis.Redis | None

        if redis_url:
            try:
                import redis as redis_lib  # optional dep
                client = redis_lib.from_url(redis_url, decode_responses=True)
                client.ping()
                self._redis = client
                logger.info("rules_loader redis connected", version=version)
            except Exception as exc:
                logger.warning(
                    "rules_loader redis unavailable — using file cache only",
                    error=str(exc),
                )

    # ── Public accessors ──────────────────────────────────────────────────────

    def get_credit_rules(self) -> CreditRules:
        return self._load("credit_rules", CreditRules)

    def get_fraud_rules(self) -> FraudRules:
        return self._load("fraud_rules", FraudRules)

    def get_policy_rules(self) -> PolicyRules:
        return self._load("policy_rules", PolicyRules)

    def get_synthesis_weights(self) -> SynthesisWeights:
        return self._load("synthesis_weights", SynthesisWeights)

    def get_metadata(self) -> StrategyMetadata:
        return self._load("metadata", StrategyMetadata)

    def invalidate(self, key: str | None = None) -> None:
        """Clear cached rule(s). Pass a name to evict one key; omit to clear all."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
        logger.info("rules_cache_invalidated", key=key or "all", version=self._version)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self, name: str, model_cls: type[T]) -> T:
        if name in self._cache:
            return self._cache[name]  # type: ignore[return-value]

        raw = self._from_redis(name) or self._from_file(name)
        validate_yaml(raw, name)
        parsed = model_cls.model_validate(raw)
        self._cache[name] = parsed
        logger.debug("rules_loaded", name=name, version=self._version)
        return parsed  # type: ignore[return-value]

    def _from_redis(self, name: str) -> dict | None:
        if not self._redis:
            return None
        try:
            value = self._redis.get(f"rules:{self._version}:{name}")
            if value:
                return yaml.safe_load(value)
        except Exception as exc:
            logger.warning("rules_redis_read_failed", name=name, error=str(exc))
        return None

    def _from_file(self, name: str) -> dict:
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"Rules file not found: {path}. "
                f"Check strategies_dir setting and version '{self._version}'."
            )
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)


# Module-level loader cache — one RulesLoader instance per (version, dir) pair.
_loader_registry: dict[tuple[str, str], RulesLoader] = {}


def get_loader(
    version: str,
    strategies_dir: Path,
    redis_url: str = "",
) -> RulesLoader:
    key = (version, str(strategies_dir))
    if key not in _loader_registry:
        _loader_registry[key] = RulesLoader(version, strategies_dir, redis_url)
    return _loader_registry[key]


def clear_loader_registry() -> None:
    """Evict all cached loaders — use in tests or multi-provider eval runs."""
    _loader_registry.clear()
