from pydantic import BaseModel, Field, field_validator, model_validator

from ..sanitization import sanitize_optional_text, sanitize_plain_text
from .customer import PortalCustomerSchema


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


class PasswordResetRequest(BaseModel):
    identifier: str = Field(max_length=255)


class PasswordResetConfirmRequest(BaseModel):
    identifier: str = Field(max_length=255)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8)


class ChallengeResponse(BaseModel):
    message: str
    delivery_id: int | None = None
    debug_code: str | None = None
