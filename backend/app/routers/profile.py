from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..dependencies import current_customer
from ..models import CustomerAccount, CustomerIdentity
from ..schemas import (
    ChallengeResponse,
    ContactCreateRequest,
    PortalCustomerSchema,
    ProfileUpdateRequest,
    VerificationConfirmRequest,
    VerificationRequest,
)
from ..security import normalize_identity
from ..services import (
    create_contact_challenge,
    create_identity,
    serialize_customer,
    verify_contact_code,
)

router = APIRouter(prefix="/api/portal/me", tags=["portal-profile"])


@router.get("", response_model=PortalCustomerSchema)
def me(customer: CustomerAccount = Depends(current_customer)) -> PortalCustomerSchema:
    return serialize_customer(customer)


@router.patch("", response_model=PortalCustomerSchema)
def update_profile(
    data: ProfileUpdateRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> PortalCustomerSchema:
    if data.first_name is not None:
        customer.first_name = data.first_name.strip()
    if data.last_name is not None:
        customer.last_name = data.last_name.strip()
    if data.middle_name is not None:
        customer.middle_name = data.middle_name.strip() or None
    if data.marketing_consent is not None:
        customer.marketing_consent = data.marketing_consent
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer)


@router.post("/contacts", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
def add_contact(
    data: ContactCreateRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChallengeResponse:
    identity = create_identity(db, customer, data.type, data.value, data.make_primary)
    message, code = create_contact_challenge(db, identity, settings)
    db.commit()
    return ChallengeResponse(
        message="Код подтверждения отправлен",
        delivery_id=message.id,
        debug_code=code if settings.delivery_debug else None,
    )


@router.post("/contacts/request-verification", response_model=ChallengeResponse)
def request_contact_verification(
    data: VerificationRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChallengeResponse:
    normalized = normalize_identity(data.type, data.value)
    identity = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.customer_id == customer.id,
            CustomerIdentity.tenant_key == customer.tenant_key,
            CustomerIdentity.type == data.type,
            CustomerIdentity.normalized_value == normalized,
        )
    )
    if not identity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контакт не найден")

    message, code = create_contact_challenge(db, identity, settings)
    db.commit()
    return ChallengeResponse(
        message="Код подтверждения отправлен",
        delivery_id=message.id,
        debug_code=code if settings.delivery_debug else None,
    )


@router.post("/contacts/confirm", response_model=PortalCustomerSchema)
def confirm_contact(
    data: VerificationConfirmRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PortalCustomerSchema:
    normalized = normalize_identity(data.type, data.value)
    identity = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.customer_id == customer.id,
            CustomerIdentity.tenant_key == customer.tenant_key,
            CustomerIdentity.type == data.type,
            CustomerIdentity.normalized_value == normalized,
        )
    )
    if not identity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контакт не найден")

    verify_contact_code(db, identity, data.code, settings)
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer)
