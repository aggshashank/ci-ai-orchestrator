"""
StrategyRegistry: all DB reads and writes for the strategy_versions table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import StrategyVersionRecord as StrategyVersionORM
from strategy.models import StrategyVersionRecord

logger = structlog.get_logger()


class StrategyRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_versions(self) -> list[StrategyVersionRecord]:
        stmt = select(StrategyVersionORM).order_by(StrategyVersionORM.created_at.desc())
        result = await self._s.execute(stmt)
        return [_to_pydantic(row) for row in result.scalars().all()]

    async def get_by_version(self, version: str) -> Optional[StrategyVersionRecord]:
        row = await self._get_orm(version)
        return _to_pydantic(row) if row else None

    async def get_active(self) -> Optional[StrategyVersionRecord]:
        stmt = select(StrategyVersionORM).where(StrategyVersionORM.is_active.is_(True))
        result = await self._s.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_pydantic(row) if row else None

    async def register(
        self,
        version: str,
        snapshot: dict[str, Any],
        changelog: list[str],
    ) -> StrategyVersionRecord:
        """
        Idempotent: if this version is already registered, return the existing row.
        """
        existing = await self._get_orm(version)
        if existing:
            logger.info("strategy_version already registered", version=version)
            return _to_pydantic(existing)

        weights_snap = snapshot.get("synthesis_weights", {}).get("weights", {})
        row = StrategyVersionORM(
            version=version,
            rules_snapshot=snapshot,
            weights_snapshot=weights_snap,
            is_active=False,
            changelog=changelog,
        )
        self._s.add(row)
        await self._s.flush()
        logger.info("strategy_version registered", version=version)
        return _to_pydantic(row)

    async def set_active(self, version: str) -> Optional[StrategyVersionRecord]:
        """Deactivate any currently-active version, then activate this one."""
        now = datetime.now(timezone.utc)

        # Deactivate old active
        stmt = select(StrategyVersionORM).where(StrategyVersionORM.is_active.is_(True))
        result = await self._s.execute(stmt)
        for old in result.scalars().all():
            old.is_active = False
            old.deactivated_at = now

        target = await self._get_orm(version)
        if not target:
            return None
        target.is_active = True
        target.activated_at = now
        await self._s.flush()
        logger.info("strategy_version activated", version=version)
        return _to_pydantic(target)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get_orm(self, version: str) -> Optional[StrategyVersionORM]:
        stmt = select(StrategyVersionORM).where(StrategyVersionORM.version == version)
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()


def _to_pydantic(row: StrategyVersionORM) -> StrategyVersionRecord:
    return StrategyVersionRecord(
        version=row.version,
        is_active=row.is_active,
        activated_at=row.activated_at,
        deactivated_at=row.deactivated_at,
        created_at=row.created_at,
        changelog=row.changelog or [],
        rules_snapshot=row.rules_snapshot or {},
        weights_snapshot=row.weights_snapshot or {},
    )
