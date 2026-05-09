"""Unit tests for service helpers, security utilities and sanitization.

These tests do NOT start the HTTP server — they call Python functions directly.
"""

from __future__ import annotations

import pytest

from app.sanitization import sanitize_optional_text, sanitize_plain_text
from app.security import (
    create_access_token,
    detect_identity_type,
    generate_code,
    hash_password,
    normalize_email,
    normalize_phone,
    parse_access_token,
    validate_password,
    verify_password,
)


# ──────────────────────────────────────────────────────────────────────────────
# Phone normalisation
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+79991234567", "+79991234567"),
        ("79991234567", "+79991234567"),
        ("89991234567", "+79991234567"),
        ("9991234567", "+79991234567"),
        ("+7 (999) 123-45-67", "+79991234567"),
        ("8 (999) 123-45-67", "+79991234567"),
    ],
)
def test_normalize_phone_valid(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("bad", ["123", "not-a-phone", "000"])
def test_normalize_phone_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(bad)


# ──────────────────────────────────────────────────────────────────────────────
# Email normalisation
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("User@Example.COM", "user@example.com"),
        ("  test@test.ru  ", "test@test.ru"),
        ("a+tag@domain.org", "a+tag@domain.org"),
    ],
)
def test_normalize_email_valid(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("bad", ["notanemail", "@nodomain", "user@", "a@b"])
def test_normalize_email_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_email(bad)


# ──────────────────────────────────────────────────────────────────────────────
# Identity type detection
# ──────────────────────────────────────────────────────────────────────────────


def test_detect_email() -> None:
    assert detect_identity_type("user@example.com") == "email"


def test_detect_phone() -> None:
    assert detect_identity_type("+79991234567") == "phone"


# ──────────────────────────────────────────────────────────────────────────────
# Password hashing
# ──────────────────────────────────────────────────────────────────────────────


def test_hash_and_verify_password() -> None:
    hashed = hash_password("Secure1!")
    assert verify_password("Secure1!", hashed)
    assert not verify_password("Wrong1!", hashed)


def test_hash_password_is_salted() -> None:
    h1 = hash_password("SamePass1!")
    h2 = hash_password("SamePass1!")
    assert h1 != h2  # different salts


def test_verify_password_wrong_format() -> None:
    assert not verify_password("anything", "not_a_valid_hash")


# ──────────────────────────────────────────────────────────────────────────────
# Password validation
# ──────────────────────────────────────────────────────────────────────────────


def test_password_too_short_raises() -> None:
    with pytest.raises(ValueError):
        validate_password("Sh0rt!")


def test_password_all_digits_raises() -> None:
    with pytest.raises(ValueError):
        validate_password("12345678")


def test_password_all_letters_raises() -> None:
    with pytest.raises(ValueError):
        validate_password("onlyletter")


def test_valid_password_passes() -> None:
    validate_password("Valid1Pass!")  # should not raise


# ──────────────────────────────────────────────────────────────────────────────
# Token creation / parsing
# ──────────────────────────────────────────────────────────────────────────────


def test_create_and_parse_token() -> None:
    from app.config import Settings

    settings = Settings(secret_key="a-strong-test-secret-key-32chars!!")
    token = create_access_token(42, settings)
    customer_id = parse_access_token(token, settings)
    assert customer_id == 42


def test_parse_token_wrong_secret_raises() -> None:
    from app.config import Settings
    from app.security import AuthError

    s1 = Settings(secret_key="a-strong-test-secret-key-32chars!!")
    s2 = Settings(secret_key="another-strong-test-secret-key-99")
    token = create_access_token(1, s1)
    with pytest.raises(AuthError):
        parse_access_token(token, s2)


def test_generate_code_is_six_digits() -> None:
    code = generate_code()
    assert len(code) == 6
    assert code.isdigit()


# ──────────────────────────────────────────────────────────────────────────────
# Sanitization
# ──────────────────────────────────────────────────────────────────────────────


def test_sanitize_plain_text_strips_html() -> None:
    assert "<script>" not in sanitize_plain_text("<script>alert(1)</script>Hello")
    assert "Hello" in sanitize_plain_text("<b>Hello</b>")


def test_sanitize_plain_text_max_length() -> None:
    result = sanitize_plain_text("a" * 200, max_length=50)
    assert len(result) == 50


def test_sanitize_plain_text_strips_whitespace() -> None:
    assert sanitize_plain_text("  hello  ") == "hello"


def test_sanitize_plain_text_removes_control_chars() -> None:
    result = sanitize_plain_text("hel\x00lo\x1bworld")
    assert "\x00" not in result
    assert "\x1b" not in result


def test_sanitize_optional_text_none_returns_none() -> None:
    assert sanitize_optional_text(None) is None


def test_sanitize_optional_text_empty_returns_none() -> None:
    assert sanitize_optional_text("   ") is None


def test_sanitize_optional_text_strips_tags() -> None:
    result = sanitize_optional_text("<img src=x onerror=evil()>text")
    assert result is not None
    assert "onerror" not in result.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Config validation
# ──────────────────────────────────────────────────────────────────────────────


def test_config_production_rejects_weak_secret() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        from app.config import Settings

        Settings(
            environment="production",
            secret_key="dev-secret-change-me",
            sync_api_key="a" * 25,
            database_url="postgresql://x:x@localhost/x",
            cors_origins="https://example.com",
        )


def test_config_production_rejects_sqlite() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        from app.config import Settings

        Settings(
            environment="production",
            secret_key="A" * 40,
            sync_api_key="B" * 30,
            database_url="sqlite:///./test.db",
            cors_origins="https://example.com",
        )


def test_config_production_rejects_wildcard_cors() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        from app.config import Settings

        Settings(
            environment="production",
            secret_key="A" * 40,
            sync_api_key="B" * 30,
            database_url="postgresql://x:x@localhost/x",
            cors_origins="*",
        )


# ──────────────────────────────────────────────────────────────────────────────
# validate_registration_contacts
# ──────────────────────────────────────────────────────────────────────────────


def test_registration_contacts_phone_policy() -> None:
    from app.config import Settings
    from app.services import validate_registration_contacts

    settings = Settings(
        secret_key="a-strong-test-secret-key-32chars!!",
        auth_policy="phone_only",
    )
    # returns list[tuple[type, raw, normalized]]
    contacts = validate_registration_contacts(settings, "+79991234567", None)
    assert contacts[0][0] == "phone"


def test_registration_contacts_email_policy() -> None:
    from app.config import Settings
    from app.services import validate_registration_contacts

    settings = Settings(
        secret_key="a-strong-test-secret-key-32chars!!",
        auth_policy="email_only",
    )
    contacts = validate_registration_contacts(settings, None, "user@example.com")
    assert contacts[0][0] == "email"


def test_registration_contacts_phone_only_rejects_email() -> None:
    from app.config import Settings
    from app.services import validate_registration_contacts
    from fastapi import HTTPException

    settings = Settings(
        secret_key="a-strong-test-secret-key-32chars!!",
        auth_policy="phone_only",
    )
    with pytest.raises(HTTPException):
        validate_registration_contacts(settings, None, "user@example.com")
