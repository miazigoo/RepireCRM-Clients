"""Tests for profile and contact management (/api/portal/me/*)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, get_latest_debug_code, register_customer


# ──────────────────────────────────────────────────────────────────────────────
# Profile read
# ──────────────────────────────────────────────────────────────────────────────


def test_get_profile(client: TestClient) -> None:
    data = register_customer(client, email="me@example.com")
    r = client.get("/api/portal/me", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["first_name"] == "Тест"


def test_get_profile_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/portal/me")
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Profile update
# ──────────────────────────────────────────────────────────────────────────────


def test_update_profile_name(client: TestClient) -> None:
    data = register_customer(client, email="upd@example.com")
    r = client.patch(
        "/api/portal/me",
        headers=auth_headers(data["access_token"]),
        json={"first_name": "Иван", "last_name": "Сидоров"},
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "Иван"
    assert r.json()["last_name"] == "Сидоров"


def test_update_marketing_consent(client: TestClient) -> None:
    data = register_customer(client, email="mkt2@example.com", marketing_consent=False)
    r = client.patch(
        "/api/portal/me",
        headers=auth_headers(data["access_token"]),
        json={"marketing_consent": True},
    )
    assert r.status_code == 200
    assert r.json()["marketing_consent"] is True


def test_update_profile_partial(client: TestClient) -> None:
    """Only supplied fields should change."""
    data = register_customer(
        client, first_name="Оля", last_name="Кузнецова", email="partial@example.com"
    )
    r = client.patch(
        "/api/portal/me",
        headers=auth_headers(data["access_token"]),
        json={"first_name": "Ольга"},
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "Ольга"
    assert r.json()["last_name"] == "Кузнецова"


def test_update_profile_xss_sanitized(client: TestClient) -> None:
    data = register_customer(client, email="xss2@example.com")
    r = client.patch(
        "/api/portal/me",
        headers=auth_headers(data["access_token"]),
        json={"first_name": "<script>alert(1)</script>Максим"},
    )
    assert r.status_code == 200
    assert "<script" not in r.json()["first_name"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# Contact management
# ──────────────────────────────────────────────────────────────────────────────


def test_add_email_contact(client: TestClient, db: Session) -> None:
    data = register_customer(client, email=None, phone="+79990001111")
    token = data["access_token"]

    r = client.post(
        "/api/portal/me/contacts",
        headers=auth_headers(token),
        json={"type": "email", "value": "new@example.com"},
    )
    assert r.status_code == 201  # ChallengeResponse
    # Fetch updated profile to see contacts
    profile = client.get("/api/portal/me", headers=auth_headers(token)).json()
    assert any(c["value"] == "new@example.com" for c in profile["contacts"])


def test_verify_contact_correct_code(client: TestClient, db: Session) -> None:
    data = register_customer(client, email=None, phone="+79990002222")
    token = data["access_token"]

    client.post(
        "/api/portal/me/contacts",
        headers=auth_headers(token),
        json={"type": "email", "value": "verify@example.com"},
    )

    code = get_latest_debug_code(db)
    r = client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": "verify@example.com", "code": code},
    )
    assert r.status_code == 200
    verified = [c for c in r.json()["contacts"] if c["value"] == "verify@example.com"]
    assert verified[0]["verified_at"] is not None


def test_verify_contact_wrong_code(client: TestClient, db: Session) -> None:
    data = register_customer(client, email=None, phone="+79990003333")
    token = data["access_token"]

    client.post(
        "/api/portal/me/contacts",
        headers=auth_headers(token),
        json={"type": "email", "value": "badcode@example.com"},
    )
    r = client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": "badcode@example.com", "code": "000000"},
    )
    assert r.status_code == 400


def test_add_phone_contact_to_email_registered_user(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="addphone@example.com")
    token = data["access_token"]

    r = client.post(
        "/api/portal/me/contacts",
        headers=auth_headers(token),
        json={"type": "phone", "value": "+79990004444"},
    )
    assert r.status_code == 201  # endpoint returns 201 Created
    # Fetch updated profile to see contacts
    profile = client.get("/api/portal/me", headers=auth_headers(token)).json()
    assert any(c["type"] == "phone" for c in profile["contacts"])


def test_duplicate_contact_returns_409(client: TestClient, db: Session) -> None:
    """A contact already owned by another user cannot be added."""
    register_customer(client, email="owner@example.com")
    data2 = register_customer(client, email="other@example.com")
    token2 = data2["access_token"]

    r = client.post(
        "/api/portal/me/contacts",
        headers=auth_headers(token2),
        json={"type": "email", "value": "owner@example.com"},
    )
    assert r.status_code == 409


def test_request_verification_sends_code(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="coderequest@example.com")
    token = data["access_token"]

    # Request fresh verification code
    r = client.post(
        "/api/portal/me/contacts/request-verification",
        headers=auth_headers(token),
        json={"type": "email", "value": "coderequest@example.com"},
    )
    assert r.status_code == 200
    # In debug mode code is returned
    assert r.json().get("debug_code") or get_latest_debug_code(db)


# ──────────────────────────────────────────────────────────────────────────────
# Sessions list
# ──────────────────────────────────────────────────────────────────────────────


def test_list_sessions(client: TestClient) -> None:
    data = register_customer(client, email="sess@example.com")
    token = data["access_token"]

    r = client.get("/api/mobile/sessions", headers=auth_headers(token))
    assert r.status_code == 200
    sessions = r.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
