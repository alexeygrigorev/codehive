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
