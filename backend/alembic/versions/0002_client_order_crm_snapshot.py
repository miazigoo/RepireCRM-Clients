"""client_orders crm_snapshot for CRM extras

Revision ID: 0002_client_order_crm_snapshot
Revises: 0001_initial
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_client_order_crm_snapshot"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_orders", sa.Column("crm_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("client_orders", "crm_snapshot")
