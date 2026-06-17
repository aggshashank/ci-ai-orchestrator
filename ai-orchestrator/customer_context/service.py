"""
CustomerContextService — assembles a CustomerProfile from the decisions history.

In a real bank this would call:
  - Core banking API for account balances and payment events
  - Bureau gateway for fresh FICO refresh
  - CRM for channel interactions

For the POC, we derive all signals from the decisions table, which is the
only source of truth we have. The logic is clearly labelled so it can be
swapped for real API calls without changing the calling interface.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from customer_context.models import CustomerProfile, empty_profile
from customer_context.redis_store import CustomerContextStore

logger = structlog.get_logger()


class CustomerContextService:
    def __init__(self, session: AsyncSession, store: CustomerContextStore) -> None:
        self._session = session
        self._store = store

    # ── Public ────────────────────────────────────────────────────────────────

    async def get_profile(self, customer_id: str) -> CustomerProfile:
        """Return cached profile or build from history. Always returns a profile."""
        cached = self._store.get(customer_id)
        if cached is not None:
            logger.debug("customer_context_cache_hit", customer_id=customer_id,
                         version=cached.profile_version)
            return cached

        profile = await self._build_from_history(customer_id)
        self._store.set(profile)
        logger.info(
            "customer_context_built",
            customer_id=customer_id,
            is_new=profile.is_new_customer,
            accounts=profile.existing_accounts,
        )
        return profile

    async def invalidate(self, customer_id: str) -> None:
        self._store.invalidate(customer_id)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _build_from_history(self, customer_id: str) -> CustomerProfile:
        from db.models import Decision  # local import — avoids circular at module load

        stmt = (
            select(Decision)
            .where(Decision.customer_id == customer_id)
            .order_by(Decision.created_at.desc())
            .limit(50)
        )
        result = await self._session.execute(stmt)
        decisions = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        profile_version = now.strftime("%Y%m%dT%H%M%SZ")

        if not decisions:
            return empty_profile(customer_id)

        total = len(decisions)
        approved = sum(1 for d in decisions if d.recommendation == "APPROVE")

        # Payment consistency proxy — APPROVE rate from origination decisions
        payment_consistency = round(approved / total, 3)

        # Utilization trend from most recent 3 application payloads
        util_trend: list[float] = []
        for d in decisions[:3]:
            util = (d.application_json or {}).get("utilization")
            if util is not None:
                util_trend.append(float(util))
        util_trend.reverse()  # oldest → newest

        # Exposure: rough average income from recent decisions
        incomes = [
            float(d.application_json.get("annualIncome") or 0)
            for d in decisions[:5]
            if d.application_json
        ]
        avg_income = sum(incomes) / max(len(incomes), 1)

        # CLV heuristic: 5% of average income × consistency (replace with actuarial model)
        estimated_clv = round(avg_income * payment_consistency * 0.05, 2)

        prior_apps = [
            {
                "correlation_id": d.correlation_id,
                "recommendation": d.recommendation,
                "created_at": d.created_at.isoformat(),
                "strategy_version": d.strategy_version,
                "decision_type": getattr(d, "decision_type", "ORIGINATION"),
            }
            for d in decisions[:10]
        ]

        return CustomerProfile(
            customer_id=customer_id,
            profile_version=profile_version,
            existing_accounts=approved,
            total_exposure=avg_income,
            utilization_trend_3m=util_trend,
            payment_consistency_score=payment_consistency,
            prior_applications=prior_apps,
            estimated_clv=estimated_clv,
            last_bureau_refresh=decisions[0].created_at,
            is_new_customer=False,
        )
