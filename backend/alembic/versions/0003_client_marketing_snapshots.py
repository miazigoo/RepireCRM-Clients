"""client marketing snapshots from CRM

Revision ID: 0003_client_marketing_snapshots
Revises: 0002_client_order_crm_snapshot
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_client_marketing_snapshots"
down_revision = "0002_client_order_crm_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_marketing_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("promotions", sa.JSON(), nullable=False),
        sa.Column("banner", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_key", name="uq_marketing_tenant"),
    )
    op.create_index(
        "ix_client_marketing_snapshots_tenant_key",
        "client_marketing_snapshots",
        ["tenant_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_marketing_snapshots_tenant_key", table_name="client_marketing_snapshots"
    )
    op.drop_table("client_marketing_snapshots")
