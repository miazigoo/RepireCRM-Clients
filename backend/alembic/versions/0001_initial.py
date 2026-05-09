"""initial client portal schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("middle_name", sa.String(length=80), nullable=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("marketing_consent", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_customer_accounts_tenant_key", "customer_accounts", ["tenant_key"])

    op.create_table(
        "customer_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "tenant_key", "type", "normalized_value", name="uq_identity_tenant_type_value"
        ),
    )
    op.create_index("ix_customer_identities_tenant_key", "customer_identities", ["tenant_key"])
    op.create_index(
        "ix_customer_identities_normalized_value", "customer_identities", ["normalized_value"]
    )
    op.create_index(
        "ix_customer_identity_type_value", "customer_identities", ["type", "normalized_value"]
    )

    op.create_table(
        "verification_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "identity_id",
            sa.Integer(),
            sa.ForeignKey("customer_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "password_reset_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "identity_id",
            sa.Integer(),
            sa.ForeignKey("customer_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_messages_tenant_key", "outbox_messages", ["tenant_key"])

    op.create_table(
        "client_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("crm_order_id", sa.Integer(), nullable=True),
        sa.Column("order_number", sa.String(length=80), nullable=False),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer_accounts.id"), nullable=True
        ),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("status_display", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("device_title", sa.String(length=255), nullable=False),
        sa.Column("problem_description", sa.Text(), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("work_description", sa.Text(), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=False),
        sa.Column("final_cost", sa.Float(), nullable=True),
        sa.Column("remaining_payment", sa.Float(), nullable=False),
        sa.Column("estimated_completion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("repair_stages", sa.JSON(), nullable=False),
        sa.Column("approvals", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_key", "external_id", name="uq_order_tenant_external"),
        sa.UniqueConstraint("tenant_key", "order_number", name="uq_order_tenant_number"),
    )
    op.create_index("ix_client_orders_tenant_key", "client_orders", ["tenant_key"])
    op.create_index("ix_client_orders_crm_order_id", "client_orders", ["crm_order_id"])
    op.create_index("ix_client_orders_order_number", "client_orders", ["order_number"])
    op.create_index("ix_client_orders_customer_phone", "client_orders", ["customer_phone"])
    op.create_index("ix_client_orders_customer_email", "client_orders", ["customer_email"])

    op.create_table(
        "client_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("client_orders.id"), nullable=True),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sync_status", sa.String(length=32), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_client_actions_tenant_key", "client_actions", ["tenant_key"])
    op.create_index("ix_client_actions_status", "client_actions", ["status"])

    op.create_table(
        "mobile_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("platform", sa.String(length=24), nullable=False),
        sa.Column("device_uid", sa.String(length=255), nullable=False),
        sa.Column("push_token", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_key", "platform", "device_uid", name="uq_mobile_device_tenant_platform_uid"
        ),
    )
    op.create_index("ix_mobile_devices_tenant_key", "mobile_devices", ["tenant_key"])

    op.create_table(
        "customer_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("mobile_devices.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_customer_sessions_tenant_key", "customer_sessions", ["tenant_key"])
    op.create_index(
        "ix_customer_sessions_refresh_token_hash",
        "customer_sessions",
        ["refresh_token_hash"],
        unique=True,
    )

    op.create_table(
        "push_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("mobile_devices.id"), nullable=True),
        sa.Column("tenant_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_push_notifications_tenant_key", "push_notifications", ["tenant_key"])
    op.create_index("ix_push_notifications_status", "push_notifications", ["status"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_buckets_key", "rate_limit_buckets", ["key"], unique=True)
    op.create_index("ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"])


def downgrade() -> None:
    op.drop_table("rate_limit_buckets")
    op.drop_table("push_notifications")
    op.drop_table("customer_sessions")
    op.drop_table("mobile_devices")
    op.drop_table("client_actions")
    op.drop_table("client_orders")
    op.drop_table("outbox_messages")
    op.drop_table("password_reset_challenges")
    op.drop_table("verification_challenges")
    op.drop_table("customer_identities")
    op.drop_table("customer_accounts")
