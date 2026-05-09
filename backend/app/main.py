from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .rate_limit import RateLimitMiddleware
from .routers import auth, mobile, orders, profile, settings, sync
from .security_headers import SecurityHeadersMiddleware

settings_obj = get_settings()

app = FastAPI(title="Repair CRM Client API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_obj.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(settings.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(orders.router)
app.include_router(mobile.router)
app.include_router(sync.router)


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "Ошибка запроса",
            "details": exc.detail if isinstance(exc.detail, dict) else None,
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
