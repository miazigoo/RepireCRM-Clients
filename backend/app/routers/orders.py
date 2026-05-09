from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..dependencies import current_customer
from ..models import ClientAction, ClientOrder, CustomerAccount
from ..sanitization import sanitize_plain_text
from ..schemas import (
    ApprovalDecisionRequest,
    OrderCreateRequest,
    PortalApprovalSchema,
    PortalOrderSchema,
    PublicTrackRequest,
)
from ..security import normalize_email, normalize_phone, utcnow
from ..services import (
    create_client_order_action,
    find_accessible_order,
    iter_accessible_orders,
    serialize_order,
)

router = APIRouter(prefix="/api/portal", tags=["portal-orders"])


@router.get("/orders", response_model=list[PortalOrderSchema])
def list_orders(
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> list[PortalOrderSchema]:
    return [serialize_order(order) for order in iter_accessible_orders(db, customer)]


@router.post("/orders", response_model=PortalOrderSchema, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreateRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> PortalOrderSchema:
    payload = data.model_dump()
    order = create_client_order_action(db, customer, payload)
    db.commit()
    db.refresh(order)
    return serialize_order(order)


@router.get("/orders/{order_id}", response_model=PortalOrderSchema)
def get_order(
    order_id: int,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> PortalOrderSchema:
    return serialize_order(find_accessible_order(db, customer, order_id))


@router.post("/track", response_model=PortalOrderSchema)
def track_order(
    data: PublicTrackRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PortalOrderSchema:
    filters = [
        ClientOrder.tenant_key == settings.tenant_key,
        ClientOrder.order_number == data.order_number.strip(),
    ]
    if data.phone:
        filters.append(ClientOrder.customer_phone == normalize_phone(data.phone))
    elif data.email:
        filters.append(ClientOrder.customer_email == normalize_email(data.email))
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите телефон или email")

    order = db.scalar(select(ClientOrder).where(*filters))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заказ не найден")
    return serialize_order(order)


@router.post("/approvals/{approval_id}/approve", response_model=PortalApprovalSchema)
def approve_approval(
    approval_id: str,
    data: ApprovalDecisionRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> PortalApprovalSchema:
    return decide_approval(db, customer, approval_id, "approved", data.comment or "")


@router.post("/approvals/{approval_id}/reject", response_model=PortalApprovalSchema)
def reject_approval(
    approval_id: str,
    data: ApprovalDecisionRequest,
    customer: CustomerAccount = Depends(current_customer),
    db: Session = Depends(get_db),
) -> PortalApprovalSchema:
    return decide_approval(db, customer, approval_id, "rejected", data.comment or "")


def decide_approval(
    db: Session,
    customer: CustomerAccount,
    approval_id: str,
    decision: str,
    comment: str,
) -> PortalApprovalSchema:
    comment = sanitize_plain_text(comment, max_length=2000)
    for order in iter_accessible_orders(db, customer):
        approvals = list(order.approvals or [])
        for approval in approvals:
            if str(approval.get("id")) != str(approval_id):
                continue
            if approval.get("status") != "pending":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "По этому согласованию уже принято решение"
                )

            approval["status"] = decision
            approval["status_display"] = "Согласовано" if decision == "approved" else "Отклонено"
            approval["customer_comment"] = comment.strip() or None
            approval["decided_at"] = utcnow().isoformat()
            order.approvals = approvals
            action = ClientAction(
                customer_id=customer.id,
                order_id=order.id,
                tenant_key=customer.tenant_key,
                action_type="approval.decided",
                payload={
                    "crm_approval_id": approval.get("crm_approval_id") or approval_id,
                    "status": decision,
                    "comment": comment.strip(),
                    "order_number": order.order_number,
                    "crm_order_id": order.crm_order_id,
                },
            )
            db.add(action)
            db.commit()
            return PortalApprovalSchema(**approval)

    raise HTTPException(status.HTTP_404_NOT_FOUND, "Согласование не найдено")
