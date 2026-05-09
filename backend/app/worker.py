import logging
import time

import httpx
from sqlalchemy import delete, select

from .config import get_settings
from .database import SessionLocal
from .models import PushNotification, RateLimitBucket
from .security import utcnow

logger = logging.getLogger("client-portal-worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_forever() -> None:
    settings = get_settings()
    logger.info("client portal worker started")
    while True:
        try:
            trigger_crm_sync(settings)
            process_push_queue(settings)
            cleanup_rate_limits()
        except Exception:
            logger.exception("worker iteration failed")
        time.sleep(settings.sync_worker_interval_seconds)


def trigger_crm_sync(settings) -> None:
    if not settings.crm_base_url or not settings.crm_api_key:
        return
    url = settings.crm_base_url.rstrip("/") + "/api/client-sync/run"
    headers = {
        "Authorization": f"Bearer {settings.crm_api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "push": True,
        "pull": True,
        "limit": settings.sync_worker_batch_size,
    }
    response = httpx.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code >= 400:
        logger.warning("CRM sync trigger failed: %s %s", response.status_code, response.text[:500])
        return
    logger.info("CRM sync triggered: %s", response.text[:500])


def process_push_queue(settings) -> None:
    with SessionLocal() as db:
        notifications = list(
            db.scalars(
                select(PushNotification)
                .where(PushNotification.status == "pending")
                .order_by(PushNotification.created_at.asc())
                .limit(100)
            )
        )
        for notification in notifications:
            if settings.mobile_push_provider == "stub" or not settings.mobile_push_enabled:
                notification.status = "sent"
                notification.provider_message_id = f"stub-{notification.id}"
                notification.sent_at = utcnow()
            else:
                notification.status = "failed"
                notification.error_message = "Push provider adapter is not configured yet"
        if notifications:
            db.commit()
            logger.info("processed push notifications: %s", len(notifications))


def cleanup_rate_limits() -> None:
    with SessionLocal() as db:
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at < utcnow()))
        db.commit()


if __name__ == "__main__":
    run_forever()
