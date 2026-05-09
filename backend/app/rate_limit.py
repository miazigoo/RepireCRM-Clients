"""Rate-limit middleware using an atomic Postgres upsert.

Previously the bucket was read, then updated in two separate queries — a classic
read-modify-write race condition.  The new implementation pushes the counter
increment into a single ``INSERT … ON CONFLICT DO UPDATE`` statement so each
request is counted exactly once even under concurrent load.

Row TTL: if the existing bucket's window has expired the row is replaced with a
fresh one (count = 1).  This is also expressed atomically in the same statement.
"""

from datetime import timedelta

from fastapi import status
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import get_settings
from .database import SessionLocal
from .security import utcnow


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path == "/api/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window_seconds = settings.rate_limit_window_seconds
        limit = _limit_for_path(
            request.url.path, settings.rate_limit_default_limit, settings.rate_limit_auth_limit
        )
        key = f"{client_ip}:{request.method}:{_bucket_path(request.url.path)}"
        now = utcnow()
        expires_at = now + timedelta(seconds=window_seconds)

        # One atomic statement: insert or increment.
        # If the existing row is expired (window passed) restart from count = 1.
        upsert = text(
            """
            INSERT INTO rate_limit_buckets (key, window_start, count, expires_at)
            VALUES (:key, :now, 1, :expires_at)
            ON CONFLICT (key) DO UPDATE SET
                count = CASE
                    WHEN rate_limit_buckets.expires_at <= :now THEN 1
                    ELSE rate_limit_buckets.count + 1
                END,
                window_start = CASE
                    WHEN rate_limit_buckets.expires_at <= :now THEN :now
                    ELSE rate_limit_buckets.window_start
                END,
                expires_at = CASE
                    WHEN rate_limit_buckets.expires_at <= :now THEN :expires_at
                    ELSE rate_limit_buckets.expires_at
                END
            RETURNING count
            """
        )

        with SessionLocal() as db:
            row = db.execute(upsert, {"key": key, "now": now, "expires_at": expires_at}).fetchone()
            db.commit()
            current_count = row[0] if row else 1

        if current_count > limit:
            return JSONResponse(
                {"detail": "Слишком много запросов. Повторите позже."},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        return await call_next(request)


def _limit_for_path(path: str, default_limit: int, auth_limit: int) -> int:
    if "/auth/" in path or "/contacts/" in path:
        return auth_limit
    return default_limit


def _bucket_path(path: str) -> str:
    if path.startswith("/api/portal/auth"):
        return "/api/portal/auth"
    if path.startswith("/api/portal/me/contacts"):
        return "/api/portal/me/contacts"
    if path.startswith("/api/sync"):
        return "/api/sync"
    return path
