"""Tests for CRM → portal sync endpoints (/api/sync/*)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, get_latest_debug_code, register_customer, sync_one_order

_SYNC = {"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"}
_BAD_TOKEN = {"X-Sync-Token": "wrong", "X-Tenant-Key": "default"}


# ──────────────────────────────────────────────────────────────────────────────
# Orders upsert
# ──────────────────────────────────────────────────────────────────────────────


def test_upsert_order_creates_new(client: TestClient, db: Session) -> None:
    r = sync_one_order(client, crm_order_id=1, order_number="R-001")
    assert r["orders"][0]["crm_order_id"] == 1
    assert r["orders"][0]["remote_order_id"]


def test_upsert_order_updates_existing(client: TestClient, db: Session) -> None:
    sync_one_order(client, crm_order_id=2, order_number="R-002", status="received")
    r = sync_one_order(client, crm_order_id=2, order_number="R-002", status="ready")

    from app.models import ClientOrder

    order = db.scalar(select(ClientOrder).where(ClientOrder.crm_order_id == 2))
    assert order is not None
    assert order.status == "ready"
    assert len(r["orders"]) == 1  # no duplicate row


def test_upsert_stores_payment_details(client: TestClient, db: Session) -> None:
    sync_one_order(
        client,
        crm_order_id=3,
        order_number="R-003",
        extra={
            "payments": [
                {
                    "crm_payment_id": 10,
                    "payment_number": "PAY-10",
                    "payment_type": "income",
                    "status": "completed",
                    "status_display": "Оплачено",
                    "amount": "2500.00",
                    "payment_method": "Карта",
                    "payment_date": "2026-05-01T12:00:00Z",
                }
            ]
        },
    )

    from app.models import ClientOrder

    order = db.scalar(select(ClientOrder).where(ClientOrder.crm_order_id == 3))
    assert order is not None
    snapshot = order.crm_snapshot or {}
    payments = snapshot.get("payments", [])
    assert len(payments) == 1
    assert payments[0]["amount"] == "2500.00"


def test_upsert_stores_warranty(client: TestClient, db: Session) -> None:
    sync_one_order(
        client,
        crm_order_id=4,
        order_number="R-004",
        extra={"warranty_days": 90, "warranty_active": True},
    )

    from app.models import ClientOrder

    order = db.scalar(select(ClientOrder).where(ClientOrder.crm_order_id == 4))
    assert order is not None
    # warranty data is nested under snap["warranty"]
    snap = order.crm_snapshot or {}
    warranty = snap.get("warranty", {})
    assert warranty.get("warranty_days") == 90
    assert warranty.get("warranty_active") is True


def test_upsert_links_to_verified_customer(client: TestClient, db: Session) -> None:
    """Order should be auto-linked when customer's email is verified."""
    data = register_customer(client, email="link@example.com")
    token = data["access_token"]

    client.post(
        "/api/portal/me/contacts/request-verification",
        headers=auth_headers(token),
        json={"type": "email", "value": "link@example.com"},
    )
    code = get_latest_debug_code(db)
    client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": "link@example.com", "code": code},
    )

    sync_one_order(client, crm_order_id=5, order_number="R-005", customer_email="link@example.com")

    from app.models import ClientOrder

    order = db.scalar(select(ClientOrder).where(ClientOrder.crm_order_id == 5))
    assert order is not None
    assert order.customer_id is not None


def test_upsert_invalid_sync_token(client: TestClient) -> None:
    r = client.post(
        "/api/sync/orders/upsert",
        headers=_BAD_TOKEN,
        json={"orders": []},
    )
    assert r.status_code == 401


def test_upsert_empty_orders_list(client: TestClient) -> None:
    r = client.post(
        "/api/sync/orders/upsert",
        headers=_SYNC,
        json={"tenant_key": "default", "orders": []},
    )
    assert r.status_code == 200
    assert r.json()["orders"] == []


def test_upsert_rejects_tenant_mismatch(client: TestClient) -> None:
    r = client.post(
        "/api/sync/orders/upsert",
        headers=_SYNC,
        json={"tenant_key": "another-tenant", "orders": []},
    )
    assert r.status_code == 400


def test_upsert_multiple_orders_in_batch(client: TestClient, db: Session) -> None:
    r = client.post(
        "/api/sync/orders/upsert",
        headers=_SYNC,
        json={
            "tenant_key": "default",
            "orders": [
                {
                    "crm_order_id": 100,
                    "order_number": "R-100",
                    "customer": {"email": "batch@example.com"},
                    "device": {"brand": "Apple", "model_name": "iPad"},
                    "status": "received",
                    "status_display": "Принят",
                    "problem_description": "Треснул экран",
                    "cost_estimate": "0",
                    "remaining_payment": "0",
                },
                {
                    "crm_order_id": 101,
                    "order_number": "R-101",
                    "customer": {"email": "batch@example.com"},
                    "device": {"brand": "Samsung", "model_name": "S22"},
                    "status": "diagnosed",
                    "status_display": "Диагностика",
                    "problem_description": "Не заряжается",
                    "cost_estimate": "2000",
                    "remaining_payment": "2000",
                },
            ],
        },
    )
    assert r.status_code == 200
    assert len(r.json()["orders"]) == 2


# ──────────────────────────────────────────────────────────────────────────────
# Actions
# ──────────────────────────────────────────────────────────────────────────────


def test_list_actions_empty(client: TestClient) -> None:
    r = client.get("/api/sync/actions", headers=_SYNC)
    assert r.status_code == 200
    assert r.json()["actions"] == []


def test_list_actions_after_approval(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="act@example.com")
    token = data["access_token"]

    client.post(
        "/api/portal/me/contacts/request-verification",
        headers=auth_headers(token),
        json={"type": "email", "value": "act@example.com"},
    )
    code = get_latest_debug_code(db)
    client.post(
        "/api/portal/me/contacts/confirm",
        headers=auth_headers(token),
        json={"type": "email", "value": "act@example.com", "code": code},
    )

    sync_one_order(
        client,
        crm_order_id=200,
        order_number="R-200",
        customer_email="act@example.com",
        extra={
            "approvals": [
                {
                    "crm_approval_id": 500,
                    "title": "Замена матрицы",
                    "amount": "6000",
                    "status": "pending",
                    "created_at": "2026-05-01T10:00:00Z",
                }
            ]
        },
    )

    client.post(
        "/api/portal/approvals/500/approve",
        headers=auth_headers(token),
        json={"comment": "ОК"},
    )

    r = client.get("/api/sync/actions", headers=_SYNC)
    assert r.status_code == 200
    actions = r.json()["actions"]
    assert len(actions) >= 1
    assert actions[0]["type"] == "approval.decided"


def test_mark_action_synced(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="mark@example.com")
    token = data["access_token"]

    client.post(
        "/api/portal/orders",
        headers=auth_headers(token),
        json={
            "device_type": "Телефон",
            "brand": "Nokia",
            "model_name": "X20",
            "problem_description": "Не работает микрофон при звонках",
        },
    )

    r_actions = client.get("/api/sync/actions", headers=_SYNC)
    action = r_actions.json()["actions"][0]

    r = client.post(
        f"/api/sync/actions/{action['id']}/mark-synced",
        headers=_SYNC,
        json={"status": "applied", "crm_order_id": 999, "crm_order_number": "R-999"},
    )
    assert r.status_code == 200

    # After mark-synced, action should not appear in pending list
    r2 = client.get("/api/sync/actions", headers=_SYNC)
    assert r2.json()["actions"] == []


def test_field_visit_request_is_synced_as_action(client: TestClient, db: Session) -> None:
    data = register_customer(client, email="visit@example.com")
    token = data["access_token"]

    created = client.post(
        "/api/portal/field-visit",
        headers=auth_headers(token),
        json={
            "address": "Москва, Тверская, 1",
            "preferred_date": "2026-05-20",
            "preferred_time": "11:30",
            "device_title": "iPhone 15",
            "problem_description": "Не заряжается",
            "description": "Позвонить за час",
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    r_actions = client.get("/api/sync/actions", headers=_SYNC)
    actions = r_actions.json()["actions"]
    assert len(actions) == 1
    action = actions[0]
    assert action["type"] == "field_visit.created"
    assert action["payload"]["field_visit_request_id"] == request_id
    assert action["payload"]["field_visit"]["address"] == "Москва, Тверская, 1"

    mark = client.post(
        f"/api/sync/actions/{action['id']}/mark-synced",
        headers=_SYNC,
        json={"status": "applied", "crm_task_id": 321},
    )
    assert mark.status_code == 200, mark.text

    from app.models import FieldVisitRequest

    row = db.get(FieldVisitRequest, request_id)
    assert row is not None
    assert row.status == "accepted"
    assert row.crm_request_id == 321


def test_mark_nonexistent_action_404(client: TestClient) -> None:
    r = client.post(
        "/api/sync/actions/999999/mark-synced",
        headers=_SYNC,
        json={"status": "applied"},
    )
    assert r.status_code == 404


def test_list_actions_invalid_token(client: TestClient) -> None:
    r = client.get("/api/sync/actions", headers=_BAD_TOKEN)
    assert r.status_code == 401


def test_marketing_upsert_rejects_tenant_mismatch(client: TestClient) -> None:
    r = client.post(
        "/api/sync/marketing/upsert",
        headers=_SYNC,
        json={"tenant_key": "another-tenant", "promotions": []},
    )
    assert r.status_code == 400


def test_portal_order_linked_after_crm_accepts(client: TestClient, db: Session) -> None:
    """Portal order created offline is linked once CRM pushes back crm_order_id."""
    data = register_customer(client, email="relink@example.com")
    token = data["access_token"]

    create_r = client.post(
        "/api/portal/orders",
        headers=auth_headers(token),
        json={
            "device_type": "Телефон",
            "brand": "OnePlus",
            "model_name": "12",
            "problem_description": "Не работает Face ID после замены стекла",
        },
    )
    local_id = create_r.json()["id"]

    actions_r = client.get("/api/sync/actions", headers=_SYNC)
    action = actions_r.json()["actions"][0]

    client.post(
        f"/api/sync/actions/{action['id']}/mark-synced",
        headers=_SYNC,
        json={"status": "applied", "crm_order_id": 888, "crm_order_number": "R-888"},
    )

    sync_one_order(
        client,
        crm_order_id=888,
        order_number="R-888",
        customer_email="relink@example.com",
        status="diagnosed",
    )

    # Customer now sees their order
    r = client.get("/api/portal/orders", headers=auth_headers(token))
    orders = r.json()["items"]
    assert len(orders) == 1
    assert orders[0]["id"] == local_id
    assert orders[0]["order_number"] == "R-888"
