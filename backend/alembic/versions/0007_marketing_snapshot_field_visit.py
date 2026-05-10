"""Add field_visit_config to client_marketing_snapshots

Revision ID: 0007_marketing_snapshot_field_visit
Revises: 0006_master_info_field_visit
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_snapshot_field_visit"
down_revision = "0006_master_info_field_visit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_marketing_snapshots",
        sa.Column("field_visit_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("client_marketing_snapshots", "field_visit_config")
