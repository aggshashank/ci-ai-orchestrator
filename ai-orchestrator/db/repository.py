"""
DecisionRepository — all DB reads and writes go through here.
Agents and endpoints never touch ORM objects directly.
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import AdverseAction, AgentOutput, Decision, PolicyRetrieval

logger = structlog.get_logger()


class DecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Writes ────────────────────────────────────────────────────────────────

    async def save_decision(self, payload: dict) -> Decision:
        """
        Persist a complete decision from the explainability agent output.

        payload keys mirror the audit_record dict previously written to JSONL:
          correlation_id, recommendation, confidence, composite_score,
          application (dict), credit_result, fraud_result, policy_context,
          risk_decision, explanation  (all dicts)
        """
        explanation = payload.get("explanation", {})
        risk = payload.get("risk_decision", {})
        settings_ver = payload.get("strategy_version", "v1")
        model_ver = payload.get("model_version", "unknown")

        decision = Decision(
            correlation_id=payload["correlation_id"],
            recommendation=payload["recommendation"],
            confidence=payload["confidence"],
            composite_score=payload.get("composite_score", 0.0),
            strategy_version=settings_ver,
            model_version=model_ver,
            application_json=payload.get("application", {}),
        )
        self._s.add(decision)
        await self._s.flush()  # populate decision.id before children

        # Agent outputs
        for agent_name, key in [
            ("credit_agent",        "credit_result"),
            ("fraud_agent",         "fraud_result"),
            ("policy_rag_agent",    "policy_context"),
            ("explainability_agent","explanation"),
        ]:
            output = payload.get(key)
            if output:
                self._s.add(AgentOutput(
                    decision_id=decision.id,
                    agent_name=agent_name,
                    output_json=output,
                ))

        # Adverse actions
        for ac in explanation.get("adverse_action_codes", []):
            self._s.add(AdverseAction(
                decision_id=decision.id,
                code=ac["code"],
                description=ac["description"],
            ))

        # Policy retrievals — pull chunk texts from policy_context
        policy = payload.get("policy_context", {})
        for rule in policy.get("rules", []):
            self._s.add(PolicyRetrieval(
                decision_id=decision.id,
                chunk_text=rule,
                source_file=None,
                similarity_score=None,
            ))

        logger.info("decision saved", correlation_id=payload["correlation_id"],
                    recommendation=payload["recommendation"])
        return decision

    async def apply_human_decision(
        self,
        correlation_id: str,
        human_decision: str,
        reviewer: str,
        reviewer_notes: str = "",
    ) -> Optional[Decision]:
        decision = await self._get_by_correlation_id(correlation_id)
        if not decision:
            return None
        decision.human_decision = human_decision
        decision.reviewer = reviewer
        decision.reviewer_notes = reviewer_notes
        decision.decided_at = datetime.now(timezone.utc)
        return decision

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_pending_review_queue(self) -> list[Decision]:
        """All MANUAL_REVIEW decisions not yet actioned by a human."""
        stmt = (
            select(Decision)
            .where(
                Decision.recommendation == "MANUAL_REVIEW",
                Decision.human_decision.is_(None),
            )
            .options(selectinload(Decision.adverse_actions))
            .order_by(Decision.created_at.desc())
        )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def get_by_correlation_id(self, correlation_id: str) -> Optional[Decision]:
        return await self._get_by_correlation_id(correlation_id, eager=True)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Decision]:
        stmt = (
            select(Decision)
            .order_by(Decision.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get_by_correlation_id(
        self, correlation_id: str, eager: bool = False
    ) -> Optional[Decision]:
        stmt = select(Decision).where(Decision.correlation_id == correlation_id)
        if eager:
            stmt = stmt.options(
                selectinload(Decision.agent_outputs),
                selectinload(Decision.adverse_actions),
                selectinload(Decision.policy_retrievals),
            )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()
