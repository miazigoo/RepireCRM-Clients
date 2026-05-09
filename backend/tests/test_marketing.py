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


def test_portal_settings_has_features_dict(client: TestClient) -> None:
    r = client.get("/api/portal/settings")
    assert isinstance(r.json()["features"], dict)
