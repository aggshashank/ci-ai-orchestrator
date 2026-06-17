"""006 customer context

Revision ID: 006
Revises: 005
Create Date: 2026-06-09

Changes:
  - decisions.customer_id              VARCHAR(128) nullable, indexed
  - decisions.customer_context_version VARCHAR(32)  nullable
  - decisions.customer_context_json    JSONB        nullable
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decisions", sa.Column("customer_id", sa.String(128), nullable=True))
    op.create_index("ix_decisions_customer_id", "decisions", ["customer_id"])
    op.add_column("decisions", sa.Column("customer_context_version", sa.String(32), nullable=True))
    op.add_column("decisions", sa.Column("customer_context_json", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "customer_context_json")
    op.drop_column("decisions", "customer_context_version")
    op.drop_index("ix_decisions_customer_id", table_name="decisions")
    op.drop_column("decisions", "customer_id")
