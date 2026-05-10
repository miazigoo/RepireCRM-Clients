"""Tests for marketing sync endpoint and portal settings."""

from __future__ import annotations

from fastapi.testclient import TestClient


_SYNC = {"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"}
_BAD = {"X-Sync-Token": "bad", "X-Tenant-Key": "default"}


def _push_marketing(client: TestClient, promotions=None, banner=None) -> dict:
    payload: dict = {}
    if promotions is not None:
        payload["promotions"] = promotions
    if banner is not None:
        payload["banner"] = banner
    r = client.post("/api/sync/marketing/upsert", headers=_SYNC, json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────────────────────────────────────────────────────────────────────
# Upsert marketing
# ──────────────────────────────────────────────────────────────────────────────


def test_upsert_marketing_with_promotions_and_banner(client: TestClient) -> None:
    r = _push_marketing(
        client,
        promotions=[
            {
                "crm_promotion_id": 1,
                "title": "Скидка 10%",
                "description": "На все услуги",
                "discount_type": "percent",
                "value": "10",
                "min_order_amount": "1000",
                "promo_codes": ["SUMMER10"],
            }
        ],
        banner={
            "title": "Майская акция",
            "subtitle": "Только до конца месяца",
            "active": True,
        },
    )
    assert r["promotions_count"] == 1
    assert r["has_banner"] is True


def test_upsert_marketing_no_banner(client: TestClient) -> None:
    r = _push_marketing(
        client,
        promotions=[{"crm_promotion_id": 2, "title": "Кэшбэк 5%", "value": "5"}],
    )
    assert r["promotions_count"] == 1
    assert r["has_banner"] is False


def test_upsert_marketing_replaces_previous(client: TestClient) -> None:
    """Second upsert completely replaces previous snapshot."""
    _push_marketing(
        client,
        promotions=[
            {"crm_promotion_id": 10, "title": "Старая акция", "value": "5"},
            {"crm_promotion_id": 11, "title": "Другая акция", "value": "3"},
        ],
    )

    _push_marketing(
        client,
        promotions=[{"crm_promotion_id": 12, "title": "Новая акция", "value": "15"}],
    )

    settings = client.get("/api/portal/settings").json()
    promos = settings["marketing"]["promotions"]
    assert len(promos) == 1
    assert promos[0]["title"] == "Новая акция"


def test_upsert_marketing_clears_promotions_on_empty_list(client: TestClient) -> None:
    _push_marketing(
        client,
        promotions=[{"crm_promotion_id": 20, "title": "Temp", "value": "1"}],
    )

    _push_marketing(client, promotions=[])

    settings = client.get("/api/portal/settings").json()
    assert settings["marketing"]["promotions"] == []


def test_upsert_marketing_null_banner_clears_banner(client: TestClient) -> None:
    _push_marketing(client, banner={"title": "Banner", "active": True})
    _push_marketing(client, banner=None)

    settings = client.get("/api/portal/settings").json()
    assert settings["marketing"]["banner"] is None


def test_upsert_marketing_promotion_sanitized(client: TestClient) -> None:
    _push_marketing(
        client,
        promotions=[
            {
                "crm_promotion_id": 99,
                "title": "<script>alert(1)</script>Скидка",
                "value": "10",
            }
        ],
    )
    settings = client.get("/api/portal/settings").json()
    assert "<script" not in settings["marketing"]["promotions"][0]["title"].lower()


def test_upsert_marketing_invalid_sync_token(client: TestClient) -> None:
    r = client.post("/api/sync/marketing/upsert", headers=_BAD, json={})
    assert r.status_code == 401


def test_upsert_marketing_promo_zero_id_rejected(client: TestClient) -> None:
    """Promotions with invalid id (<=0) should be filtered out."""
    _push_marketing(
        client,
        promotions=[{"crm_promotion_id": 0, "title": "Bad", "value": "5"}],
    )
    settings = client.get("/api/portal/settings").json()
    assert settings["marketing"]["promotions"] == []


# ──────────────────────────────────────────────────────────────────────────────
# Portal /settings reflects marketing
# ──────────────────────────────────────────────────────────────────────────────


def test_portal_settings_empty_marketing_by_default(client: TestClient) -> None:
    r = client.get("/api/portal/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["marketing"]["promotions"] == []
    assert body["marketing"]["banner"] is None
    assert body["locations"] == []
    assert "landing" in body
    assert body["landing"]["feature_cards"] == []
    assert body["landing"]["promo_spotlight"]["enabled"] is False


def test_portal_settings_includes_brand_and_auth(client: TestClient) -> None:
    r = client.get("/api/portal/settings")
    body = r.json()
    assert "brand" in body
    assert "auth" in body
    assert body["auth"]["policy"] in ("phone_or_email", "phone_only", "email_only")


def test_portal_settings_shows_synced_promotions(client: TestClient) -> None:
    _push_marketing(
        client,
        promotions=[
            {
                "crm_promotion_id": 50,
                "title": "Скидка на замену экрана",
                "description": "Летняя акция",
                "discount_type": "fixed",
                "value": "500",
                "promo_codes": ["SCREEN500"],
            }
        ],
        banner={"title": "Лето со скидкой", "subtitle": "Звоните сейчас", "active": True},
    )

    r = client.get("/api/portal/settings")
    body = r.json()
    assert body["marketing"]["promotions"][0]["title"] == "Скидка на замену экрана"
    assert body["marketing"]["promotions"][0]["promo_codes"] == ["SCREEN500"]
    assert body["marketing"]["banner"]["title"] == "Лето со скидкой"


def test_upsert_marketing_includes_locations(client: TestClient) -> None:
    r = client.post(
        "/api/sync/marketing/upsert",
        headers=_SYNC,
        json={
            "promotions": [{"crm_promotion_id": 1, "title": "Акция", "value": "5"}],
            "locations": [
                {
                    "crm_shop_id": 10,
                    "name": "Центр",
                    "code": "MSK1",
                    "address": "ул. Примерная, 1",
                    "city": "Москва",
                    "phone": "+79990001122",
                    "lat": 55.751244,
                    "lng": 37.618423,
                }
            ],
        },
    )
    assert r.status_code == 200
    body = client.get("/api/portal/settings").json()
    assert len(body["locations"]) == 1
    assert body["locations"][0]["name"] == "Центр"
    assert body["locations"][0]["city"] == "Москва"
    assert body["locations"][0]["lat"] == 55.751244
    assert body["locations"][0]["lng"] == 37.618423


def test_upsert_marketing_strips_locations_with_empty_name(client: TestClient) -> None:
    client.post(
        "/api/sync/marketing/upsert",
        headers=_SYNC,
        json={
            "promotions": [{"crm_promotion_id": 2, "title": "B", "value": "1"}],
            "locations": [{"crm_shop_id": 1, "name": "", "address": "x"}],
        },
    )
    body = client.get("/api/portal/settings").json()
    assert body["locations"] == []


def test_upsert_marketing_syncs_landing_to_settings(client: TestClient) -> None:
    r = client.post(
        "/api/sync/marketing/upsert",
        headers=_SYNC,
        json={
            "promotions": [{"crm_promotion_id": 77, "title": "Hold", "value": "1"}],
            "landing": {
                "section_eyebrow": "Спецпредложение",
                "section_title": "Скидка на ремонт",
                "section_subtitle": "Успейте до конца месяца",
                "feature_cards": [
                    {"title": "Срочно", "body": "Приём в день обращения", "icon": "sparkle"},
                    {"title": "Гарантия", "body": "По договору", "icon": "shield"},
                ],
                "promo_spotlight": {
                    "enabled": True,
                    "title": "−15% на работы",
                    "subtitle": "При заказе онлайн",
                    "body": "Покажите код в сервисе или оформите заявку в кабинете.",
                    "badge": "Акция",
                    "cta_label": "Регистрация",
                    "cta_href": "/login?register=1",
                },
            },
        },
    )
    assert r.status_code == 200
    body = client.get("/api/portal/settings").json()
    assert body["landing"]["section_title"] == "Скидка на ремонт"
    assert len(body["landing"]["feature_cards"]) == 2
    assert body["landing"]["feature_cards"][0]["icon"] == "sparkle"
    assert body["landing"]["promo_spotlight"]["enabled"] is True
    assert body["landing"]["promo_spotlight"]["title"] == "−15% на работы"
    assert body["landing"]["promo_spotlight"]["cta_href"] == "/login?register=1"
