from typing import Any, Literal

from pydantic import BaseModel

AuthPolicy = Literal["phone_or_email", "phone_only", "email_only"]


class ApiError(BaseModel):
    error: str
    details: dict[str, Any] | None = None
