"""003 simulations

Revision ID: 003
Revises: 002
Create Date: 2026-06-07

Adds: simulations table — tracks background decision simulation runs.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulations",
        sa.Column("id", sa.String(36), primary_key=True),            # UUID
        sa.Column("strategy_version", sa.String(64), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("date_range", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("baseline_distribution", JSONB(), nullable=True),
        sa.Column("simulated_distribution", JSONB(), nullable=True),
        sa.Column("changed_decisions", JSONB(), nullable=True),       # list of {correlation_id, original, simulated}
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("report_html", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_simulations_strategy_version", "simulations", ["strategy_version"])
    op.create_index("ix_simulations_status", "simulations", ["status"])


def downgrade() -> None:
    op.drop_table("simulations")
