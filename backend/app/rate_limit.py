"""Rate-limit middleware backed by Redis.

Strategy
--------
For each request we build a bucket key ``{ip}:{METHOD}:{path_bucket}`` and
execute a Redis pipeline::

    INCR  key        → new counter value
    EXPIRE key ttl NX  → set TTL only when the key is brand-new

This is two round-trips but is effectively atomic for our purposes: INCR is
atomic in Redis and NX ensures the TTL is set exactly once per window.

Fallback
--------
If Redis is unavailable (``ConnectionError`` / ``TimeoutError``) the middleware
*allows* the request through rather than blocking it.  This trades a brief
window of unprotected traffic for availability.  An error is logged so ops can
react.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import status
from redis import Redis, ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import get_settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_redis() -> Redis:  # type: ignore[type-arg]
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=0.5)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path == "/api/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window = settings.rate_limit_window_seconds
        limit = _limit_for_path(
            request.url.path, settings.rate_limit_default_limit, settings.rate_limit_auth_limit
        )
        key = f"rl:{client_ip}:{request.method}:{_bucket_path(request.url.path)}"

        try:
            redis = _get_redis()
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            count, _ = pipe.execute()
        except (RedisConnectionError, RedisTimeoutError) as exc:
            log.warning("rate_limit redis unavailable — allowing request: %s", exc)
            return await call_next(request)

        if count > limit:
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
