"""Pydantic schemas for push notification endpoints."""

from pydantic import BaseModel


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class PushSendRequest(BaseModel):
    title: str
    body: str
    url: str = ""


class PushSendResponse(BaseModel):
    delivered: int


class DeviceRegisterRequest(BaseModel):
    token: str
    platform: str
    device_id: str | None = None


class DeviceRegisterResponse(BaseModel):
    status: str


class DeviceUnregisterRequest(BaseModel):
    token: str
