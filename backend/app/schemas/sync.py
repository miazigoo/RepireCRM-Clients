from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SyncOrderItem(BaseModel):
    crm_order_id: int | None = None
    external_id: str | None = None
    order_number: str
    organization: dict[str, Any] | None = None
    shop: dict[str, Any] | None = None
    customer: dict[str, Any] | None = None
    device: dict[str, Any] | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    status: str
    status_display: str | None = None
    priority: str = "normal"
    device_title: str | None = None
    problem_description: str
    diagnosis: str | None = None
    work_description: str | None = None
    accessories: str | None = None
    device_condition: str | None = None
    cost_estimate: Decimal | None = Decimal("0")
    final_cost: Decimal | None = None
    total_cost: Decimal | None = None
    remaining_payment: Decimal | None = None
    estimated_completion: datetime | None = None
    repair_stages: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    prepayment: Decimal | None = None
    subtotal_before_discount: Decimal | None = None
    discount_total: Decimal | None = None
    warranty_days: int | None = None
    warranty_until: datetime | None = None
    warranty_active: bool | None = None
    is_warranty_case: bool | None = None
    warranty_parent_order_id: int | None = None
    warranty_parent_order_number: str | None = None
    warranty_reason: str | None = None
    completed_at: datetime | None = None
    additional_services: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []
    assigned_master: dict[str, Any] | None = None


class SyncOrdersRequest(BaseModel):
    tenant_key: str | None = None
    sent_at: datetime | None = None
    orders: list[SyncOrderItem]


class SyncOrderResponseItem(BaseModel):
    crm_order_id: int | None = None
    remote_order_id: str


class SyncOrdersResponse(BaseModel):
    orders: list[SyncOrderResponseItem]


class ClientActionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | str
    type: str | None = None
    customer_id: int
    order_id: int | None
    action_type: str
    payload: dict[str, Any]
    status: str
    created_at: datetime


class SyncActionsResponse(BaseModel):
    actions: list[dict[str, Any]]


class MarkActionSyncedRequest(BaseModel):
    status: Literal["synced", "failed", "applied", "rejected", "error"] = "applied"
    crm_order_id: int | None = None
    crm_order_number: str | None = Field(default=None, max_length=80)
    crm_task_id: int | None = None
    error: str | None = None


class SyncMarketingRequest(BaseModel):
    tenant_key: str | None = None
    sent_at: datetime | None = None
    promotions: list[dict[str, Any]] = Field(default_factory=list)
    banner: dict[str, Any] | None = None
    field_visit: dict[str, Any] | None = None
    locations: list[dict[str, Any]] | None = None
    landing: dict[str, Any] | None = None


class SyncMarketingResponse(BaseModel):
    ok: bool = True
    promotions_count: int = 0
    has_banner: bool = False
