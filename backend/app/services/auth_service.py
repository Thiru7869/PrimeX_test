"""
Authentication business logic. Orchestrates repositories + security utilities.
Raises HTTPException on failure so the API layer can return clean error codes.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)

    async def register(
        self, email: str, password: str, display_name: str | None
    ) -> tuple[User, str, str]:
        existing = await self.users.get_by_email(email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        user = await self.users.create(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
        )
        access_token, raw_refresh = await self._issue_tokens(user.id)
        await self.db.commit()
        return user, access_token, raw_refresh

    async def login(self, email: str, password: str) -> tuple[User, str, str]:
        user = await self.users.get_by_email(email)
        # Same error whether email is wrong or password is wrong (don't leak which).
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        access_token, raw_refresh = await self._issue_tokens(user.id)
        await self.db.commit()
        return user, access_token, raw_refresh

    async def refresh(self, raw_refresh_token: str) -> str:
        """Validate the refresh token, rotate it, return a new access token."""
        if not raw_refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token.",
            )
        token_hash = hash_refresh_token(raw_refresh_token)
        stored = await self.tokens.get_by_hash(token_hash)

        now = datetime.now(timezone.utc)
        if (
            not stored
            or stored.revoked
            or stored.expires_at < now
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        # Rotation: kill the old token, issue a brand new one.
        await self.tokens.revoke(token_hash)
        access_token, new_raw_refresh = await self._issue_tokens(stored.user_id)
        await self.db.commit()
        # NOTE: we return the new refresh token too (the API sets it as a cookie).
        self._last_refresh = new_raw_refresh
        return access_token

    async def logout(self, raw_refresh_token: str | None) -> None:
        if raw_refresh_token:
            await self.tokens.revoke(hash_refresh_token(raw_refresh_token))
            await self.db.commit()

    async def _issue_tokens(self, user_id: uuid.UUID) -> tuple[str, str]:
        """Create a fresh access token + a fresh refresh token (stored hashed)."""
        access_token = create_access_token(user_id)
        raw_refresh = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.tokens.create(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=expires_at,
        )
        return access_token, raw_refresh