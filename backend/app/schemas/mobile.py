from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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
