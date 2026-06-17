"""009_fairness_reports

Creates fairness_reports table for governance audit trail (Task 3.4).

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fairness_reports",
        sa.Column("id",                    sa.BigInteger(),  primary_key=True, autoincrement=True),
        sa.Column("report_date",            sa.String(10),    nullable=False),
        sa.Column("period_days",            sa.Integer(),     nullable=False),
        sa.Column("total_decisions",        sa.Integer(),     nullable=False),
        sa.Column("overall_approval_rate",  sa.Float(),       nullable=False),
        sa.Column("violations_count",       sa.Integer(),     nullable=False, server_default="0"),
        sa.Column("violations_json",        JSONB(),          nullable=True),
        sa.Column("report_html",            sa.Text(),        nullable=True),
        sa.Column("created_at",             sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fairness_reports_report_date",    "fairness_reports", ["report_date"])
    op.create_index("ix_fairness_reports_violations",     "fairness_reports", ["violations_count"])


def downgrade():
    op.drop_table("fairness_reports")
