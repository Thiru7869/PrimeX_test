"""
Request and response shapes for authentication.
Pydantic validates incoming data and controls what we send back.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Incoming requests ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# ---------- Outgoing responses ----------
class UserResponse(BaseModel):
    # from_attributes lets us build this directly from a SQLAlchemy User object.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    role: str
    is_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """Returned on register and login."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AccessTokenResponse(BaseModel):
    """Returned on refresh."""
    access_token: str
    token_type: str = "bearer"