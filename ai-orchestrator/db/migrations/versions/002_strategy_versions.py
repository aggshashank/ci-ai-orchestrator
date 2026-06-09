"""002 strategy versions

Revision ID: 002
Revises: 001
Create Date: 2026-06-07

Adds: strategy_versions table — immutable snapshots of every strategy YAML set.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(64), nullable=False, unique=True),
        # Full snapshot of every YAML rule file at registration time
        sa.Column("rules_snapshot", JSONB(), nullable=False),
        sa.Column("weights_snapshot", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changelog", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_strategy_versions_version", "strategy_versions", ["version"], unique=True)
    op.create_index("ix_strategy_versions_is_active", "strategy_versions", ["is_active"])


def downgrade() -> None:
    op.drop_table("strategy_versions")
