"""Tests for mobile device registration, push notifications and sessions."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, register_customer


# ──────────────────────────────────────────────────────────────────────────────
# Device registration
# ──────────────────────────────────────────────────────────────────────────────


def test_register_device(client: TestClient) -> None:
    data = register_customer(client, email="dev@example.com")
    token = data["access_token"]

    r = client.post(
        "/api/mobile/devices",
        headers=auth_headers(token),
        json={"platform": "ios", "device_uid": "dev-aaa", "push_token": "ptok-1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["platform"] == "ios"
    assert body["is_active"] is True


def test_register_device_idempotent(client: TestClient, db: Session) -> None:
    """Re-registering the same device_uid should not create a duplicate row."""
    data = register_customer(client, email="idem@example.com")
    token = data["access_token"]

    payload = {"platform": "android", "device_uid": "dev-bbb", "push_token": "tok-1"}
    client.post("/api/mobile/devices", headers=auth_headers(token), json=payload)
    client.post(
        "/api/mobile/devices",
        headers=auth_headers(token),
        json={**payload, "push_token": "tok-2"},
    )

    from app.models import MobileDevice

    rows = db.scalars(select(MobileDevice).where(MobileDevice.device_uid == "dev-bbb")).all()
    assert len(rows) == 1
    assert rows[0].push_token == "tok-2"


def test_register_device_different_platforms(client: TestClient) -> None:
    data = register_customer(client, email="platforms@example.com")
    token = data["access_token"]

    for platform, uid in [("ios", "uid-ios"), ("android", "uid-android"), ("web", "uid-web")]:
        r = client.post(
            "/api/mobile/devices",
            headers=auth_headers(token),
            json={"platform": platform, "device_uid": uid},
        )
        assert r.status_code == 200


def test_register_device_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/api/mobile/devices",
        json={"platform": "ios", "device_uid": "no-auth"},
    )
    assert r.status_code == 401


def test_register_device_invalid_platform(client: TestClient) -> None:
    data = register_customer(client, email="badplat@example.com")
    r = client.post(
        "/api/mobile/devices",
        headers=auth_headers(data["access_token"]),
        json={"platform": "windows_phone", "device_uid": "bad-uid"},
    )
    assert r.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# Push notifications test
# ──────────────────────────────────────────────────────────────────────────────


def test_push_test_queues_notification(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="push@example.com")
    token = data["access_token"]

    client.post(
        "/api/mobile/devices",
        headers=auth_headers(token),
        json={"platform": "android", "device_uid": "push-dev", "push_token": "push-tok"},
    )

    r = client.post(
        "/api/mobile/push/test",
        headers=auth_headers(token),
        json={"title": "Тест", "body": "Проверка уведомлений", "payload": {"order": "R-001"}},
    )
    assert r.status_code == 200
    assert r.json()["queued"] == 1

    from app.models import PushNotification

    notifs = db.scalars(select(PushNotification)).all()
    assert len(notifs) == 1
    assert notifs[0].title == "Тест"


def test_push_test_no_devices_queues_zero(client: TestClient) -> None:
    data = register_customer(client, email="push0@example.com")
    token = data["access_token"]

    r = client.post(
        "/api/mobile/push/test",
        headers=auth_headers(token),
        json={"title": "Hi", "body": "Test"},
    )
    assert r.status_code == 200
    assert r.json()["queued"] == 0


def test_push_test_requires_auth(client: TestClient) -> None:
    r = client.post("/api/mobile/push/test", json={"title": "Hi", "body": "Test"})
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Sessions
# ──────────────────────────────────────────────────────────────────────────────


def test_list_sessions_shows_current_session(client: TestClient) -> None:
    data = register_customer(client, email="sess2@example.com")
    token = data["access_token"]

    r = client.get("/api/mobile/sessions", headers=auth_headers(token))
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) >= 1


def test_list_sessions_grows_after_new_login(client: TestClient) -> None:
    register_customer(client, email="sess3@example.com", password="Test1234!")
    client.post(
        "/api/portal/auth/login",
        json={"identifier": "sess3@example.com", "password": "Test1234!"},
    )
    login2 = client.post(
        "/api/portal/auth/login",
        json={"identifier": "sess3@example.com", "password": "Test1234!"},
    )
    token = login2.json()["access_token"]

    r = client.get("/api/mobile/sessions", headers=auth_headers(token))
    sessions = r.json()
    # At least 3 sessions: register + 2 logins
    assert len(sessions) >= 3


def test_sessions_require_auth(client: TestClient) -> None:
    r = client.get("/api/mobile/sessions")
    assert r.status_code == 401
