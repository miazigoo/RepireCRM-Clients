"""Shared test infrastructure.

* Uses the running docker-compose Postgres (port 55440) so tests exercise real
  SQL constraints, JSON operators, RESTART IDENTITY, CASCADE, etc.
* Creates a dedicated ``portal_test`` database once per session.
* Runs Alembic ``upgrade head`` before the first test.
* Truncates every table between tests so each test starts from a clean slate.
* Exposes small helpers (register_customer, auth_headers, sync_headers, …)
  that the domain test files import.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

# ──────────────────────────────────────────────────────────────────────────────
# Postgres coordinates
# ──────────────────────────────────────────────────────────────────────────────
_PG_BASE_DSN = os.environ.get(
    "TEST_POSTGRES_BASE_DSN",
    "postgresql://repaircrm_client:repaircrm_client@127.0.0.1:55440/repaircrm_client",
)
_TEST_DB = "portal_test"
_TEST_URL = _PG_BASE_DSN.rsplit("/", 1)[0] + f"/{_TEST_DB}"
_TEST_SQLA_URL = _TEST_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# ──────────────────────────────────────────────────────────────────────────────
# Tables (dependency order — children first so TRUNCATE CASCADE is fastest)
# ──────────────────────────────────────────────────────────────────────────────
_TABLES = ", ".join(
    f'"{t}"'
    for t in [
        "push_notifications",
        "client_actions",
        "mobile_devices",
        "customer_sessions",
        "outbox_messages",
        "password_reset_challenges",
        "verification_challenges",
        "client_orders",
        "client_marketing_snapshots",
        "rate_limit_buckets",
        "customer_identities",
        "customer_accounts",
    ]
)
_TRUNCATE_SQL = text(f"TRUNCATE TABLE {_TABLES} RESTART IDENTITY CASCADE")


# ──────────────────────────────────────────────────────────────────────────────
# Session-scoped setup: create DB + migrate ONCE
# ──────────────────────────────────────────────────────────────────────────────
def pytest_configure(config):  # noqa: ANN001
    """Called by pytest before any collection; set env vars before app import."""
    with psycopg.connect(_PG_BASE_DSN, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB}"')
        conn.execute(f'CREATE DATABASE "{_TEST_DB}"')

    os.environ["CLIENT_PORTAL_DATABASE_URL"] = _TEST_SQLA_URL
    os.environ["CLIENT_PORTAL_SECRET_KEY"] = "test-secret-key-change-me"
    os.environ["CLIENT_PORTAL_SYNC_API_KEY"] = "sync-token"
    os.environ["CLIENT_PORTAL_DELIVERY_DEBUG"] = "true"
    os.environ["CLIENT_PORTAL_RATE_LIMIT_ENABLED"] = "false"
    os.environ["CLIENT_PORTAL_AUTH_POLICY"] = "phone_or_email"

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", _TEST_SQLA_URL)
    command.upgrade(alembic_cfg, "head")


# ──────────────────────────────────────────────────────────────────────────────
# Function-scoped: truncate between tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def clean_db() -> Generator[None, None, None]:
    yield
    from app.database import SessionLocal

    with SessionLocal() as db:
        db.execute(_TRUNCATE_SQL)
        db.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    from app.database import SessionLocal

    with SessionLocal() as session:
        yield session


@pytest.fixture()
def sync_headers() -> dict[str, str]:
    return {"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"}


# ──────────────────────────────────────────────────────────────────────────────
# Helper functions (importable from test modules)
# ──────────────────────────────────────────────────────────────────────────────
def register_customer(
    client: TestClient,
    *,
    first_name: str = "Тест",
    last_name: str = "Пользователь",
    email: str | None = "user@example.com",
    phone: str | None = None,
    password: str = "Test1234!",
    marketing_consent: bool = False,
) -> dict:
    """Register a customer and return the full token response dict."""
    payload: dict = {
        "first_name": first_name,
        "last_name": last_name,
        "password": password,
        "marketing_consent": marketing_consent,
    }
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone
    r = client.post("/api/portal/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def get_latest_debug_code(db: Session) -> str:
    """Return the most recent OTP code stored in OutboxMessage (debug mode)."""
    from sqlalchemy import select

    from app.models import OutboxMessage

    msg = db.scalar(select(OutboxMessage).order_by(OutboxMessage.id.desc()))
    assert msg is not None, "No OutboxMessage found"
    return str(msg.payload["code"])


def sync_one_order(
    client: TestClient,
    *,
    crm_order_id: int = 1,
    order_number: str = "R-001",
    customer_email: str | None = None,
    customer_phone: str | None = None,
    status: str = "diagnosed",
    status_display: str = "Диагностика",
    cost_estimate: str = "3000.00",
    remaining_payment: str = "3000.00",
    extra: dict | None = None,
) -> dict:
    """Push a single order via the sync endpoint and return response JSON."""
    customer: dict = {}
    if customer_email:
        customer["email"] = customer_email
    if customer_phone:
        customer["phone"] = customer_phone
    order = {
        "crm_order_id": crm_order_id,
        "order_number": order_number,
        "customer": customer,
        "device": {"brand": "Apple", "model_name": "iPhone 15"},
        "status": status,
        "status_display": status_display,
        "problem_description": "Проблема с устройством",
        "cost_estimate": cost_estimate,
        "remaining_payment": remaining_payment,
    }
    if extra:
        order.update(extra)
    r = client.post(
        "/api/sync/orders/upsert",
        headers={"X-Sync-Token": "sync-token", "X-Tenant-Key": "default"},
        json={"tenant_key": "default", "orders": [order]},
    )
    assert r.status_code == 200, r.text
    return r.json()
