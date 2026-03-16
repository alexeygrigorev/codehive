"""Push notification endpoints: subscribe, unsubscribe, send."""

import json
import logging

from fastapi import APIRouter, Depends, status
from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.push import (
    DeviceRegisterRequest,
    DeviceUnregisterRequest,
    PushSendRequest,
    PushSendResponse,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
)
from codehive.config import Settings
from codehive.db.models import DeviceToken, PushSubscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["push"])


def _get_settings() -> Settings:
    return Settings()


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: PushSubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store a push subscription. Upserts on duplicate endpoint."""
    stmt = select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        sub = PushSubscription(
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )
        db.add(sub)

    await db.commit()
    return {"status": "subscribed"}


@router.post("/unsubscribe", status_code=status.HTTP_200_OK)
async def unsubscribe(
    payload: PushUnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a push subscription by endpoint. Idempotent."""
    stmt = delete(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    await db.execute(stmt)
    await db.commit()
    return {"status": "unsubscribed"}


@router.post("/send", status_code=status.HTTP_200_OK, response_model=PushSendResponse)
async def send_push(
    payload: PushSendRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(_get_settings),
) -> PushSendResponse:
    """Send a web push notification to all stored subscriptions (admin/test endpoint)."""
    stmt = select(PushSubscription)
    result = await db.execute(stmt)
    subscriptions = list(result.scalars().all())

    delivered = 0
    stale_ids: list = []

    notification_data = json.dumps(
        {"title": payload.title, "body": payload.body, "url": payload.url}
    )

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=notification_data,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_mailto},
            )
            delivered += 1
        except WebPushException as exc:
            if getattr(exc, "response", None) is not None and exc.response.status_code == 410:
                stale_ids.append(sub.id)
                logger.info("Removing stale push subscription: %s", sub.endpoint)
            else:
                logger.warning("Push delivery failed for %s: %s", sub.endpoint, exc)

    # Clean up stale subscriptions
    if stale_ids:
        stmt_del = delete(PushSubscription).where(PushSubscription.id.in_(stale_ids))
        await db.execute(stmt_del)
        await db.commit()

    return PushSendResponse(delivered=delivered)


@router.post("/register-device", status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register an FCM device token. Upserts on duplicate token."""
    stmt = select(DeviceToken).where(DeviceToken.token == payload.token)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.platform = payload.platform
        existing.device_id = payload.device_id
    else:
        device = DeviceToken(
            token=payload.token,
            platform=payload.platform,
            device_id=payload.device_id,
        )
        db.add(device)

    await db.commit()
    return {"status": "registered"}


@router.post("/unregister-device", status_code=status.HTTP_200_OK)
async def unregister_device(
    payload: DeviceUnregisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove an FCM device token. Idempotent."""
    stmt = delete(DeviceToken).where(DeviceToken.token == payload.token)
    await db.execute(stmt)
    await db.commit()
    return {"status": "unregistered"}
