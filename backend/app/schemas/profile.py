from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..sanitization import sanitize_optional_text


class ContactCreateRequest(BaseModel):
    type: Literal["phone", "email"]
    value: str
    make_primary: bool = True


class VerificationRequest(BaseModel):
    type: Literal["phone", "email"]
    value: str


class VerificationConfirmRequest(VerificationRequest):
    code: str = Field(min_length=4, max_length=12)


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    marketing_consent: bool | None = None

    @field_validator("first_name", "last_name", "middle_name", mode="before")
    @classmethod
    def sanitize_profile_text(cls, value):
        return sanitize_optional_text(value, max_length=80)
