"""Add master info to client_orders and field_visit_requests table

Revision ID: 0006_master_info_field_visit
Revises: 0005_customer_avatar
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_master_info_field_visit"
down_revision = "0005_customer_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_orders", sa.Column("assigned_master_name", sa.String(200), nullable=True))
    op.add_column(
        "client_orders", sa.Column("assigned_master_avatar_url", sa.Text(), nullable=True)
    )

    op.create_table(
        "field_visit_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_key", sa.String(80), nullable=False, server_default="default"),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("preferred_date", sa.String(20), nullable=True),
        sa.Column("preferred_time", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("device_title", sa.String(255), nullable=False, server_default=""),
        sa.Column("problem_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("zone_name", sa.String(100), nullable=True),
        sa.Column("price_estimate", sa.Float(), nullable=True),
        sa.Column("crm_request_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_field_visit_requests_tenant_key", "field_visit_requests", ["tenant_key"])
    op.create_index("ix_field_visit_requests_status", "field_visit_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_field_visit_requests_status", "field_visit_requests")
    op.drop_index("ix_field_visit_requests_tenant_key", "field_visit_requests")
    op.drop_table("field_visit_requests")
    op.drop_column("client_orders", "assigned_master_avatar_url")
    op.drop_column("client_orders", "assigned_master_name")
