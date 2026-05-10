from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import AuthPolicy


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


class FieldVisitZoneSchema(BaseModel):
    id: str
    name: str
    price: float = 0.0
    geometry: dict[str, Any]


class FieldVisitSettingsSchema(BaseModel):
    enabled: bool = False
    service_name: str = "Выезд мастера"
    base_price: float = 0.0
    out_of_zone_price: float = 0.0
    description: str = ""
    zones: list[FieldVisitZoneSchema] = []
    advance_days: int = 1


class PortalPublicLocationSchema(BaseModel):
    """Публичная точка сервиса для лендинга и карты (синхр. из CRM)."""

    model_config = ConfigDict(extra="ignore")

    crm_shop_id: int = 0
    name: str
    code: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    lat: float | None = None
    lng: float | None = None


class LandingFeatureCardSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    body: str
    icon: str = "status"


class LandingPromoSpotlightSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    title: str = ""
    subtitle: str = ""
    body: str = ""
    badge: str = ""
    cta_label: str = ""
    cta_href: str = ""
    image_url: str | None = None


class PortalLandingContentSchema(BaseModel):
    """Тексты карточек и акцентный баннер лендинга (из CRM)."""

    section_eyebrow: str = ""
    section_title: str = ""
    section_subtitle: str = ""
    feature_cards: list[LandingFeatureCardSchema] = []
    promo_spotlight: LandingPromoSpotlightSchema = Field(
        default_factory=LandingPromoSpotlightSchema
    )


class PortalSettingsResponse(BaseModel):
    brand: BrandSettings
    auth: AuthSettings
    features: dict[str, bool]
    marketing: PortalMarketingSchema
    field_visit: FieldVisitSettingsSchema | None = None
    locations: list[PortalPublicLocationSchema] = []
    landing: PortalLandingContentSchema = Field(default_factory=PortalLandingContentSchema)
