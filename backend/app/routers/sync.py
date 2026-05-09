from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_sync_token, sync_tenant_key
from ..models import ClientAction
from ..schemas import (
    MarkActionSyncedRequest,
    SyncActionsResponse,
    SyncMarketingRequest,
    SyncMarketingResponse,
    SyncOrderResponseItem,
    SyncOrdersRequest,
    SyncOrdersResponse,
)
from ..services import (
    mark_client_action_synced,
    upsert_marketing_snapshot,
    upsert_synced_order,
)

router = APIRouter(
    prefix="/api/sync", tags=["crm-sync"], dependencies=[Depends(require_sync_token)]
)


@router.post("/orders/upsert", response_model=SyncOrdersResponse)
def upsert_orders(
    data: SyncOrdersRequest,
    header_tenant_key: str = Depends(sync_tenant_key),
    db: Session = Depends(get_db),
) -> SyncOrdersResponse:
    tenant_key = data.tenant_key or header_tenant_key
    items: list[SyncOrderResponseItem] = []
    for item in data.orders:
        order, _, _ = upsert_synced_order(db, item, tenant_key=tenant_key)
        items.append(
            SyncOrderResponseItem(
                crm_order_id=item.crm_order_id,
                remote_order_id=str(order.id),
            )
        )
    db.commit()
    return SyncOrdersResponse(orders=items)


@router.post("/marketing/upsert", response_model=SyncMarketingResponse)
def upsert_marketing(
    data: SyncMarketingRequest,
    header_tenant_key: str = Depends(sync_tenant_key),
    db: Session = Depends(get_db),
) -> SyncMarketingResponse:
    tenant_key = data.tenant_key or header_tenant_key
    snap = upsert_marketing_snapshot(db, data, tenant_key=tenant_key)
    db.commit()
    return SyncMarketingResponse(
        promotions_count=len(snap.promotions),
        has_banner=bool(snap.banner),
    )


@router.get("/actions", response_model=SyncActionsResponse)
def list_actions(
    limit: int = 100,
    sync_status: str = Query("pending", alias="status"),
    tenant_key: str = Depends(sync_tenant_key),
    db: Session = Depends(get_db),
) -> SyncActionsResponse:
    actions = list(
        db.scalars(
            select(ClientAction)
            .where(ClientAction.tenant_key == tenant_key, ClientAction.status == sync_status)
            .order_by(ClientAction.created_at.asc())
            .limit(max(1, min(limit, 500)))
        )
    )
    return SyncActionsResponse(actions=[serialize_sync_action(action) for action in actions])


@router.post("/actions/{action_id}/mark-synced", response_model=dict)
def mark_action_synced(
    action_id: str,
    data: MarkActionSyncedRequest,
    tenant_key: str = Depends(sync_tenant_key),
    db: Session = Depends(get_db),
) -> dict:
    numeric_id = (
        int(action_id.removeprefix("act-")) if action_id.removeprefix("act-").isdigit() else None
    )
    action = db.get(ClientAction, numeric_id) if numeric_id is not None else None
    if action is None or action.tenant_key != tenant_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Действие не найдено")
    mark_client_action_synced(
        action,
        status_value=data.status,
        crm_order_id=data.crm_order_id,
        crm_order_number=data.crm_order_number,
        error=data.error or "",
    )
    db.commit()
    return {"ok": True}


def serialize_sync_action(action: ClientAction) -> dict:
    return {
        "id": f"act-{action.id}",
        "type": action.action_type,
        "order_id": action.order_id,
        "payload": action.payload,
    }
