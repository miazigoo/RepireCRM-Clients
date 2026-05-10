"""Add avatar field to customer_accounts

Revision ID: 0005_customer_avatar
Revises: 0004_drop_rate_limit_buckets
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_customer_avatar"
down_revision = "0004_drop_rate_limit_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_accounts",
        sa.Column("avatar", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer_accounts", "avatar")
