"""
Security utilities: password hashing and JWT creation/verification.

- Passwords: hashed with bcrypt (one-way; cannot be reversed).
- Access token: a signed JWT that proves who you are. Short-lived.
- Refresh token: a long random string. We return the raw value to the client
  but store only its SHA-256 hash in the database.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt context for password hashing.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------- Passwords ----------
def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------- Access token (JWT) ----------
def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),   # "subject" = who this token belongs to
        "type": "access",
        "iat": now,            # issued at
        "exp": expire,         # expires at
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Returns the user_id if the token is valid, else None."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        return uuid.UUID(user_id) if user_id else None
    except (JWTError, ValueError):
        return None


# ---------- Refresh token (opaque random string) ----------
def generate_refresh_token() -> str:
    """A long, unguessable random string. This is the RAW value sent to the client."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """We store only this hash in the database, never the raw token."""
    return hashlib.sha256(raw_token.encode()).hexdigest()