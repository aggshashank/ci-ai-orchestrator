"""008_decision_outcomes

Creates decision_outcomes table for outcome event storage (Task 3.3).

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "decision_outcomes",
        sa.Column("id",                      sa.BigInteger(),  primary_key=True, autoincrement=True),
        sa.Column("correlation_id",           sa.String(128),   nullable=False),
        sa.Column("outcome_type",             sa.String(32),    nullable=False),
        sa.Column("outcome_date",             sa.String(32),    nullable=False),
        sa.Column("months_on_books",          sa.Integer(),     nullable=False, server_default="0"),
        sa.Column("original_recommendation",  sa.String(32),    nullable=False, server_default=""),
        sa.Column("original_confidence",      sa.Float(),       nullable=False, server_default="0"),
        sa.Column("consumed_at",              sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_decision_outcomes_correlation_id", "decision_outcomes", ["correlation_id"])
    op.create_index("ix_decision_outcomes_outcome_type",   "decision_outcomes", ["outcome_type"])
    op.create_unique_constraint(
        "uq_decision_outcomes_corr_type",
        "decision_outcomes",
        ["correlation_id", "outcome_type"],
    )


def downgrade():
    op.drop_table("decision_outcomes")
