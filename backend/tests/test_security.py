"""Tests for security: HTTP headers, XSS sanitization, rate limiting, tokens."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_customer


# ──────────────────────────────────────────────────────────────────────────────
# HTTP security headers
# ──────────────────────────────────────────────────────────────────────────────


def test_security_headers_on_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    csp = r.headers.get("content-security-policy", "")
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp


def test_security_headers_on_api_endpoint(client: TestClient) -> None:
    r = client.get("/api/portal/settings")
    assert r.headers.get("x-content-type-options") == "nosniff"


# ──────────────────────────────────────────────────────────────────────────────
# XSS sanitisation
# ──────────────────────────────────────────────────────────────────────────────


def test_xss_stripped_from_first_last_name(client: TestClient) -> None:
    r = client.post(
        "/api/portal/auth/register",
        json={
            "first_name": "<img src=x onerror=alert(1)>Иван",
            "last_name": "<script>steal()</script>Петров",
            "email": "xss1@example.com",
            "password": "Test1234!",
        },
    )
    assert r.status_code == 201
    c = r.json()["customer"]
    assert "<" not in c["first_name"]
    assert "onerror" not in c["first_name"].lower()
    assert "<script" not in c["last_name"].lower()


def test_xss_stripped_from_order_fields(client: TestClient) -> None:
    data = register_customer(client, email="xss2@example.com")
    r = client.post(
        "/api/portal/orders",
        headers=auth_headers(data["access_token"]),
        json={
            "device_type": "Телефон",
            "brand": "<img src=x onerror=alert(1)>Apple",
            "model_name": "iPhone <script>alert(1)</script>",
            "problem_description": "<script>alert(1)</script>Не включается после падения",
            "cost_estimate": 0,
        },
    )
    assert r.status_code == 201
    order = r.json()
    assert "<script" not in order["problem_description"].lower()
    assert "onerror" not in order["device_title"].lower()
    assert "<" not in order["device_title"]


def test_xss_stripped_from_profile_update(client: TestClient) -> None:
    data = register_customer(client, email="xss3@example.com")
    r = client.patch(
        "/api/portal/me",
        headers=auth_headers(data["access_token"]),
        json={"first_name": "<b>Иван</b>", "last_name": "<em>Иванов</em>"},
    )
    assert r.status_code == 200
    assert "<b>" not in r.json()["first_name"]
    assert "<em>" not in r.json()["last_name"]


def test_xss_stripped_from_marketing_banner(client: TestClient) -> None:
    client.post(
        "/api/sync/marketing/upsert",
        headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
        json={
            "promotions": [],
            "banner": {
                "title": "<script>alert(1)</script>Акция",
                "subtitle": "<img src=x onerror=evil()>Скидки",
                "active": True,
            },
        },
    )
    settings = client.get("/api/portal/settings").json()
    banner = settings["marketing"]["banner"]
    assert banner is not None
    assert "<script" not in banner["title"].lower()
    assert "onerror" not in banner["subtitle"].lower()


def test_xss_stripped_from_approval_comment(client: TestClient) -> None:
    """Approval comment is sanitized before being stored."""
    from tests.conftest import get_latest_debug_code

    from app.main import app
    from fastapi.testclient import TestClient as _TC

    with _TC(app) as c:
        data = register_customer(c, email="xssappr@example.com")
        token = data["access_token"]

        c.post(
            "/api/portal/me/contacts/request-verification",
            headers=auth_headers(token),
            json={"type": "email", "value": "xssappr@example.com"},
        )
        from app.database import SessionLocal

        with SessionLocal() as db:
            code = get_latest_debug_code(db)

        c.post(
            "/api/portal/me/contacts/confirm",
            headers=auth_headers(token),
            json={"type": "email", "value": "xssappr@example.com", "code": code},
        )

        c.post(
            "/api/sync/orders/upsert",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
            json={
                "tenant_key": "default",
                "orders": [
                    {
                        "crm_order_id": 300,
                        "order_number": "R-300",
                        "customer": {"email": "xssappr@example.com"},
                        "device": {"brand": "LG", "model_name": "G8"},
                        "status": "diagnosed",
                        "status_display": "Диагностика",
                        "problem_description": "Экран мигает",
                        "cost_estimate": "4000",
                        "remaining_payment": "4000",
                        "approvals": [
                            {
                                "crm_approval_id": 600,
                                "title": "Ремонт матрицы",
                                "amount": "4000",
                                "status": "pending",
                                "created_at": "2026-05-01T10:00:00Z",
                            }
                        ],
                    }
                ],
            },
        )

        r = c.post(
            "/api/portal/approvals/600/approve",
            headers=auth_headers(token),
            json={"comment": "<script>alert(1)</script>Согласовано"},
        )
        assert r.status_code == 200

        from sqlalchemy import select
        from app.models import ClientAction

        with SessionLocal() as db:
            action = db.scalar(select(ClientAction).order_by(ClientAction.id.desc()))
        assert action is not None
        comment = action.payload.get("comment", "")
        assert "<script" not in comment.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Token edge cases
# ──────────────────────────────────────────────────────────────────────────────


def test_tampered_signature_rejected(client: TestClient) -> None:
    data = register_customer(client, email="tamper2@example.com")
    token = data["access_token"]
    body, sig = token.rsplit(".", 1)
    bad_token = f"{body}.{'a' * len(sig)}"
    r = client.get("/api/portal/me", headers=auth_headers(bad_token))
    assert r.status_code == 401


def test_expired_token_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import time
    import app.security as sec_mod
    from datetime import datetime, timezone

    past_ts = time.time() - 7200

    def _past_now():
        return datetime.fromtimestamp(past_ts, tz=timezone.utc)

    monkeypatch.setattr(sec_mod, "utcnow", _past_now)
    from app.config import get_settings

    expired_token = sec_mod.create_access_token(42, get_settings())
    monkeypatch.undo()

    r = client.get("/api/portal/me", headers=auth_headers(expired_token))
    assert r.status_code == 401


def test_completely_random_token_rejected(client: TestClient) -> None:
    r = client.get("/api/portal/me", headers=auth_headers("notavalidtoken"))
    assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Rate limiting
# ──────────────────────────────────────────────────────────────────────────────


def test_rate_limit_auth_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """When rate-limiting is enabled, exceeding the auth limit returns 429."""
    import os

    from app.config import get_settings

    get_settings.cache_clear()
    old = os.environ.get("CLIENT_PORTAL_RATE_LIMIT_ENABLED")
    old_limit = os.environ.get("CLIENT_PORTAL_RATE_LIMIT_AUTH_LIMIT")

    os.environ["CLIENT_PORTAL_RATE_LIMIT_ENABLED"] = "true"
    os.environ["CLIENT_PORTAL_RATE_LIMIT_AUTH_LIMIT"] = "3"
    get_settings.cache_clear()

    try:
        statuses = []
        for i in range(6):
            r = client.post(
                "/api/portal/auth/login",
                json={"identifier": f"nobody{i}@x.com", "password": "Test1234!"},
            )
            statuses.append(r.status_code)
        assert 429 in statuses
    finally:
        if old is None:
            os.environ.pop("CLIENT_PORTAL_RATE_LIMIT_ENABLED", None)
        else:
            os.environ["CLIENT_PORTAL_RATE_LIMIT_ENABLED"] = old
        if old_limit is None:
            os.environ.pop("CLIENT_PORTAL_RATE_LIMIT_AUTH_LIMIT", None)
        else:
            os.environ["CLIENT_PORTAL_RATE_LIMIT_AUTH_LIMIT"] = old_limit
        get_settings.cache_clear()


# ──────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ──────────────────────────────────────────────────────────────────────────────


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_returns_503_when_db_unavailable(monkeypatch) -> None:
    """When the DB is unreachable, /api/health must respond with 503."""
    from app import main as main_mod
    from sqlalchemy.exc import OperationalError

    class _FailingSession:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, *_a, **_kw):
            raise OperationalError("conn failed", None, None)

    monkeypatch.setattr(main_mod, "SessionLocal", lambda: _FailingSession())

    from fastapi.testclient import TestClient as _TC
    from app.main import app as _app

    with _TC(app=_app, raise_server_exceptions=False) as tc:
        r = tc.get("/api/health")
        assert r.status_code == 503
