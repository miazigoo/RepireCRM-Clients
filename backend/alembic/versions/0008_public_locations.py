"""Add public_locations to marketing snapshot

Revision ID: 0008_pub_locations
Revises: 0007_snapshot_field_visit
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_pub_locations"
down_revision = "0007_snapshot_field_visit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_marketing_snapshots",
        sa.Column(
            "public_locations",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column(
        "client_marketing_snapshots",
        "public_locations",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("client_marketing_snapshots", "public_locations")
