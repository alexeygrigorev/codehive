"""Pydantic schemas for authentication endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Request body for POST /api/auth/register."""

    email: str = Field(..., max_length=255)
    username: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)


class UserLogin(BaseModel):
    """Request body for POST /api/auth/login."""

    email: str = Field(..., max_length=255)
    password: str


class TokenResponse(BaseModel):
    """Token pair returned on successful auth."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for POST /api/auth/refresh."""

    refresh_token: str


class UserRead(BaseModel):
    """Public user representation (never includes password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    is_admin: bool
    created_at: datetime
