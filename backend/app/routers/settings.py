from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..schemas import AuthSettings, BrandSettings, PortalSettingsResponse

router = APIRouter(prefix="/api/portal", tags=["portal-settings"])


@router.get("/settings", response_model=PortalSettingsResponse)
def portal_settings(settings: Settings = Depends(get_settings)) -> PortalSettingsResponse:
    return PortalSettingsResponse(
        brand=BrandSettings(
            name=settings.brand_name,
            accent_color=settings.accent_color,
            logo_url=settings.logo_url,
            support_phone=settings.support_phone,
            support_email=settings.support_email,
        ),
        auth=AuthSettings(
            policy=settings.auth_policy,
            allow_phone=settings.auth_policy in {"phone_or_email", "phone_only"},
            allow_email=settings.auth_policy in {"phone_or_email", "email_only"},
            require_verified_contact_for_orders=settings.require_verified_contact_for_orders,
        ),
        features={
            "orders": True,
            "order_create": True,
            "approvals": True,
            "password_reset": True,
            "contact_verification": True,
            "mobile_sessions": True,
            "mobile_push": settings.mobile_push_enabled,
        },
    )
