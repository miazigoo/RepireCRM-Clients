from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_customer
from ..models import ClientAction, CustomerAccount, FieldVisitRequest
from ..sanitization import sanitize_optional_text, sanitize_plain_text

router = APIRouter(prefix="/api/portal/field-visit", tags=["portal-field-visit"])


class FieldVisitCreateRequest(BaseModel):
    address: str = Field(min_length=3, max_length=1000)
    lat: float | None = None
    lng: float | None = None
    preferred_date: str | None = Field(default=None, max_length=20)
    preferred_time: str | None = Field(default=None, max_length=20)
    description: str = Field(default="", max_length=2000)
    device_title: str = Field(default="", max_length=255)
    problem_description: str = Field(default="", max_length=5000)

    @field_validator(
        "address",
        "preferred_date",
        "preferred_time",
        "description",
        "device_title",
        "problem_description",
        mode="before",
    )
    @classmethod
    def sanitize_text(cls, value):
        return sanitize_optional_text(value, max_length=5000) or ""


class FieldVisitRequestSchema(BaseModel):
    id: int
    address: str
    lat: float | None = None
    lng: float | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    description: str
    device_title: str
    problem_description: str
    status: str
    zone_name: str | None = None
    price_estimate: float | None = None
    created_at: datetime


def _serialize(r: FieldVisitRequest) -> FieldVisitRequestSchema:
    return FieldVisitRequestSchema(
        id=r.id,
        address=r.address,
        lat=r.lat,
        lng=r.lng,
        preferred_date=r.preferred_date,
        preferred_time=r.preferred_time,
        description=r.description,
        device_title=r.device_title,
        problem_description=r.problem_description,
        status=r.status,
        zone_name=r.zone_name,
        price_estimate=r.price_estimate,
        created_at=r.created_at,
    )


def _primary_identity(customer: CustomerAccount, identity_type: str) -> str:
    primary = next(
        (
            identity.value
            for identity in customer.identities
            if identity.type == identity_type and identity.is_primary
        ),
        "",
    )
    if primary:
        return primary
    return next(
        (identity.value for identity in customer.identities if identity.type == identity_type),
        "",
    )


def _field_visit_action_payload(
    request_row: FieldVisitRequest,
    customer: CustomerAccount,
) -> dict:
    field_visit = {
        "id": request_row.id,
        "address": request_row.address,
        "lat": request_row.lat,
        "lng": request_row.lng,
        "preferred_date": request_row.preferred_date,
        "preferred_time": request_row.preferred_time,
        "description": request_row.description,
        "device_title": request_row.device_title,
        "problem_description": request_row.problem_description,
        "status": request_row.status,
        "created_at": request_row.created_at.isoformat() if request_row.created_at else None,
    }
    return {
        "field_visit_request_id": request_row.id,
        "field_visit": field_visit,
        "customer": {
            "first_name": sanitize_plain_text(customer.first_name, max_length=80),
            "last_name": sanitize_plain_text(customer.last_name, max_length=80),
            "middle_name": sanitize_plain_text(customer.middle_name or "", max_length=80),
            "phone": _primary_identity(customer, "phone"),
            "email": _primary_identity(customer, "email"),
            "marketing_consent": customer.marketing_consent,
        },
    }


@router.post("", response_model=FieldVisitRequestSchema, status_code=status.HTTP_201_CREATED)
def create_field_visit_request(
    data: FieldVisitCreateRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> FieldVisitRequestSchema:
    if not data.address.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Укажите адрес")

    req = FieldVisitRequest(
        customer_id=customer.id,
        tenant_key=customer.tenant_key,
        address=data.address.strip(),
        lat=data.lat,
        lng=data.lng,
        preferred_date=data.preferred_date,
        preferred_time=data.preferred_time,
        description=data.description,
        device_title=data.device_title,
        problem_description=data.problem_description,
        status="pending",
    )
    db.add(req)
    db.flush()
    db.add(
        ClientAction(
            customer_id=customer.id,
            tenant_key=customer.tenant_key,
            action_type="field_visit.created",
            payload=_field_visit_action_payload(req, customer),
        )
    )
    db.commit()
    db.refresh(req)
    return _serialize(req)


@router.get("", response_model=list[FieldVisitRequestSchema])
def get_my_field_visit_requests(
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> list[FieldVisitRequestSchema]:
    requests = (
        db.query(FieldVisitRequest)
        .filter(
            FieldVisitRequest.customer_id == customer.id,
            FieldVisitRequest.tenant_key == customer.tenant_key,
        )
        .order_by(FieldVisitRequest.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in requests]
