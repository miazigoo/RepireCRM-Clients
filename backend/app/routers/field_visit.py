from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_customer
from ..models import CustomerAccount, FieldVisitRequest

router = APIRouter(prefix="/api/portal/field-visit", tags=["portal-field-visit"])


class FieldVisitCreateRequest(BaseModel):
    address: str
    lat: float | None = None
    lng: float | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    description: str = ""
    device_title: str = ""
    problem_description: str = ""


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
