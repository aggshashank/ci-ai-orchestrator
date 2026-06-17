"""007 workflow types

Revision ID: 007
Revises: 006
Create Date: 2026-06-09

Changes:
  - decisions.decision_type  VARCHAR(32) NOT NULL default 'ORIGINATION'
    Identifies which workflow produced the decision.
    Values: ORIGINATION | LIMIT_REVIEW | DELINQUENCY_TREATMENT | CROSS_SELL
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column(
            "decision_type",
            sa.String(32),
            nullable=False,
            server_default="ORIGINATION",
        ),
    )
    op.create_index("ix_decisions_decision_type", "decisions", ["decision_type"])


def downgrade() -> None:
    op.drop_index("ix_decisions_decision_type", table_name="decisions")
    op.drop_column("decisions", "decision_type")
