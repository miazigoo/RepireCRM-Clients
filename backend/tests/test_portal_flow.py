from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.database import SessionLocal
from app.main import app
from app.models import ClientOrder, OutboxMessage
from app.services import validate_registration_contacts


def latest_debug_code() -> str:
    with SessionLocal() as db:
        message = db.scalar(select(OutboxMessage).order_by(OutboxMessage.id.desc()))
        assert message is not None
        return message.payload["code"]


def test_registration_contact_verification_order_sync_and_password_reset():
    with TestClient(app) as client:
        settings_response = client.get("/api/portal/settings")
        assert settings_response.status_code == 200
        assert settings_response.json()["auth"]["policy"] == "phone_or_email"
        assert settings_response.json()["marketing"]["promotions"] == []

        register_response = client.post(
            "/api/portal/auth/register",
            json={
                "first_name": "Анна",
                "last_name": "Иванова",
                "email": "Anna@example.com",
                "password": "secret123!",
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]
        assert register_response.json()["refresh_token"]

        sync_response = client.post(
            "/api/sync/orders/upsert",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
            json={
                "tenant_key": "default",
                "orders": [
                    {
                        "crm_order_id": 1,
                        "order_number": "R-100",
                        "customer": {"email": "anna@example.com"},
                        "device": {"brand": "Apple", "model_name": "iPhone 13"},
                        "shop": {
                            "code": "msk-1",
                            "name": "Филиал Арбат",
                            "address": "ул. Арбат, 1",
                            "phone": "+74951234567",
                        },
                        "status": "diagnosed",
                        "status_display": "Диагностика",
                        "problem_description": "Не включается",
                        "cost_estimate": "5000.00",
                        "remaining_payment": "5000.00",
                        "prepayment": "1000.00",
                        "approvals": [
                            {
                                "crm_approval_id": 45,
                                "title": "Замена аккумулятора",
                                "amount": "5000.00",
                                "status": "pending",
                                "created_at": "2026-05-09T10:00:00Z",
                            }
                        ],
                    }
                ],
            },
        )
        assert sync_response.status_code == 200
        assert sync_response.json()["orders"][0]["crm_order_id"] == 1

        empty_orders = client.get(
            "/api/portal/orders", headers={"Authorization": f"Bearer {token}"}
        )
        assert empty_orders.status_code == 200
        assert empty_orders.json() == []

        code = latest_debug_code()
        verify_response = client.post(
            "/api/portal/me/contacts/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"type": "email", "value": "anna@example.com", "code": code},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["contacts"][0]["verified_at"] is not None

        orders_response = client.get(
            "/api/portal/orders", headers={"Authorization": f"Bearer {token}"}
        )
        assert orders_response.status_code == 200
        orders = orders_response.json()
        assert len(orders) == 1
        assert orders[0]["order_number"] == "R-100"
        assert orders[0]["shop"]["name"] == "Филиал Арбат"
        assert orders[0]["shop"]["address"] == "ул. Арбат, 1"
        assert orders[0]["prepayment"] == 1000.0

        remote_id = orders[0]["id"]
        detail_response = client.get(
            f"/api/portal/orders/{remote_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert detail_response.status_code == 200
        assert detail_response.json()["shop"]["code"] == "msk-1"

        approval_response = client.post(
            "/api/portal/approvals/45/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={"comment": "Согласовано"},
        )
        assert approval_response.status_code == 200
        assert approval_response.json()["status"] == "approved"

        actions_response = client.get(
            "/api/sync/actions", headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"}
        )
        assert actions_response.status_code == 200
        action = actions_response.json()["actions"][0]
        assert action["type"] == "approval.decided"
        assert action["payload"]["crm_approval_id"] == 45

        mark_response = client.post(
            f"/api/sync/actions/{action['id']}/mark-synced",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
            json={"status": "applied", "crm_order_id": 1, "error": ""},
        )
        assert mark_response.status_code == 200

        reset_request = client.post(
            "/api/portal/auth/password/request-reset",
            json={"identifier": "anna@example.com"},
        )
        assert reset_request.status_code == 202
        reset_code = reset_request.json()["debug_code"]

        reset_confirm = client.post(
            "/api/portal/auth/password/confirm-reset",
            json={
                "identifier": "anna@example.com",
                "code": reset_code,
                "new_password": "new-secret123!",
            },
        )
        assert reset_confirm.status_code == 200

        login_response = client.post(
            "/api/portal/auth/login",
            json={"identifier": "anna@example.com", "password": "new-secret123!"},
        )
        assert login_response.status_code == 200

        refresh_response = client.post(
            "/api/portal/auth/refresh",
            json={"refresh_token": login_response.json()["refresh_token"]},
        )
        assert refresh_response.status_code == 200

        device_response = client.post(
            "/api/mobile/devices",
            headers={"Authorization": f"Bearer {refresh_response.json()['access_token']}"},
            json={"platform": "ios", "device_uid": "device-1", "push_token": "push-token"},
        )
        assert device_response.status_code == 200

        push_response = client.post(
            "/api/mobile/push/test",
            headers={"Authorization": f"Bearer {refresh_response.json()['access_token']}"},
            json={"title": "Test", "body": "Hello", "payload": {"order": "R-100"}},
        )
        assert push_response.status_code == 200
        assert push_response.json()["queued"] == 1

        logout_response = client.post(
            "/api/portal/auth/logout",
            json={"refresh_token": refresh_response.json()["refresh_token"]},
        )
        assert logout_response.status_code == 204


def test_marketing_sync_roundtrip():
    with TestClient(app) as client:
        sync_response = client.post(
            "/api/sync/marketing/upsert",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
            json={
                "promotions": [
                    {
                        "crm_promotion_id": 42,
                        "title": "Скидка 10%",
                        "description": "На все услуги",
                        "discount_type": "percent",
                        "value": "10",
                        "min_order_amount": "1000",
                        "promo_codes": ["SUMMER"],
                    }
                ],
                "banner": {
                    "title": "Майские скидки",
                    "subtitle": "До конца месяца",
                    "active": True,
                },
            },
        )
        assert sync_response.status_code == 200
        assert sync_response.json()["promotions_count"] == 1
        assert sync_response.json()["has_banner"] is True

        settings_response = client.get("/api/portal/settings")
        assert settings_response.status_code == 200
        body = settings_response.json()
        assert body["marketing"]["promotions"][0]["title"] == "Скидка 10%"
        assert body["marketing"]["banner"]["title"] == "Майские скидки"


def test_portal_created_order_is_relinked_after_crm_accepts_it():
    with TestClient(app) as client:
        register_response = client.post(
            "/api/portal/auth/register",
            json={
                "first_name": "Ольга",
                "last_name": "Смирнова",
                "email": "olga@example.com",
                "password": "secret123!",
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]

        create_response = client.post(
            "/api/portal/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_type": "Телефон",
                "brand": "Samsung",
                "model_name": "S24",
                "problem_description": "Не заряжается от оригинального кабеля",
                "cost_estimate": 0,
            },
        )
        assert create_response.status_code == 201
        local_order_id = create_response.json()["id"]

        actions_response = client.get(
            "/api/sync/actions",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
        )
        assert actions_response.status_code == 200
        action = actions_response.json()["actions"][0]
        assert action["payload"]["client_order_id"] == local_order_id

        mark_response = client.post(
            f"/api/sync/actions/{action['id']}/mark-synced",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
            json={
                "status": "applied",
                "crm_order_id": 777,
                "crm_order_number": "R-777",
                "error": "",
            },
        )
        assert mark_response.status_code == 200

        sync_response = client.post(
            "/api/sync/orders/upsert",
            headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
            json={
                "tenant_key": "default",
                "orders": [
                    {
                        "crm_order_id": 777,
                        "order_number": "R-777",
                        "customer": {"email": "olga@example.com"},
                        "device": {"brand": "Samsung", "model_name": "S24"},
                        "status": "diagnosed",
                        "status_display": "Диагностика",
                        "problem_description": "Не заряжается от оригинального кабеля",
                        "cost_estimate": "1500.00",
                        "remaining_payment": "1500.00",
                        "payments": [
                            {
                                "crm_payment_id": 51,
                                "payment_number": "PAY-51",
                                "payment_type": "income",
                                "status": "completed",
                                "status_display": "Завершен",
                                "amount": "500.00",
                                "payment_method": "Наличные",
                                "payment_date": "2026-05-10T10:00:00+03:00",
                            }
                        ],
                    }
                ],
            },
        )
        assert sync_response.status_code == 200

        orders_response = client.get(
            "/api/portal/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert orders_response.status_code == 200
        orders = orders_response.json()
        assert len(orders) == 1
        assert orders[0]["id"] == local_order_id
        assert orders[0]["order_number"] == "R-777"
        assert orders[0]["status"] == "diagnosed"
        assert orders[0]["payments"][0]["amount"] == 500.0
        assert orders[0]["payments"][0]["payment_method"] == "Наличные"

        with SessionLocal() as db:
            rows = db.scalars(select(ClientOrder).where(ClientOrder.crm_order_id == 777)).all()
            assert len(rows) == 1


def test_auth_policy_validation():
    phone_settings = Settings(
        secret_key="test-secret-key-change-me",
        auth_policy="phone_only",
    )
    email_settings = Settings(
        secret_key="test-secret-key-change-me",
        auth_policy="email_only",
    )

    assert validate_registration_contacts(phone_settings, "+79990001122", None)[0][0] == "phone"
    assert validate_registration_contacts(email_settings, None, "user@example.com")[0][0] == "email"


def test_security_headers_and_xss_sanitization():
    with TestClient(app) as client:
        health_response = client.get("/api/health")
        assert health_response.status_code == 200
        assert health_response.headers["x-content-type-options"] == "nosniff"
        assert health_response.headers["x-frame-options"] == "DENY"
        assert "script-src 'self'" in health_response.headers["content-security-policy"]
        assert "object-src 'none'" in health_response.headers["content-security-policy"]

        register_response = client.post(
            "/api/portal/auth/register",
            json={
                "first_name": "<img src=x onerror=alert(1)>Мария",
                "last_name": "<script>alert(1)</script>Петрова",
                "email": "xss@example.com",
                "password": "secret123!",
            },
        )
        assert register_response.status_code == 201
        customer = register_response.json()["customer"]
        assert "<" not in customer["first_name"]
        assert "onerror" not in customer["first_name"].lower()
        assert "<script" not in customer["last_name"].lower()

        token = register_response.json()["access_token"]
        order_response = client.post(
            "/api/portal/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_type": "phone",
                "brand": "<img src=x onerror=alert(1)>Apple",
                "model_name": "iPhone <script>alert(1)</script>",
                "problem_description": "<script>alert(1)</script>Не включается после падения",
                "cost_estimate": 0,
            },
        )
        assert order_response.status_code == 201
        order = order_response.json()
        assert "<script" not in order["problem_description"].lower()
        assert "onerror" not in order["device_title"].lower()
        assert "<" not in order["device_title"]
