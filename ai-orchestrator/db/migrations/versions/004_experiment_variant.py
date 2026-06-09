"""004 experiment variant

Revision ID: 004
Revises: 003
Create Date: 2026-06-07

Changes:
  - decisions.experiment_variant  VARCHAR(32) nullable
  - CREATE TABLE experiments
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add experiment_variant to decisions (nullable — NULL when no experiment running)
    op.add_column("decisions", sa.Column("experiment_variant", sa.String(32), nullable=True))
    op.create_index("ix_decisions_experiment_variant", "decisions", ["experiment_variant"])

    # Experiments table — one row per A/B test run
    op.create_table(
        "experiments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("champion_strategy", sa.String(64), nullable=False),
        sa.Column("challenger_strategy", sa.String(64), nullable=False),
        sa.Column("challenger_pct", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("significance_threshold", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column("min_sample_size", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("promoted_version", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_experiments_status", "experiments", ["status"])


def downgrade() -> None:
    op.drop_table("experiments")
    op.drop_index("ix_decisions_experiment_variant", table_name="decisions")
    op.drop_column("decisions", "experiment_variant")
