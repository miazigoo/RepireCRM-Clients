from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import current_customer
from ..models import CustomerAccount, CustomerSession, MobileDevice, PushNotification
from ..schemas.mobile import (
    CustomerSessionSchema,
    MobileDeviceRegisterRequest,
    MobileDeviceSchema,
    PushTestRequest,
)
from ..security import utcnow

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


@router.post("/devices", response_model=MobileDeviceSchema)
def register_device(
    data: MobileDeviceRegisterRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> MobileDevice:
    device = db.scalar(
        select(MobileDevice).where(
            MobileDevice.tenant_key == customer.tenant_key,
            MobileDevice.platform == data.platform,
            MobileDevice.device_uid == data.device_uid,
        )
    )
    if device is None:
        device = MobileDevice(
            customer_id=customer.id,
            tenant_key=customer.tenant_key,
            platform=data.platform,
            device_uid=data.device_uid,
        )
        db.add(device)
    device.customer_id = customer.id
    device.push_token = data.push_token or device.push_token
    device.app_version = data.app_version or device.app_version
    device.locale = data.locale or device.locale or "ru-RU"
    device.is_active = True
    device.last_seen_at = utcnow()
    db.commit()
    db.refresh(device)
    return device


@router.get("/devices", response_model=list[MobileDeviceSchema])
def list_devices(
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> list[MobileDevice]:
    return list(
        db.scalars(
            select(MobileDevice)
            .where(
                MobileDevice.customer_id == customer.id,
                MobileDevice.tenant_key == customer.tenant_key,
            )
            .order_by(MobileDevice.last_seen_at.desc())
        )
    )


@router.get("/sessions", response_model=list[CustomerSessionSchema])
def list_sessions(
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> list[CustomerSession]:
    return list(
        db.scalars(
            select(CustomerSession)
            .where(
                CustomerSession.customer_id == customer.id,
                CustomerSession.tenant_key == customer.tenant_key,
            )
            .order_by(CustomerSession.created_at.desc())
        )
    )


@router.post("/push/test", response_model=dict)
def queue_test_push(
    data: PushTestRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> dict:
    active_devices = list(
        db.scalars(
            select(MobileDevice).where(
                MobileDevice.customer_id == customer.id,
                MobileDevice.tenant_key == customer.tenant_key,
                MobileDevice.is_active.is_(True),
            )
        )
    )
    for device in active_devices:
        db.add(
            PushNotification(
                customer_id=customer.id,
                device_id=device.id,
                tenant_key=customer.tenant_key,
                title=data.title,
                body=data.body,
                payload=data.payload,
            )
        )
    db.commit()
    return {"queued": len(active_devices)}
