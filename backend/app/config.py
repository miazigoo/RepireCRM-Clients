from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthPolicy = Literal["phone_or_email", "phone_only", "email_only"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLIENT_PORTAL_",
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://repaircrm_client:repaircrm_client@127.0.0.1:55440/repaircrm_client"
    )
    secret_key: str = Field(default="dev-secret-key-change-me-use-32chars!", min_length=32)
    sync_api_key: str = "dev-sync-token"
    environment: Literal["development", "test", "production"] = "development"
    tenant_key: str = "default"
    token_ttl_minutes: int = 60 * 24 * 30
    refresh_token_ttl_days: int = 60
    verification_ttl_minutes: int = 15
    password_reset_ttl_minutes: int = 30
    auth_policy: AuthPolicy = "phone_or_email"
    require_verified_contact_for_orders: bool = True
    delivery_debug: bool = True
    cors_origins: str = "*"
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_default_limit: int = 120
    rate_limit_auth_limit: int = 20
    redis_url: str = "redis://127.0.0.1:56379/0"

    brand_name: str = "Repair CRM"
    accent_color: str = "#0f766e"
    logo_url: str | None = None
    support_phone: str | None = None
    support_email: str | None = None

    crm_base_url: str | None = Field(
        default=None,
        description=("Базовый URL Repair CRM; точки лендинга: GET …/portal-public-shops."),
    )
    crm_api_key: str | None = Field(
        default=None,
        description="Обычно тот же ключ, что X-Sync-Token в интеграции с порталом.",
    )
    crm_tenant_key: str | None = Field(
        default=None,
        description="Иначе tenant_key; должен совпадать с X-Tenant-Key в CRM.",
    )
    sync_worker_interval_seconds: int = 60
    sync_worker_batch_size: int = 100

    mobile_push_enabled: bool = False
    mobile_push_provider: Literal["stub", "fcm", "apns"] = "stub"
    mobile_push_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment != "production":
            return self
        weak_secret_values = {
            "dev-secret-change-me",
            "change-me-in-production",
            "CHANGE_WITH_MAKE_GENERATE_SECRETS",
        }
        weak_sync_values = {
            "dev-sync-token",
            "change-me-sync-token",
            "CHANGE_WITH_MAKE_GENERATE_SECRETS",
        }
        if self.secret_key in weak_secret_values or len(self.secret_key) < 32:
            raise ValueError("CLIENT_PORTAL_SECRET_KEY must be strong in production")
        if self.sync_api_key in weak_sync_values or len(self.sync_api_key) < 24:
            raise ValueError("CLIENT_PORTAL_SYNC_API_KEY must be strong in production")
        if self.delivery_debug:
            raise ValueError("CLIENT_PORTAL_DELIVERY_DEBUG must be false in production")
        if self.database_url.startswith("sqlite"):
            raise ValueError("CLIENT_PORTAL_DATABASE_URL must use Postgres in production")
        if self.cors_origins.strip() == "*":
            raise ValueError("CLIENT_PORTAL_CORS_ORIGINS must be explicit in production")
        if (
            self.mobile_push_enabled
            and self.mobile_push_provider != "stub"
            and not self.mobile_push_api_key
        ):
            raise ValueError(
                "CLIENT_PORTAL_MOBILE_PUSH_API_KEY is required when mobile push is enabled"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
