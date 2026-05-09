import os
import sys
import tempfile
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

_TEST_WORKDIR = tempfile.mkdtemp()


def pytest_configure(config):
    os.environ["CLIENT_PORTAL_DATABASE_URL"] = f"sqlite:///{_TEST_WORKDIR}/test.sqlite3"
    os.environ["CLIENT_PORTAL_SECRET_KEY"] = "test-secret-key-change-me"
    os.environ["CLIENT_PORTAL_SYNC_API_KEY"] = "sync-token"
    os.environ["CLIENT_PORTAL_DELIVERY_DEBUG"] = "true"
    os.environ["CLIENT_PORTAL_RATE_LIMIT_ENABLED"] = "false"

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
