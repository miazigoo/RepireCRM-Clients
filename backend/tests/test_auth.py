"""Tests for authentication endpoints (/api/portal/auth/*)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, get_latest_debug_code, register_customer


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────


def test_register_with_email(client: TestClient) -> None:
    r = register_customer(client, email="anna@example.com")
    assert r["access_token"]
    assert r["refresh_token"]
    assert r["customer"]["email"] == "anna@example.com"
    assert r["customer"]["first_name"] == "Тест"


def test_register_with_phone(client: TestClient) -> None:
    r = register_customer(client, email=None, phone="+79991234567")
    assert r["customer"]["phone"] == "+79991234567"


def test_register_phone_normalised(client: TestClient) -> None:
    """8-format phone is normalized to +7 in the stored contact."""
    r = register_customer(client, email=None, phone="89161234567")
    # The customer schema exposes the phone field from normalized identity value
    contacts = r["customer"]["contacts"]
    normalized = next((c["normalized_value"] for c in contacts if c["type"] == "phone"), None)
    assert normalized == "+79161234567"


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    register_customer(client, email="dup@example.com")
    r2 = client.post(
        "/api/portal/auth/register",
        json={
            "first_name": "X",
            "last_name": "Y",
            "email": "dup@example.com",
            "password": "Test1234!",
        },
    )
    assert r2.status_code == 409


def test_register_duplicate_phone_returns_409(client: TestClient) -> None:
    register_customer(client, email=None, phone="+79991112233")
    r2 = client.post(
        "/api/portal/auth/register",
        json={
            "first_name": "X",
            "last_name": "Y",
            "phone": "+79991112233",
            "password": "Test1234!",
        },
    )
    assert r2.status_code == 409


def test_register_requires_identifier(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/register",
        json={"first_name": "X", "last_name": "Y", "password": "Test1234!"},
    )
    assert r.status_code in (400, 422)


def test_register_weak_password_returns_422(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/register",
        json={"first_name": "X", "last_name": "Y", "email": "x@x.com", "password": "short"},
    )
    assert r.status_code == 422


def test_register_all_digits_password_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/register",
        json={"first_name": "X", "last_name": "Y", "email": "x@x.com", "password": "12345678"},
    )
    assert r.status_code == 422  # Pydantic field_validator rejects all-digit passwords


def test_register_all_letters_password_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/register",
        json={
            "first_name": "X",
            "last_name": "Y",
            "email": "x@x.com",
            "password": "onlyletters",
        },
    )
    assert r.status_code == 422


def test_register_marketing_consent_stored(client: TestClient) -> None:
    r = register_customer(client, email="mkt@example.com", marketing_consent=True)
    assert r["customer"]["marketing_consent"] is True


# ──────────────────────────────────────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────────────────────────────────────


def test_login_with_email(client: TestClient) -> None:
    register_customer(client, email="login@example.com", password="Test1234!")
    r = client.post(
        "/api/portal/auth/login",
        json={"identifier": "login@example.com", "password": "Test1234!"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_case_insensitive_email(client: TestClient) -> None:
    register_customer(client, email="Upper@Example.COM", password="Test1234!")
    r = client.post(
        "/api/portal/auth/login",
        json={"identifier": "upper@example.com", "password": "Test1234!"},
    )
    assert r.status_code == 200


def test_login_with_phone_field(client: TestClient) -> None:
    register_customer(client, email=None, phone="+79990001122", password="Test1234!")
    r = client.post(
        "/api/portal/auth/login",
        json={"phone": "+79990001122", "password": "Test1234!"},
    )
    assert r.status_code == 200


def test_login_wrong_password(client: TestClient) -> None:
    register_customer(client, email="pw@example.com", password="Test1234!")
    r = client.post(
        "/api/portal/auth/login",
        json={"identifier": "pw@example.com", "password": "WrongPass9!"},
    )
    # App uses 400 for invalid credentials (avoids browser native-auth prompt)
    assert r.status_code == 400


def test_login_unknown_user(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/login",
        json={"identifier": "nobody@example.com", "password": "Test1234!"},
    )
    assert r.status_code == 400


def test_login_no_identifier_returns_422(client: TestClient) -> None:
    r = client.post("/api/portal/auth/login", json={"password": "Test1234!"})
    assert r.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# Token refresh
# ──────────────────────────────────────────────────────────────────────────────


def test_refresh_token_returns_new_access_token(client: TestClient) -> None:
    data = register_customer(client, email="refresh@example.com")
    r = client.post(
        "/api/portal/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_refresh_with_invalid_token(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/refresh",
        json={"refresh_token": "a" * 64},
    )
    assert r.status_code == 401


def test_refresh_with_short_token_422(client: TestClient) -> None:
    r = client.post("/api/portal/auth/refresh", json={"refresh_token": "tooshort"})
    assert r.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# Logout
# ──────────────────────────────────────────────────────────────────────────────


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    data = register_customer(client, email="logout@example.com")
    logout = client.post(
        "/api/portal/auth/logout",
        json={"refresh_token": data["refresh_token"]},
    )
    assert logout.status_code == 204

    # After logout refresh must be rejected
    r = client.post(
        "/api/portal/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert r.status_code == 401


def test_logout_does_not_invalidate_existing_access_token(client: TestClient) -> None:
    """Access token remains valid until expiry even after logout."""
    data = register_customer(client, email="access_after_logout@example.com")
    client.post(
        "/api/portal/auth/logout",
        json={"refresh_token": data["refresh_token"]},
    )
    # Access token still works
    r = client.get(
        "/api/portal/me",
        headers=auth_headers(data["access_token"]),
    )
    assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Token integrity
# ──────────────────────────────────────────────────────────────────────────────


def test_tampered_access_token_rejected(client: TestClient) -> None:
    data = register_customer(client, email="tamper@example.com")
    token = data["access_token"]
    tampered = token[:-5] + ("X" * 5)
    r = client.get("/api/portal/me", headers=auth_headers(tampered))
    assert r.status_code == 401


def test_expired_access_token_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Create a token with a past expiry time."""
    import app.security as sec_mod

    # Freeze time 1 hour in the past so the token is born expired
    past = time.time() - 3601

    original_utcnow = sec_mod.utcnow

    def _past_utcnow():
        from datetime import datetime, timezone

        return datetime.fromtimestamp(past, tz=timezone.utc)

    monkeypatch.setattr(sec_mod, "utcnow", _past_utcnow)

    from app.config import get_settings

    token = sec_mod.create_access_token(999, get_settings())

    monkeypatch.setattr(sec_mod, "utcnow", original_utcnow)

    r = client.get("/api/portal/me", headers=auth_headers(token))
    assert r.status_code == 401


def test_missing_bearer_returns_401(client: TestClient) -> None:
    r = client.get("/api/portal/me")
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Password reset
# ──────────────────────────────────────────────────────────────────────────────


def test_password_reset_full_flow(client: TestClient, db: Session) -> None:
    """Password reset works only when the identity is verified."""

    data = register_customer(client, email="reset@example.com", password="OldPass1!")
    token = data["access_token"]

    # Must verify email first so reset code is sent
    client.post(
        "/api/portal/me/contacts/request-verification",
        headers=auth_headers(token),
        json={"type": "email", "value": "reset@example.com"},
    )
    v_code = get_latest_debug_code(db)
    client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": "reset@example.com", "code": v_code},
    )

    req = client.post(
        "/api/portal/auth/password/request-reset",
        json={"identifier": "reset@example.com"},
    )
    assert req.status_code == 202
    code = req.json()["debug_code"]
    assert code is not None

    confirm = client.post(
        "/api/portal/auth/password/confirm-reset",
        json={
            "identifier": "reset@example.com",
            "code": code,
            "new_password": "NewPass2!",
        },
    )
    assert confirm.status_code == 200

    login = client.post(
        "/api/portal/auth/login",
        json={"identifier": "reset@example.com", "password": "NewPass2!"},
    )
    assert login.status_code == 200


def test_password_reset_wrong_code(client: TestClient) -> None:
    register_customer(client, email="reset2@example.com", password="OldPass1!")
    client.post(
        "/api/portal/auth/password/request-reset",
        json={"identifier": "reset2@example.com"},
    )
    confirm = client.post(
        "/api/portal/auth/password/confirm-reset",
        json={
            "identifier": "reset2@example.com",
            "code": "000000",
            "new_password": "NewPass2!",
        },
    )
    assert confirm.status_code == 400


def test_password_reset_unknown_identifier(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/password/request-reset",
        json={"identifier": "ghost@example.com"},
    )
    # Should not leak whether user exists — 202 or 404 both acceptable
    assert r.status_code in (202, 404)


def test_old_password_rejected_after_reset(client: TestClient, db: Session) -> None:
    from tests.conftest import get_latest_debug_code

    data = register_customer(client, email="oldpw@example.com", password="OldPass1!")
    token = data["access_token"]

    # Verify email first
    client.post(
        "/api/portal/me/contacts/request-verification",
        headers=auth_headers(token),
        json={"type": "email", "value": "oldpw@example.com"},
    )
    v_code = get_latest_debug_code(db)
    client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": "oldpw@example.com", "code": v_code},
    )

    req = client.post(
        "/api/portal/auth/password/request-reset",
        json={"identifier": "oldpw@example.com"},
    )
    code = req.json()["debug_code"]
    client.post(
        "/api/portal/auth/password/confirm-reset",
        json={
            "identifier": "oldpw@example.com",
            "code": code,
            "new_password": "NewPass2!",
        },
    )
    r = client.post(
        "/api/portal/auth/login",
        json={"identifier": "oldpw@example.com", "password": "OldPass1!"},
    )
    assert r.status_code == 400  # app uses 400 for bad credentials
