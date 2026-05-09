from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .sanitization import sanitize_optional_text, sanitize_plain_text

AuthPolicy = Literal["phone_or_email", "phone_only", "email_only"]


class ApiError(BaseModel):
    error: str
    details: dict[str, Any] | None = None


class BrandSettings(BaseModel):
    name: str
    accent_color: str
    logo_url: str | None = None
    support_phone: str | None = None
    support_email: str | None = None


class AuthSettings(BaseModel):
    policy: AuthPolicy
    allow_phone: bool
    allow_email: bool
    require_verified_contact_for_orders: bool


class PortalBannerSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    subtitle: str = ""
    image_url: str | None = None
    link_url: str | None = None
    active: bool = True


class PortalPromotionItemSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    crm_promotion_id: int
    title: str
    description: str = ""
    discount_type: str = "percent"
    value: str = "0"
    max_discount_amount: str | None = None
    min_order_amount: str = "0"
    starts_at: str | None = None
    ends_at: str | None = None
    promo_codes: list[str] = []
    auto_apply: bool = False


class PortalMarketingSchema(BaseModel):
    promotions: list[PortalPromotionItemSchema] = []
    banner: PortalBannerSchema | None = None


class PortalSettingsResponse(BaseModel):
    brand: BrandSettings
    auth: AuthSettings
    features: dict[str, bool]
    marketing: PortalMarketingSchema


class ContactSchema(BaseModel):
    id: int
    type: Literal["phone", "email"]
    value: str
    normalized_value: str
    is_primary: bool
    verified_at: datetime | None = None


class PortalCustomerSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    middle_name: str | None = None
    phone: str | None = None
    email: str | None = None
    marketing_consent: bool
    contacts: list[ContactSchema] = []


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    phone: str | None = None
    email: str | None = None
    password: str = Field(min_length=8)
    marketing_consent: bool = False

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def sanitize_required_names(cls, value):
        return sanitize_plain_text(value, max_length=80)

    @field_validator("middle_name", mode="before")
    @classmethod
    def sanitize_middle_name(cls, value):
        return sanitize_optional_text(value, max_length=80)


class LoginRequest(BaseModel):
    identifier: str | None = None
    phone: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode="after")
    def require_identifier(self):
        if not (self.identifier or self.phone or self.email):
            raise ValueError("Укажите телефон или email")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    customer: PortalCustomerSchema


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class ContactCreateRequest(BaseModel):
    type: Literal["phone", "email"]
    value: str
    make_primary: bool = True


class VerificationRequest(BaseModel):
    type: Literal["phone", "email"]
    value: str


class VerificationConfirmRequest(VerificationRequest):
    code: str = Field(min_length=4, max_length=12)


class ChallengeResponse(BaseModel):
    message: str
    delivery_id: int | None = None
    debug_code: str | None = None


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    marketing_consent: bool | None = None

    @field_validator("first_name", "last_name", "middle_name", mode="before")
    @classmethod
    def sanitize_profile_text(cls, value):
        return sanitize_optional_text(value, max_length=80)


class PasswordResetRequest(BaseModel):
    identifier: str = Field(max_length=255)


class PasswordResetConfirmRequest(BaseModel):
    identifier: str = Field(max_length=255)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8)


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
    accessories: str | None = None
    device_condition: str | None = None
    prepayment: float | None = None
    subtotal_before_discount: float | None = None
    discount_total: float | None = None
    total_cost: float | None = None
    completed_at: datetime | str | None = None


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


class MobileDeviceRegisterRequest(BaseModel):
    platform: Literal["ios", "android", "web"]
    device_uid: str
    push_token: str | None = None
    app_version: str | None = None
    locale: str | None = None


class MobileDeviceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    device_uid: str
    app_version: str
    locale: str
    is_active: bool
    last_seen_at: datetime | None = None


class PushTestRequest(BaseModel):
    title: str = "Repair CRM"
    body: str = "Проверка push-уведомлений"
    payload: dict[str, Any] = {}


class CustomerSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_agent: str
    ip_address: str
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime
    last_seen_at: datetime | None = None


class SyncMarketingRequest(BaseModel):
    tenant_key: str | None = None
    sent_at: datetime | None = None
    promotions: list[dict[str, Any]] = Field(default_factory=list)
    banner: dict[str, Any] | None = None


class SyncMarketingResponse(BaseModel):
    ok: bool = True
    promotions_count: int = 0
    has_banner: bool = False
