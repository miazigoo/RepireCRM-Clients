from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..dependencies import current_customer
from ..models import CustomerAccount, CustomerIdentity, CustomerSession
from ..schemas import (
    ChallengeResponse,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from ..security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    utcnow,
    verify_password,
)
from ..services import (
    create_contact_challenge,
    create_password_reset_challenge,
    find_identity_by_identifier,
    serialize_customer,
    validate_registration_contacts,
    reset_password,
)

router = APIRouter(prefix="/api/portal/auth", tags=["portal-auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    contacts = validate_registration_contacts(settings, data.phone, data.email)
    existing = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.tenant_key == settings.tenant_key,
            CustomerIdentity.normalized_value.in_([item[2] for item in contacts]),
        )
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Клиент с таким контактом уже зарегистрирован"
        )

    customer = CustomerAccount(
        tenant_key=settings.tenant_key,
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        middle_name=data.middle_name.strip() if data.middle_name else None,
        password_hash=hash_password(data.password),
        marketing_consent=data.marketing_consent,
    )
    db.add(customer)
    db.flush()

    for index, (identity_type, value, normalized) in enumerate(contacts):
        identity = CustomerIdentity(
            customer=customer,
            tenant_key=settings.tenant_key,
            type=identity_type,
            value=value,
            normalized_value=normalized,
            is_primary=index == 0,
        )
        db.add(identity)
        db.flush()
        create_contact_challenge(db, identity, settings)

    customer.last_login_at = utcnow()
    db.commit()
    db.refresh(customer)
    refresh_token = create_session(db, customer, request, settings)
    db.commit()

    return TokenResponse(
        access_token=create_access_token(customer.id, settings),
        expires_in=settings.token_ttl_minutes * 60,
        refresh_token=refresh_token,
        customer=serialize_customer(customer),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    identifier = data.identifier or data.phone or data.email
    assert identifier is not None
    identity = find_identity_by_identifier(db, identifier, settings.tenant_key)
    if (
        not identity
        or not identity.customer.is_active
        or not verify_password(data.password, identity.customer.password_hash)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неверный логин или пароль")

    identity.customer.last_login_at = utcnow()
    refresh_token = create_session(db, identity.customer, request, settings)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(identity.customer_id, settings),
        expires_in=settings.token_ttl_minutes * 60,
        refresh_token=refresh_token,
        customer=serialize_customer(identity.customer),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    token_hash = hash_token(data.refresh_token, settings.secret_key)
    session = db.scalar(
        select(CustomerSession).where(
            CustomerSession.refresh_token_hash == token_hash,
            CustomerSession.revoked_at.is_(None),
            CustomerSession.expires_at >= utcnow(),
        )
    )
    if not session or not session.customer.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия недействительна")
    session.last_seen_at = utcnow()
    refresh_value = rotate_session(db, session, request, settings)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(session.customer_id, settings),
        expires_in=settings.token_ttl_minutes * 60,
        refresh_token=refresh_value,
        customer=serialize_customer(session.customer),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_session(
    data: LogoutRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    token_hash = hash_token(data.refresh_token, settings.secret_key)
    session = db.scalar(
        select(CustomerSession).where(
            CustomerSession.refresh_token_hash == token_hash,
            CustomerSession.revoked_at.is_(None),
            CustomerSession.expires_at >= utcnow(),
        )
    )
    if session:
        session.revoked_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all_sessions(
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        update(CustomerSession)
        .where(
            CustomerSession.customer_id == customer.id,
            CustomerSession.tenant_key == customer.tenant_key,
            CustomerSession.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password/request-reset",
    response_model=ChallengeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChallengeResponse:
    identity = find_identity_by_identifier(db, data.identifier, settings.tenant_key)
    debug_code = None
    delivery_id = None
    if identity and identity.verified_at is not None and identity.customer.is_active:
        message, code = create_password_reset_challenge(db, identity, settings)
        debug_code = code if settings.delivery_debug else None
        delivery_id = message.id
        db.commit()

    return ChallengeResponse(
        message="Если контакт подтвержден, код восстановления будет отправлен",
        delivery_id=delivery_id,
        debug_code=debug_code,
    )


@router.post("/password/confirm-reset", response_model=ChallengeResponse)
def confirm_password_reset(
    data: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChallengeResponse:
    reset_password(db, data.identifier, data.code, data.new_password, settings)
    db.commit()
    return ChallengeResponse(message="Пароль обновлен")


def create_session(
    db: Session, customer: CustomerAccount, request: Request, settings: Settings
) -> str:
    refresh_token = generate_refresh_token()
    session = CustomerSession(
        customer_id=customer.id,
        tenant_key=customer.tenant_key,
        refresh_token_hash=hash_token(refresh_token, settings.secret_key),
        user_agent=request.headers.get("user-agent", "")[:255],
        ip_address=request.client.host if request.client else "",
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
        last_seen_at=utcnow(),
    )
    db.add(session)
    db.flush()
    return refresh_token


def rotate_session(
    db: Session, session: CustomerSession, request: Request, settings: Settings
) -> str:
    session.revoked_at = utcnow()
    return create_session(db, session.customer, request, settings)
