from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import CustomerAccount
from .security import AuthError, parse_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def current_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CustomerAccount:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется вход")
    try:
        customer_id = parse_access_token(credentials.credentials, settings)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    customer = db.scalar(
        select(CustomerAccount).where(
            CustomerAccount.id == customer_id,
            CustomerAccount.is_active.is_(True),
        )
    )
    if not customer:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Клиент не найден")
    return customer


def require_sync_token(
    x_sync_token: str | None = Header(default=None, alias="X-Sync-Token"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_sync_token or x_sync_token != settings.sync_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Некорректный sync token")


def sync_tenant_key(
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    settings: Settings = Depends(get_settings),
) -> str:
    return x_tenant_key or settings.tenant_key
