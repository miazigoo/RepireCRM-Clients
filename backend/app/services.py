from datetime import timedelta
from decimal import Decimal
from typing import Any, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import AuthPolicy, Settings
from .models import (
    ClientAction,
    ClientMarketingSnapshot,
    ClientOrder,
    CustomerAccount,
    CustomerIdentity,
    OutboxMessage,
    PasswordResetChallenge,
    VerificationChallenge,
)
from .schemas import (
    ContactSchema,
    PortalAdditionalServiceSchema,
    PortalApprovalSchema,
    PortalCustomerSchema,
    PortalDeviceDetailSchema,
    PortalOrderSchema,
    PortalOrganizationSchema,
    PortalRepairStageSchema,
    PortalShopSchema,
    PortalBannerSchema,
    PortalMarketingSchema,
    PortalPaymentSchema,
    PortalPromotionItemSchema,
    PortalWarrantySchema,
    SyncMarketingRequest,
    SyncOrderItem,
)
from .sanitization import sanitize_optional_text, sanitize_payload, sanitize_plain_text
from .security import (
    detect_identity_type,
    generate_code,
    hash_code,
    hash_password,
    normalize_email,
    normalize_identity,
    normalize_phone,
    utcnow,
    validate_password,
    verify_code,
)


def serialize_contact(identity: CustomerIdentity) -> ContactSchema:
    return ContactSchema(
        id=identity.id,
        type=identity.type,  # type: ignore[arg-type]
        value=identity.value,
        normalized_value=identity.normalized_value,
        is_primary=identity.is_primary,
        verified_at=identity.verified_at,
    )


def serialize_customer(customer: CustomerAccount) -> PortalCustomerSchema:
    contacts = [
        serialize_contact(identity)
        for identity in sorted(customer.identities, key=lambda item: item.id)
    ]
    phone = next(
        (item.value for item in contacts if item.type == "phone" and item.is_primary), None
    )
    email = next(
        (item.value for item in contacts if item.type == "email" and item.is_primary), None
    )
    return PortalCustomerSchema(
        id=customer.id,
        first_name=customer.first_name,
        last_name=customer.last_name,
        middle_name=customer.middle_name,
        phone=phone,
        email=email,
        marketing_consent=customer.marketing_consent,
        avatar_url=customer.avatar,
        contacts=contacts,
    )


T = TypeVar("T", bound=BaseModel)


def _optional_model(model_cls: type[T], raw: Any) -> T | None:
    if not isinstance(raw, dict):
        return None
    try:
        return model_cls.model_validate(raw)
    except Exception:
        return None


def _additional_service_rows(raw_list: Any) -> list[PortalAdditionalServiceSchema]:
    if not isinstance(raw_list, list):
        return []
    rows: list[PortalAdditionalServiceSchema] = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        try:
            rows.append(PortalAdditionalServiceSchema.model_validate(raw))
        except Exception:
            name = sanitize_optional_text(raw.get("name"), max_length=500) or ""
            if name:
                rows.append(PortalAdditionalServiceSchema(name=name))
    return rows


def _portal_repair_stages(raw: Any) -> list[PortalRepairStageSchema]:
    if not isinstance(raw, list):
        return []
    out: list[PortalRepairStageSchema] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                out.append(PortalRepairStageSchema.model_validate(item))
            except Exception:
                continue
    return out


def _portal_approvals(raw: Any) -> list[PortalApprovalSchema]:
    if not isinstance(raw, list):
        return []
    out: list[PortalApprovalSchema] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                out.append(PortalApprovalSchema.model_validate(item))
            except Exception:
                continue
    return out


def _portal_payments(raw: Any) -> list[PortalPaymentSchema]:
    if not isinstance(raw, list):
        return []
    out: list[PortalPaymentSchema] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                out.append(PortalPaymentSchema.model_validate(item))
            except Exception:
                continue
    return out


def serialize_order(order: ClientOrder) -> PortalOrderSchema:
    snap = order.crm_snapshot or {}
    fin = snap["financial"] if isinstance(snap.get("financial"), dict) else {}

    def fin_float(key: str) -> float | None:
        v = fin.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    completed_raw = snap.get("completed_at")

    return PortalOrderSchema(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        status_display=order.status_display,
        priority=order.priority,
        device_title=order.device_title,
        problem_description=order.problem_description,
        diagnosis=order.diagnosis,
        work_description=order.work_description,
        cost_estimate=float(order.cost_estimate or 0),
        final_cost=float(order.final_cost) if order.final_cost is not None else None,
        remaining_payment=float(order.remaining_payment or 0),
        created_at=order.created_at,
        updated_at=order.updated_at,
        estimated_completion=order.estimated_completion,
        repair_stages=_portal_repair_stages(order.repair_stages),
        approvals=_portal_approvals(order.approvals),
        organization=_optional_model(PortalOrganizationSchema, snap.get("organization")),
        shop=_optional_model(PortalShopSchema, snap.get("shop")),
        device=_optional_model(PortalDeviceDetailSchema, snap.get("device")),
        warranty=_optional_model(PortalWarrantySchema, snap.get("warranty")),
        additional_services=_additional_service_rows(snap.get("additional_services")),
        payments=_portal_payments(snap.get("payments")),
        accessories=sanitize_optional_text(snap.get("accessories"), max_length=1000),
        device_condition=sanitize_optional_text(snap.get("device_condition"), max_length=1000),
        prepayment=fin_float("prepayment"),
        subtotal_before_discount=fin_float("subtotal_before_discount"),
        discount_total=fin_float("discount_total"),
        total_cost=fin_float("total_cost"),
        completed_at=completed_raw,
        assigned_master_name=order.assigned_master_name,
        assigned_master_avatar_url=order.assigned_master_avatar_url,
    )


def build_portal_marketing_schema(db: Session, tenant_key: str) -> PortalMarketingSchema:
    snap = db.scalar(
        select(ClientMarketingSnapshot).where(ClientMarketingSnapshot.tenant_key == tenant_key)
    )
    if not snap:
        return PortalMarketingSchema()
    promos: list[PortalPromotionItemSchema] = []
    for raw in snap.promotions or []:
        if not isinstance(raw, dict):
            continue
        try:
            promos.append(PortalPromotionItemSchema.model_validate(raw))
        except Exception:
            continue
    banner = None
    if isinstance(snap.banner, dict):
        try:
            banner = PortalBannerSchema.model_validate(snap.banner)
        except Exception:
            banner = None
    return PortalMarketingSchema(promotions=promos, banner=banner)


def _sanitize_sync_promotion(raw: dict[str, Any]) -> dict[str, Any]:
    cid = raw.get("crm_promotion_id") if raw.get("crm_promotion_id") is not None else raw.get("id")
    cid_int = 0
    if cid is not None:
        try:
            cid_int = int(cid)
        except (TypeError, ValueError):
            cid_int = 0
    codes = raw.get("promo_codes") or []
    if isinstance(codes, str):
        codes = [codes]
    clean_codes = [sanitize_plain_text(str(c), max_length=40).strip().upper() for c in codes if c][
        :20
    ]
    return {
        "crm_promotion_id": cid_int,
        "title": sanitize_plain_text(
            raw.get("title") or raw.get("name") or "Акция", max_length=200
        ),
        "description": sanitize_optional_text(raw.get("description"), max_length=4000) or "",
        "discount_type": sanitize_plain_text(
            str(raw.get("discount_type", "percent")), max_length=20
        ),
        "value": sanitize_plain_text(str(raw.get("value", "0")), max_length=32),
        "max_discount_amount": sanitize_optional_text(
            str(raw.get("max_discount_amount")), max_length=32
        ),
        "min_order_amount": sanitize_plain_text(
            str(raw.get("min_order_amount", "0")), max_length=32
        ),
        "starts_at": sanitize_optional_text(raw.get("starts_at"), max_length=80),
        "ends_at": sanitize_optional_text(raw.get("ends_at"), max_length=80),
        "promo_codes": clean_codes,
        "auto_apply": bool(raw.get("auto_apply", False)),
    }


def _sanitize_sync_banner(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return {
        "title": sanitize_plain_text(raw.get("title", ""), max_length=200),
        "subtitle": sanitize_plain_text(raw.get("subtitle", ""), max_length=500),
        "image_url": sanitize_optional_text(raw.get("image_url"), max_length=2000),
        "link_url": sanitize_optional_text(raw.get("link_url"), max_length=2000),
        "active": bool(raw.get("active", True)),
    }


def upsert_marketing_snapshot(
    db: Session,
    data: SyncMarketingRequest,
    tenant_key: str,
) -> ClientMarketingSnapshot:
    promos = [
        _sanitize_sync_promotion(p)
        for p in data.promotions
        if isinstance(p, dict) and _promotion_id_ok(p)
    ]
    banner = _sanitize_sync_banner(data.banner)
    row = db.scalar(
        select(ClientMarketingSnapshot).where(ClientMarketingSnapshot.tenant_key == tenant_key)
    )
    if row is None:
        row = ClientMarketingSnapshot(tenant_key=tenant_key, promotions=promos, banner=banner)
        db.add(row)
    else:
        row.promotions = promos
        row.banner = banner
    db.flush()
    return row


def _promotion_id_ok(raw: dict[str, Any]) -> bool:
    cid = raw.get("crm_promotion_id") if raw.get("crm_promotion_id") is not None else raw.get("id")
    if cid is None:
        return False
    try:
        return int(cid) > 0
    except (TypeError, ValueError):
        return False


def policy_allows_identity(policy: AuthPolicy, identity_type: str) -> bool:
    if policy == "phone_or_email":
        return identity_type in {"phone", "email"}
    if policy == "phone_only":
        return identity_type == "phone"
    if policy == "email_only":
        return identity_type == "email"
    return False


def validate_registration_contacts(
    settings: Settings, phone: str | None, email: str | None
) -> list[tuple[str, str, str]]:
    contacts: list[tuple[str, str, str]] = []
    if phone:
        contacts.append(("phone", phone.strip(), normalize_phone(phone)))
    if email:
        contacts.append(("email", email.strip(), normalize_email(email)))

    if settings.auth_policy == "phone_only" and not any(item[0] == "phone" for item in contacts):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Для регистрации нужен телефон")
    if settings.auth_policy == "email_only" and not any(item[0] == "email" for item in contacts):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Для регистрации нужен email")
    if settings.auth_policy == "phone_or_email" and not contacts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите телефон или email")

    disallowed = [
        item[0] for item in contacts if not policy_allows_identity(settings.auth_policy, item[0])
    ]
    if disallowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Этот способ регистрации отключен")

    return contacts


def find_identity_by_identifier(
    db: Session, identifier: str, tenant_key: str = "default"
) -> CustomerIdentity | None:
    identity_type = detect_identity_type(identifier)
    normalized = normalize_identity(identity_type, identifier)
    return db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.tenant_key == tenant_key,
            CustomerIdentity.type == identity_type,
            CustomerIdentity.normalized_value == normalized,
        )
    )


def create_identity(
    db: Session,
    customer: CustomerAccount,
    identity_type: str,
    value: str,
    make_primary: bool,
) -> CustomerIdentity:
    normalized = normalize_identity(identity_type, value)
    existing = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.tenant_key == customer.tenant_key,
            CustomerIdentity.type == identity_type,
            CustomerIdentity.normalized_value == normalized,
        )
    )
    if existing:
        if existing.customer_id == customer.id:
            return existing
        raise HTTPException(status.HTTP_409_CONFLICT, "Этот контакт уже используется")

    if make_primary:
        db.execute(
            select(CustomerIdentity).where(
                CustomerIdentity.customer_id == customer.id,
                CustomerIdentity.type == identity_type,
            )
        )
        for identity in customer.identities:
            if identity.type == identity_type:
                identity.is_primary = False

    identity = CustomerIdentity(
        customer=customer,
        tenant_key=customer.tenant_key,
        type=identity_type,
        value=value.strip(),
        normalized_value=normalized,
        is_primary=make_primary,
    )
    db.add(identity)
    db.flush()
    return identity


def create_contact_challenge(
    db: Session,
    identity: CustomerIdentity,
    settings: Settings,
    purpose: str = "contact",
) -> tuple[OutboxMessage, str]:
    code = generate_code()
    challenge = VerificationChallenge(
        identity=identity,
        code_hash=hash_code(code, settings.secret_key),
        purpose=purpose,
        expires_at=utcnow() + timedelta(minutes=settings.verification_ttl_minutes),
    )
    message = OutboxMessage(
        tenant_key=identity.tenant_key,
        channel=identity.type,
        destination=identity.value,
        purpose=purpose,
        payload={"code": code} if settings.delivery_debug else {},
    )
    db.add_all([challenge, message])
    db.flush()
    return message, code


def create_password_reset_challenge(
    db: Session,
    identity: CustomerIdentity,
    settings: Settings,
) -> tuple[OutboxMessage, str]:
    code = generate_code()
    challenge = PasswordResetChallenge(
        customer_id=identity.customer_id,
        identity=identity,
        code_hash=hash_code(code, settings.secret_key),
        expires_at=utcnow() + timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    message = OutboxMessage(
        tenant_key=identity.tenant_key,
        channel=identity.type,
        destination=identity.value,
        purpose="password_reset",
        payload={"code": code} if settings.delivery_debug else {},
    )
    db.add_all([challenge, message])
    db.flush()
    return message, code


def verify_contact_code(
    db: Session, identity: CustomerIdentity, code: str, settings: Settings
) -> None:
    challenge = db.scalar(
        select(VerificationChallenge)
        .where(
            VerificationChallenge.identity_id == identity.id,
            VerificationChallenge.consumed_at.is_(None),
            VerificationChallenge.expires_at >= utcnow(),
        )
        .order_by(VerificationChallenge.created_at.desc())
    )
    if not challenge or not verify_code(code, challenge.code_hash, settings.secret_key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный код подтверждения")

    challenge.consumed_at = utcnow()
    identity.verified_at = utcnow()
    link_orders_for_customer(db, identity.customer)
    db.flush()


def reset_password(
    db: Session, identifier: str, code: str, new_password: str, settings: Settings
) -> None:
    identity = find_identity_by_identifier(db, identifier, settings.tenant_key)
    if not identity:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный код восстановления")

    challenge = db.scalar(
        select(PasswordResetChallenge)
        .where(
            PasswordResetChallenge.identity_id == identity.id,
            PasswordResetChallenge.consumed_at.is_(None),
            PasswordResetChallenge.expires_at >= utcnow(),
        )
        .order_by(PasswordResetChallenge.created_at.desc())
    )
    if not challenge or not verify_code(code, challenge.code_hash, settings.secret_key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный код восстановления")

    validate_password(new_password)
    challenge.consumed_at = utcnow()
    identity.customer.password_hash = hash_password(new_password)
    db.flush()


def verified_identity_values(customer: CustomerAccount) -> tuple[list[str], list[str]]:
    phones = [
        identity.normalized_value
        for identity in customer.identities
        if identity.type == "phone" and identity.verified_at is not None
    ]
    emails = [
        identity.normalized_value
        for identity in customer.identities
        if identity.type == "email" and identity.verified_at is not None
    ]
    return phones, emails


def link_orders_for_customer(db: Session, customer: CustomerAccount) -> int:
    phones, emails = verified_identity_values(customer)
    if not phones and not emails:
        return 0

    filters = []
    if phones:
        filters.append(ClientOrder.customer_phone.in_(phones))
    if emails:
        filters.append(ClientOrder.customer_email.in_(emails))
    orders = db.scalars(
        select(ClientOrder).where(
            ClientOrder.tenant_key == customer.tenant_key,
            or_(*filters),
        )
    ).all()
    linked = 0
    for order in orders:
        if order.customer_id != customer.id:
            order.customer_id = customer.id
            linked += 1
    db.flush()
    return linked


def customer_order_query(db: Session, customer: CustomerAccount, include_unverified: bool = False):
    phones, emails = verified_identity_values(customer)
    filters = [ClientOrder.customer_id == customer.id]
    if include_unverified:
        phones = [
            identity.normalized_value
            for identity in customer.identities
            if identity.type == "phone"
        ]
        emails = [
            identity.normalized_value
            for identity in customer.identities
            if identity.type == "email"
        ]
    if phones:
        filters.append(ClientOrder.customer_phone.in_(phones))
    if emails:
        filters.append(ClientOrder.customer_email.in_(emails))
    return (
        select(ClientOrder)
        .where(ClientOrder.tenant_key == customer.tenant_key)
        .where(or_(*filters))
        .order_by(ClientOrder.created_at.desc())
    )


def build_crm_snapshot_from_sync(item: SyncOrderItem) -> dict[str, Any]:
    snap: dict[str, Any] = {}
    if item.organization:
        snap["organization"] = sanitize_payload(item.organization)
    if item.shop:
        snap["shop"] = sanitize_payload(item.shop)
    if item.device:
        snap["device"] = sanitize_payload(item.device)

    acc = sanitize_optional_text(item.accessories, max_length=1000)
    if acc:
        snap["accessories"] = acc
    dc = sanitize_optional_text(item.device_condition, max_length=1000)
    if dc:
        snap["device_condition"] = dc

    warranty: dict[str, Any] = {}
    if item.warranty_days is not None:
        warranty["warranty_days"] = item.warranty_days
    if item.warranty_until is not None:
        warranty["warranty_until"] = item.warranty_until.isoformat()
    if item.warranty_active is not None:
        warranty["warranty_active"] = item.warranty_active
    if item.is_warranty_case is not None:
        warranty["is_warranty_case"] = item.is_warranty_case
    if item.warranty_parent_order_id is not None:
        warranty["warranty_parent_order_id"] = item.warranty_parent_order_id
    parent_num = sanitize_optional_text(item.warranty_parent_order_number, max_length=80)
    if parent_num:
        warranty["warranty_parent_order_number"] = parent_num
    reason = sanitize_optional_text(item.warranty_reason, max_length=500)
    if reason:
        warranty["warranty_reason"] = reason
    if warranty:
        snap["warranty"] = warranty

    if item.additional_services:
        snap["additional_services"] = [
            sanitize_payload(entry) for entry in item.additional_services
        ]
    if item.payments:
        snap["payments"] = [sanitize_payload(entry) for entry in item.payments]

    financial: dict[str, Any] = {}
    if item.prepayment is not None:
        financial["prepayment"] = float(item.prepayment)
    if item.subtotal_before_discount is not None:
        financial["subtotal_before_discount"] = float(item.subtotal_before_discount)
    if item.discount_total is not None:
        financial["discount_total"] = float(item.discount_total)
    if item.total_cost is not None:
        financial["total_cost"] = float(item.total_cost)
    if financial:
        snap["financial"] = financial

    if item.completed_at is not None:
        snap["completed_at"] = item.completed_at.isoformat()

    return snap


def normalize_sync_contact(identity_type: str, value: str | None) -> str | None:
    if not value:
        return None
    try:
        return normalize_identity(identity_type, value)
    except ValueError:
        return None


def upsert_synced_order(
    db: Session, item: SyncOrderItem, tenant_key: str = "default"
) -> tuple[ClientOrder, bool, bool]:
    customer_payload = sanitize_payload(item.customer or {})
    device_payload = sanitize_payload(item.device or {})
    normalized_phone = normalize_sync_contact(
        "phone", item.customer_phone or customer_payload.get("phone")
    )
    normalized_email = normalize_sync_contact(
        "email", item.customer_email or customer_payload.get("email")
    )
    external_id = sanitize_optional_text(item.external_id, max_length=120) or (
        str(item.crm_order_id) if item.crm_order_id is not None else None
    )
    device_title = sanitize_optional_text(item.device_title, max_length=255) or _device_title(
        device_payload
    )
    query = select(ClientOrder).where(
        ClientOrder.tenant_key == tenant_key,
        ClientOrder.order_number == item.order_number,
    )
    if external_id:
        query = select(ClientOrder).where(
            ClientOrder.tenant_key == tenant_key,
            or_(
                ClientOrder.external_id == external_id,
                ClientOrder.order_number == item.order_number,
            ),
        )
    order = db.scalar(query)
    created = order is None
    if order is None:
        order = ClientOrder(
            tenant_key=tenant_key,
            order_number=item.order_number,
            device_title=device_title,
            problem_description=item.problem_description,
        )
        db.add(order)

    order.external_id = external_id or order.external_id
    order.crm_order_id = item.crm_order_id
    order.customer_phone = normalized_phone
    order.customer_email = normalized_email
    order.status = sanitize_plain_text(item.status, max_length=40) or "received"
    order.status_display = (
        sanitize_optional_text(item.status_display, max_length=80) or order.status
    )
    order.priority = sanitize_plain_text(item.priority, max_length=40) or "normal"
    order.device_title = device_title
    order.problem_description = sanitize_plain_text(item.problem_description, max_length=5000)
    order.diagnosis = sanitize_optional_text(item.diagnosis, max_length=5000)
    order.work_description = sanitize_optional_text(item.work_description, max_length=5000)
    cost_estimate = _money(item.cost_estimate, 0)
    final_cost = _money(item.final_cost if item.final_cost is not None else item.total_cost, None)
    order.cost_estimate = cost_estimate
    order.final_cost = final_cost
    order.remaining_payment = _money(
        item.remaining_payment,
        final_cost if final_cost is not None else cost_estimate,
    )
    order.estimated_completion = item.estimated_completion
    order.repair_stages = [_normalize_stage(stage) for stage in item.repair_stages]
    order.approvals = [_normalize_approval(approval) for approval in item.approvals]
    order.synced_at = utcnow()
    master = item.assigned_master or {}
    order.assigned_master_name = master.get("name") or master.get("display_name")
    order.assigned_master_avatar_url = master.get("avatar_url")
    order.crm_snapshot = build_crm_snapshot_from_sync(item)

    linked = link_order_to_existing_customer(db, order)
    db.flush()
    return order, created, linked


def link_order_to_existing_customer(db: Session, order: ClientOrder) -> bool:
    values: list[str] = []
    if order.customer_phone:
        values.append(order.customer_phone)
    if order.customer_email:
        values.append(order.customer_email)
    if not values:
        return False

    identity = db.scalar(
        select(CustomerIdentity).where(
            CustomerIdentity.tenant_key == order.tenant_key,
            CustomerIdentity.normalized_value.in_(values),
            CustomerIdentity.verified_at.is_not(None),
        )
    )
    if identity and order.customer_id != identity.customer_id:
        order.customer_id = identity.customer_id
        return True
    return False


def create_client_order_action(
    db: Session, customer: CustomerAccount, payload: dict
) -> ClientOrder:
    payload = sanitize_payload(payload)
    device_title = " ".join(
        part
        for part in [
            payload.get("brand"),
            payload.get("model_name"),
            payload.get("color"),
            payload.get("storage_capacity"),
        ]
        if part
    )
    order = ClientOrder(
        order_number=f"ONLINE-{int(utcnow().timestamp())}",
        tenant_key=customer.tenant_key,
        customer_id=customer.id,
        status="received",
        status_display="Заявка отправлена",
        priority="normal",
        device_title=device_title or payload.get("device_type", "Устройство"),
        problem_description=payload["problem_description"],
        cost_estimate=float(payload.get("cost_estimate") or 0),
        remaining_payment=float(payload.get("cost_estimate") or 0),
        source="portal",
        crm_snapshot={
            "device": sanitize_payload(
                {
                    "device_type": payload.get("device_type"),
                    "brand": payload.get("brand"),
                    "model_name": payload.get("model_name"),
                    "serial_number": payload.get("serial_number"),
                    "imei": payload.get("imei"),
                    "color": payload.get("color"),
                    "storage_capacity": payload.get("storage_capacity"),
                }
            ),
            "accessories": sanitize_optional_text(payload.get("accessories"), max_length=1000),
            "device_condition": sanitize_optional_text(
                payload.get("device_condition"), max_length=1000
            ),
            "portal_self_service": True,
        },
    )
    db.add(order)
    db.flush()
    action = ClientAction(
        customer_id=customer.id,
        order_id=order.id,
        tenant_key=customer.tenant_key,
        action_type="repair_request.created",
        payload={
            "client_order_id": order.id,
            "customer": _customer_payload(customer),
            "device": {
                "device_type": payload.get("device_type"),
                "brand": payload.get("brand"),
                "model_name": payload.get("model_name"),
                "serial_number": payload.get("serial_number"),
                "imei": payload.get("imei"),
                "color": payload.get("color"),
                "storage_capacity": payload.get("storage_capacity"),
            },
            "order": payload,
            "order_number": order.order_number,
        },
    )
    db.add(action)
    db.flush()
    return order


def mark_client_action_synced(
    action: ClientAction,
    status_value: str,
    crm_order_id: int | None = None,
    crm_order_number: str | None = None,
    error: str = "",
) -> None:
    action.status = "synced" if status_value in {"applied", "synced"} else "failed"
    action.sync_status = status_value
    action.sync_error = error
    action.synced_at = utcnow()

    if action.order:
        if crm_order_id is not None:
            action.order.crm_order_id = crm_order_id
            action.order.external_id = str(crm_order_id)
        clean_number = sanitize_optional_text(crm_order_number, max_length=80)
        if clean_number:
            action.order.order_number = clean_number
        if action.status == "synced":
            action.order.status = "received"
            action.order.status_display = "Принята сервисом"
        elif error:
            action.order.status_display = "Требует проверки"
        action.order.synced_at = utcnow()


def find_accessible_order(db: Session, customer: CustomerAccount, order_id: int) -> ClientOrder:
    link_orders_for_customer(db, customer)
    order = db.scalar(customer_order_query(db, customer).where(ClientOrder.id == order_id))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заказ не найден")
    return order


def iter_accessible_orders(
    db: Session,
    customer: CustomerAccount,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list, int]:
    """Return (orders, total_count) for pagination."""
    link_orders_for_customer(db, customer)
    base_q = customer_order_query(db, customer)
    from sqlalchemy import func

    total = db.scalar(select(func.count()).select_from(base_q.subquery())) or 0
    orders = db.scalars(base_q.limit(limit).offset(offset)).all()
    return list(orders), total


def _customer_payload(customer: CustomerAccount) -> dict:
    phone = next(
        (
            identity.normalized_value
            for identity in customer.identities
            if identity.type == "phone" and identity.is_primary
        ),
        "",
    )
    email = next(
        (
            identity.normalized_value
            for identity in customer.identities
            if identity.type == "email" and identity.is_primary
        ),
        "",
    )
    return {
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "middle_name": customer.middle_name or "",
        "phone": phone,
        "email": email,
        "marketing_consent": customer.marketing_consent,
    }


def _device_title(device_payload: dict) -> str:
    parts = [
        device_payload.get("brand"),
        device_payload.get("model_name"),
        device_payload.get("color"),
        device_payload.get("storage_capacity"),
    ]
    return (
        sanitize_plain_text(" ".join(str(part).strip() for part in parts if part), max_length=255)
        or "Устройство"
    )


def _normalize_stage(stage: dict) -> dict:
    stage = sanitize_payload(stage)
    return {
        "id": stage.get("crm_stage_id") or stage.get("id"),
        "title": sanitize_optional_text(stage.get("title"), max_length=160) or "Этап ремонта",
        "description": sanitize_optional_text(stage.get("description"), max_length=2000),
        "photo_url": sanitize_optional_text(stage.get("photo_url"), max_length=1000),
        "created_at": stage.get("created_at") or utcnow().isoformat(),
    }


def _normalize_approval(approval: dict) -> dict:
    approval = sanitize_payload(approval)
    amount = approval.get("amount") or 0
    if isinstance(amount, Decimal):
        amount = float(amount)
    return {
        "id": approval.get("crm_approval_id") or approval.get("id"),
        "crm_approval_id": approval.get("crm_approval_id") or approval.get("id"),
        "title": sanitize_optional_text(approval.get("title"), max_length=160) or "Согласование",
        "description": sanitize_optional_text(approval.get("description"), max_length=2000),
        "amount": float(amount),
        "status": sanitize_optional_text(approval.get("status"), max_length=40) or "pending",
        "status_display": sanitize_optional_text(
            approval.get("status_display") or approval.get("status"), max_length=80
        )
        or "Ожидает",
        "customer_comment": sanitize_optional_text(
            approval.get("customer_comment"), max_length=2000
        ),
        "decided_at": approval.get("decided_at") or None,
        "created_at": approval.get("created_at") or utcnow().isoformat(),
    }


def _money(value, default):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
