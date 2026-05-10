"""Public shop list for landing map."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import services as app_services


def test_portal_shops_empty_without_crm_and_snapshot(client: TestClient) -> None:
    r = client.get("/api/portal/shops")
    assert r.status_code == 200
    assert r.json() == []


def test_portal_shops_uses_live_crm_payload(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    def fake_fetch(_settings):
        return [
            {
                "crm_shop_id": 5,
                "name": "Центр",
                "code": "C1",
                "address": "ул. 1",
                "phone": "+79990001122",
                "email": "",
                "city": "Самара",
            }
        ]

    monkeypatch.setattr(app_services, "fetch_portal_shops_from_crm", fake_fetch)
    r = client.get("/api/portal/shops")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["name"] == "Центр"
    assert body[0]["city"] == "Самара"
