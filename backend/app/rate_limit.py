from datetime import timedelta

from fastapi import status
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import get_settings
from .database import SessionLocal
from .models import RateLimitBucket
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

        with SessionLocal() as db:
            bucket = db.query(RateLimitBucket).filter(RateLimitBucket.key == key).one_or_none()
            if bucket is None or bucket.expires_at <= now:
                bucket = RateLimitBucket(
                    key=key,
                    window_start=now,
                    count=1,
                    expires_at=now + timedelta(seconds=window_seconds),
                )
                db.merge(bucket)
                db.commit()
            else:
                bucket.count += 1
                if bucket.count > limit:
                    db.commit()
                    return JSONResponse(
                        {"detail": "Слишком много запросов. Повторите позже."},
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                db.commit()

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
