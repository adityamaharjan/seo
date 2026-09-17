"""add PageSpeed Insights usage flags to reports and site audits

Records whether a run was enriched with PageSpeed data, and for a crawl, how
much of it was covered. This is not cosmetic: PSI data feeds scored checks in
the performance category, so two reports are only comparable when they made the
same choice, and the report UI needs to say which pages carry rendered metrics.

Existing rows predate the feature and are backfilled to false, which is
accurate — none of them ran PageSpeed.

Revision ID: b4e2c8a71f03
Revises: a3f7b2c91d40
"""
import sqlalchemy as sa
from alembic import op

revision = "b4e2c8a71f03"
down_revision = "a3f7b2c91d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seo_reports",
        sa.Column(
            "used_psi", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "site_audits",
        sa.Column(
            "used_psi", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column(
        "site_audits", sa.Column("psi_scope", sa.String(length=16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("site_audits", "psi_scope")
    op.drop_column("site_audits", "used_psi")
    op.drop_column("seo_reports", "used_psi")
