"""001 initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-07

Creates: decisions, agent_outputs, adverse_actions, policy_retrievals
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("correlation_id", sa.String(128), nullable=False, unique=True),
        sa.Column("recommendation", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("strategy_version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("model_version", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("human_decision", sa.String(32), nullable=True),
        sa.Column("reviewer", sa.String(256), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_json", JSONB(), nullable=False),
    )
    op.create_index("ix_decisions_correlation_id", "decisions", ["correlation_id"], unique=True)

    op.create_table(
        "agent_outputs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.BigInteger(), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("output_json", JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
    )
    op.create_index("ix_agent_outputs_decision_id", "agent_outputs", ["decision_id"])

    op.create_table(
        "adverse_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.BigInteger(), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("description", sa.String(256), nullable=False),
    )
    op.create_index("ix_adverse_actions_decision_id", "adverse_actions", ["decision_id"])

    op.create_table(
        "policy_retrievals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.BigInteger(), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("source_file", sa.String(512), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_policy_retrievals_decision_id", "policy_retrievals", ["decision_id"])


def downgrade() -> None:
    op.drop_table("policy_retrievals")
    op.drop_table("adverse_actions")
    op.drop_table("agent_outputs")
    op.drop_table("decisions")
