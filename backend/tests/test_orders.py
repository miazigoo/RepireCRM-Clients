"""Tests for order endpoints (/api/portal/orders, /approvals, /track)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, get_latest_debug_code, register_customer, sync_one_order

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _register_and_verify(client: TestClient, db: Session, email: str) -> str:
    """Register, verify contact, return access_token."""
    data = register_customer(client, email=email)
    token = data["access_token"]
    # request verification
    client.post(
        "/api/portal/me/contacts/request-verification",
        headers=auth_headers(token),
        json={"type": "email", "value": email},
    )
    code = get_latest_debug_code(db)
    client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": email, "code": code},
    )
    return token


def _list_orders(client: TestClient, token: str, **params) -> list:
    r = client.get("/api/portal/orders", headers=auth_headers(token), params=params)
    assert r.status_code == 200
    return r.json()["items"]


# ──────────────────────────────────────────────────────────────────────────────
# Order listing
# ──────────────────────────────────────────────────────────────────────────────


def test_orders_empty_for_new_customer(client: TestClient) -> None:
    data = register_customer(client, email="empty@example.com")
    r = client.get("/api/portal/orders", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 50
    assert body["offset"] == 0


def test_portal_order_numbers_are_unique_for_fast_submits(client: TestClient) -> None:
    data = register_customer(client, email="fast-submit@example.com")
    token = data["access_token"]
    payload = {
        "device_type": "Телефон",
        "brand": "Apple",
        "model_name": "iPhone 15",
        "problem_description": "Не включается после обновления",
    }

    first = client.post("/api/portal/orders", headers=auth_headers(token), json=payload)
    second = client.post("/api/portal/orders", headers=auth_headers(token), json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["order_number"] != second.json()["order_number"]


def test_orders_require_authentication(client: TestClient) -> None:
    r = client.get("/api/portal/orders")
    assert r.status_code == 401


def test_orders_invisible_before_contact_verification(client: TestClient, db: Session) -> None:
    """Customer sees no orders when their contact is not yet verified."""
    data = register_customer(client, email="unverified@example.com")
    sync_one_order(
        client, crm_order_id=10, order_number="R-010", customer_email="unverified@example.com"
    )

    r = client.get("/api/portal/orders", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_orders_visible_after_verification(client: TestClient, db: Session) -> None:
    token = _register_and_verify(client, db, "vis@example.com")
    sync_one_order(client, crm_order_id=20, order_number="R-020", customer_email="vis@example.com")

    items = _list_orders(client, token)
    assert len(items) == 1
    assert items[0]["order_number"] == "R-020"


def test_multiple_orders_returned(client: TestClient, db: Session) -> None:
    token = _register_and_verify(client, db, "multi@example.com")
    sync_one_order(
        client, crm_order_id=30, order_number="R-030", customer_email="multi@example.com"
    )
    sync_one_order(
        client, crm_order_id=31, order_number="R-031", customer_email="multi@example.com"
    )

    items = _list_orders(client, token)
    assert len(items) == 2


# ──────────────────────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────────────────────


def test_pagination_limit_and_offset(client: TestClient, db: Session) -> None:
    """Pagination: limit and offset params are respected."""
    token = _register_and_verify(client, db, "pager@example.com")
    for i in range(5):
        sync_one_order(
            client,
            crm_order_id=200 + i,
            order_number=f"R-2{i:02d}",
            customer_email="pager@example.com",
        )

    r_all = client.get("/api/portal/orders", headers=auth_headers(token))
    assert r_all.json()["total"] == 5

    r_page1 = client.get(
        "/api/portal/orders", headers=auth_headers(token), params={"limit": 2, "offset": 0}
    )
    assert r_page1.status_code == 200
    p1 = r_page1.json()
    assert len(p1["items"]) == 2
    assert p1["total"] == 5
    assert p1["limit"] == 2
    assert p1["offset"] == 0

    r_page2 = client.get(
        "/api/portal/orders", headers=auth_headers(token), params={"limit": 2, "offset": 2}
    )
    p2 = r_page2.json()
    assert len(p2["items"]) == 2
    assert p2["offset"] == 2

    r_page3 = client.get(
        "/api/portal/orders", headers=auth_headers(token), params={"limit": 2, "offset": 4}
    )
    p3 = r_page3.json()
    assert len(p3["items"]) == 1


def test_pagination_invalid_params(client: TestClient) -> None:
    """Negative limit/offset should be rejected with 422."""
    data = register_customer(client, email="badpager@example.com")
    r = client.get(
        "/api/portal/orders",
        headers=auth_headers(data["access_token"]),
        params={"limit": -1},
    )
    assert r.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# Order detail
# ──────────────────────────────────────────────────────────────────────────────


def test_order_detail_returns_full_data(client: TestClient, db: Session) -> None:
    token = _register_and_verify(client, db, "detail@example.com")
    sync_one_order(
        client,
        crm_order_id=40,
        order_number="R-040",
        customer_email="detail@example.com",
        extra={
            "shop": {"code": "msk-1", "name": "Арбат", "address": "ул. Арбат, 1"},
            "prepayment": "500.00",
            "warranty_days": 90,
        },
    )

    items = _list_orders(client, token)
    detail_r = client.get(f"/api/portal/orders/{items[0]['id']}", headers=auth_headers(token))
    assert detail_r.status_code == 200
    body = detail_r.json()
    assert body["shop"]["code"] == "msk-1"
    assert body["prepayment"] == 500.0


def test_order_detail_not_found(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="nf@example.com")
    r = client.get("/api/portal/orders/99999", headers=auth_headers(data["access_token"]))
    assert r.status_code == 404


def test_order_detail_not_accessible_by_other_customer(client: TestClient, db: Session) -> None:
    token_owner = _register_and_verify(client, db, "owner2@example.com")
    token_other = register_customer(client, email="intruder@example.com")["access_token"]

    sync_one_order(
        client, crm_order_id=50, order_number="R-050", customer_email="owner2@example.com"
    )

    items = _list_orders(client, token_owner)
    order_id = items[0]["id"]

    r = client.get(f"/api/portal/orders/{order_id}", headers=auth_headers(token_other))
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Portal order creation
# ──────────────────────────────────────────────────────────────────────────────


def test_create_portal_order(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="create_order@example.com")
    token = data["access_token"]

    r = client.post(
        "/api/portal/orders",
        headers=auth_headers(token),
        json={
            "device_type": "Смартфон",
            "brand": "Samsung",
            "model_name": "Galaxy S24",
            "problem_description": "Разбитый экран, не реагирует на касания",
            "cost_estimate": 0,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "Galaxy S24" in body["device_title"]
    assert body["status"] == "received"


def test_create_portal_order_appears_in_list(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="list_portal@example.com")
    token = data["access_token"]

    client.post(
        "/api/portal/orders",
        headers=auth_headers(token),
        json={
            "device_type": "Ноутбук",
            "brand": "Apple",
            "model_name": "MacBook Air",
            "problem_description": "Не включается после обновления системы",
        },
    )
    items = _list_orders(client, token)
    assert len(items) == 1


def test_create_portal_order_too_short_description(client: TestClient) -> None:
    data = register_customer(client, email="short_desc@example.com")
    r = client.post(
        "/api/portal/orders",
        headers=auth_headers(data["access_token"]),
        json={
            "device_type": "Телефон",
            "brand": "Nokia",
            "model_name": "3310",
            "problem_description": "Bad",
        },
    )
    assert r.status_code == 422


def test_create_portal_order_creates_sync_action(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="action_create@example.com")
    token = data["access_token"]

    client.post(
        "/api/portal/orders",
        headers=auth_headers(token),
        json={
            "device_type": "Планшет",
            "brand": "Xiaomi",
            "model_name": "Pad 6",
            "problem_description": "Не заряжается батарея устройства",
        },
    )

    actions_r = client.get(
        "/api/sync/actions",
        headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
    )
    assert actions_r.status_code == 200
    actions = actions_r.json()["actions"]
    # Actions serialized with "type" key (= action_type)
    assert any(a["type"] == "repair_request.created" for a in actions)


# ──────────────────────────────────────────────────────────────────────────────
# Approval decisions
# ──────────────────────────────────────────────────────────────────────────────


def test_approve_approval(client: TestClient, db: Session) -> None:
    token = _register_and_verify(client, db, "approve@example.com")
    sync_one_order(
        client,
        crm_order_id=60,
        order_number="R-060",
        customer_email="approve@example.com",
        extra={
            "approvals": [
                {
                    "crm_approval_id": 101,
                    "title": "Замена экрана",
                    "amount": "8000",
                    "status": "pending",
                    "created_at": "2026-05-01T10:00:00Z",
                }
            ]
        },
    )

    r = client.post(
        "/api/portal/approvals/101/approve",
        headers=auth_headers(token),
        json={"comment": "Согласовано клиентом"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_reject_approval(client: TestClient, db: Session) -> None:
    token = _register_and_verify(client, db, "reject@example.com")
    sync_one_order(
        client,
        crm_order_id=61,
        order_number="R-061",
        customer_email="reject@example.com",
        extra={
            "approvals": [
                {
                    "crm_approval_id": 102,
                    "title": "Замена платы",
                    "amount": "15000",
                    "status": "pending",
                    "created_at": "2026-05-01T10:00:00Z",
                }
            ]
        },
    )

    r = client.post(
        "/api/portal/approvals/102/reject",
        headers=auth_headers(token),
        json={"comment": "Слишком дорого"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_approval_decision_creates_action(client: TestClient, db: Session) -> None:
    token = _register_and_verify(client, db, "act_approve@example.com")
    sync_one_order(
        client,
        crm_order_id=62,
        order_number="R-062",
        customer_email="act_approve@example.com",
        extra={
            "approvals": [
                {
                    "crm_approval_id": 103,
                    "title": "Ремонт",
                    "amount": "5000",
                    "status": "pending",
                    "created_at": "2026-05-01T10:00:00Z",
                }
            ]
        },
    )

    client.post(
        "/api/portal/approvals/103/approve",
        headers=auth_headers(token),
        json={},
    )

    actions_r = client.get(
        "/api/sync/actions",
        headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
    )
    actions = actions_r.json()["actions"]
    assert any(a["type"] == "approval.decided" for a in actions)


def test_approve_unknown_approval_404(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="ghost2@example.com")
    r = client.post(
        "/api/portal/approvals/9999/approve",
        headers=auth_headers(data["access_token"]),
        json={},
    )
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Public order tracking
# ──────────────────────────────────────────────────────────────────────────────


def test_public_track_by_email(client: TestClient) -> None:
    sync_one_order(
        client,
        crm_order_id=70,
        order_number="R-070",
        customer_email="track@example.com",
    )

    r = client.post(
        "/api/portal/track",
        json={"order_number": "R-070", "email": "track@example.com"},
    )
    assert r.status_code == 200
    assert r.json()["order_number"] == "R-070"


def test_public_track_by_phone(client: TestClient) -> None:
    sync_one_order(
        client,
        crm_order_id=71,
        order_number="R-071",
        customer_phone="+79991239999",
        extra={"customer": {"phone": "+79991239999"}},
    )

    r = client.post(
        "/api/portal/track",
        json={"order_number": "R-071", "phone": "+79991239999"},
    )
    assert r.status_code == 200


def test_public_track_not_found(client: TestClient) -> None:
    r = client.post(
        "/api/portal/track",
        json={"order_number": "NOPE", "email": "nobody@example.com"},
    )
    assert r.status_code == 404


def test_public_track_missing_contact_400(client: TestClient) -> None:
    r = client.post("/api/portal/track", json={"order_number": "R-080"})
    assert r.status_code in (400, 422)
