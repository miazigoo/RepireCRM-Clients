from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
    avatar_url: str | None = None
    contacts: list[ContactSchema] = []
