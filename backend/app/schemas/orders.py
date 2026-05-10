from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..sanitization import sanitize_optional_text, sanitize_plain_text


class PortalRepairStageSchema(BaseModel):
    id: int | str
    title: str
    description: str | None = None
    photo_url: str | None = None
    created_at: datetime | str


class PortalApprovalSchema(BaseModel):
    id: int | str
    title: str
    description: str | None = None
    amount: float
    status: str
    status_display: str
    customer_comment: str | None = None
    decided_at: datetime | str | None = None
    created_at: datetime | str


class PortalShopSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crm_shop_id: int | None = None
    code: str | None = None
    name: str = ""
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class PortalOrganizationSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crm_organization_id: int | None = None
    name: str = ""


class PortalDeviceDetailSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_type: str | None = None
    brand: str | None = None
    model_name: str | None = None
    serial_number: str | None = None
    imei: str | None = None
    color: str | None = None
    storage_capacity: str | None = None


class PortalWarrantySchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    warranty_days: int | None = None
    warranty_until: datetime | str | None = None
    warranty_active: bool = False
    is_warranty_case: bool = False
    warranty_parent_order_id: int | None = None
    warranty_parent_order_number: str | None = None
    warranty_reason: str | None = None


class PortalAdditionalServiceSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    category: str | None = None
    quantity: float = 1
    price: float | None = None
    total_price: float | None = None


class PortalPaymentSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crm_payment_id: int | None = None
    payment_number: str = ""
    payment_type: str = ""
    status: str = ""
    status_display: str = ""
    amount: float | None = None
    payment_method: str = ""
    payment_date: datetime | str | None = None


class PortalOrderSchema(BaseModel):
    id: int
    order_number: str
    status: str
    status_display: str
    priority: str
    device_title: str
    problem_description: str
    diagnosis: str | None = None
    work_description: str | None = None
    cost_estimate: float
    final_cost: float | None = None
    remaining_payment: float
    created_at: datetime
    updated_at: datetime
    estimated_completion: datetime | None = None
    repair_stages: list[PortalRepairStageSchema] = []
    approvals: list[PortalApprovalSchema] = []
    organization: PortalOrganizationSchema | None = None
    shop: PortalShopSchema | None = None
    device: PortalDeviceDetailSchema | None = None
    warranty: PortalWarrantySchema | None = None
    additional_services: list[PortalAdditionalServiceSchema] = []
    payments: list[PortalPaymentSchema] = []
    accessories: str | None = None
    device_condition: str | None = None
    prepayment: float | None = None
    subtotal_before_discount: float | None = None
    discount_total: float | None = None
    total_cost: float | None = None
    completed_at: datetime | str | None = None
    assigned_master_name: str | None = None
    assigned_master_avatar_url: str | None = None


class PortalOrdersPage(BaseModel):
    """Paginated orders response."""

    items: list[PortalOrderSchema]
    total: int
    limit: int
    offset: int


class OrderCreateRequest(BaseModel):
    device_type: str = Field(min_length=1, max_length=80)
    brand: str = Field(min_length=1, max_length=80)
    model_name: str = Field(min_length=1, max_length=120)
    problem_description: str = Field(min_length=10, max_length=5000)
    serial_number: str | None = Field(default=None, max_length=120)
    imei: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=80)
    storage_capacity: str | None = Field(default=None, max_length=80)
    accessories: str | None = Field(default=None, max_length=1000)
    device_condition: str | None = Field(default=None, max_length=1000)
    cost_estimate: float = Field(default=0, ge=0)

    @field_validator(
        "device_type",
        "brand",
        "model_name",
        "problem_description",
        "serial_number",
        "imei",
        "color",
        "storage_capacity",
        "accessories",
        "device_condition",
        mode="before",
    )
    @classmethod
    def sanitize_order_text(cls, value):
        return sanitize_optional_text(value, max_length=5000)


class PublicTrackRequest(BaseModel):
    order_number: str = Field(max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("order_number", mode="before")
    @classmethod
    def sanitize_order_number(cls, value):
        return sanitize_plain_text(value, max_length=80)


class ApprovalDecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("comment", mode="before")
    @classmethod
    def sanitize_comment(cls, value):
        return sanitize_optional_text(value, max_length=2000)
