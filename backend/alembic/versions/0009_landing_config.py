"""Add landing_config to marketing snapshot

Revision ID: 0009_landing_cfg
Revises: 0008_pub_locations
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_landing_cfg"
down_revision = "0008_pub_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_marketing_snapshots",
        sa.Column("landing_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("client_marketing_snapshots", "landing_config")
