from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class CustomerAccount(Base):
    __tablename__ = "customer_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    middle_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    identities: Mapped[list["CustomerIdentity"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class CustomerIdentity(Base):
    __tablename__ = "customer_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"))
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    type: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(255))
    normalized_value: Mapped[str] = mapped_column(String(255), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped[CustomerAccount] = relationship(back_populates="identities")

    __table_args__ = (
        Index("ix_customer_identity_type_value", "type", "normalized_value"),
        UniqueConstraint(
            "tenant_key", "type", "normalized_value", name="uq_identity_tenant_type_value"
        ),
    )


class VerificationChallenge(Base):
    __tablename__ = "verification_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(
        ForeignKey("customer_identities.id", ondelete="CASCADE")
    )
    code_hash: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(32), default="contact")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    identity: Mapped[CustomerIdentity] = relationship()


class PasswordResetChallenge(Base):
    __tablename__ = "password_reset_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"))
    identity_id: Mapped[int] = mapped_column(
        ForeignKey("customer_identities.id", ondelete="CASCADE")
    )
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped[CustomerAccount] = relationship()
    identity: Mapped[CustomerIdentity] = relationship()


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    channel: Mapped[str] = mapped_column(String(16))
    destination: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClientOrder(Base):
    __tablename__ = "client_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    crm_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_number: Mapped[str] = mapped_column(String(80), index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_accounts.id"), nullable=True
    )
    customer_phone: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="received")
    status_display: Mapped[str] = mapped_column(String(80), default="Принят")
    priority: Mapped[str] = mapped_column(String(40), default="normal")
    device_title: Mapped[str] = mapped_column(String(255))
    problem_description: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0)
    final_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    remaining_payment: Mapped[float] = mapped_column(Float, default=0)
    estimated_completion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    crm_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    repair_stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    approvals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), default="crm")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[CustomerAccount | None] = relationship()

    __table_args__ = (
        UniqueConstraint("tenant_key", "external_id", name="uq_order_tenant_external"),
        UniqueConstraint("tenant_key", "order_number", name="uq_order_tenant_number"),
    )


class ClientMarketingSnapshot(Base):
    """Акции и баннер, синхронизируемые из CRM (POST /api/sync/marketing/upsert)."""

    __tablename__ = "client_marketing_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    promotions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    banner: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ClientAction(Base):
    __tablename__ = "client_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("client_orders.id"), nullable=True)
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    action_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sync_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[CustomerAccount] = relationship()
    order: Mapped[ClientOrder | None] = relationship()


class CustomerSession(Base):
    __tablename__ = "customer_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"))
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    device_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[CustomerAccount] = relationship()


class MobileDevice(Base):
    __tablename__ = "mobile_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"))
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    platform: Mapped[str] = mapped_column(String(24))
    device_uid: Mapped[str] = mapped_column(String(255))
    push_token: Mapped[str] = mapped_column(Text, default="")
    app_version: Mapped[str] = mapped_column(String(40), default="")
    locale: Mapped[str] = mapped_column(String(20), default="ru-RU")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[CustomerAccount] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "tenant_key", "platform", "device_uid", name="uq_mobile_device_tenant_platform_uid"
        ),
    )


class PushNotification(Base):
    __tablename__ = "push_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer_accounts.id", ondelete="CASCADE"))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True)
    tenant_key: Mapped[str] = mapped_column(String(80), default="default", index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    provider_message_id: Mapped[str] = mapped_column(String(255), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
