"""Drop rate_limit_buckets table (rate limiting moved to Redis)

Revision ID: 0004_drop_rate_limit_buckets
Revises: 0003_client_marketing_snapshots
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_drop_rate_limit_buckets"
down_revision = "0003_client_marketing_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_expires_at", table_name="rate_limit_buckets")
    op.drop_index("ix_rate_limit_buckets_key", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")


def downgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rate_limit_buckets_key", "rate_limit_buckets", ["key"], unique=True)
    op.create_index(
        "ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"], unique=False
    )
