"""005 prompt versions

Revision ID: 005
Revises: 004
Create Date: 2026-06-07

Changes:
  - decisions.prompt_versions_json  JSONB nullable
    Stores {credit_agent: "v1", fraud_agent: "v1", ...} for audit reproducibility.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("prompt_versions_json", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("decisions", "prompt_versions_json")
