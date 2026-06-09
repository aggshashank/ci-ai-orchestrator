"""
SQLAlchemy ORM models for the decision store.

Four tables:
  decisions         — one row per application decision
  agent_outputs     — one row per agent per decision (credit, fraud, policy, explain)
  adverse_actions   — ECOA adverse action codes attached to a decision
  policy_retrievals — RAG chunks retrieved during policy evaluation
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)  # APPROVE|DECLINE|MANUAL_REVIEW
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    # HITL fields — populated via POST /review/{id}/decision
    human_decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reviewer: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Full application payload — stored for audit reproducibility
    application_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Champion/challenger experiment routing (nullable — NULL when no experiment active)
    experiment_variant: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    # Audit trail: which prompt version each agent used
    prompt_versions_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    agent_outputs: Mapped[list["AgentOutput"]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    adverse_actions: Mapped[list["AdverseAction"]] = relationship(back_populates="decision", cascade="all, delete-orphan")
    policy_retrievals: Mapped[list["PolicyRetrieval"]] = relationship(back_populates="decision", cascade="all, delete-orphan")


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    decision: Mapped["Decision"] = relationship(back_populates="agent_outputs")


class AdverseAction(Base):
    __tablename__ = "adverse_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False)      # AA01–AA12
    description: Mapped[str] = mapped_column(String(256), nullable=False)

    decision: Mapped["Decision"] = relationship(back_populates="adverse_actions")


class PolicyRetrieval(Base):
    __tablename__ = "policy_retrievals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    decision: Mapped["Decision"] = relationship(back_populates="policy_retrievals")


class StrategyVersionRecord(Base):
    """Immutable snapshot of a rules YAML set registered at a point in time."""
    __tablename__ = "strategy_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    rules_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    weights_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    changelog: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())


class Experiment(Base):
    """Champion/Challenger experiment run — one row per active A/B test."""
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    champion_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    challenger_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    challenger_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    significance_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    min_sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    promoted_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())


class Simulation(Base):
    """Background simulation run record."""
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID string
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    date_range: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    baseline_distribution: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    simulated_distribution: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    changed_decisions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    report_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
