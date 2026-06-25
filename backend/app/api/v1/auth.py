"""
Authentication endpoints: register, login, refresh, logout, me.
The access token is returned in the JSON body (frontend keeps it in memory).
The refresh token is set as an HttpOnly cookie (JavaScript cannot read it).
"""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()

REFRESH_COOKIE_NAME = "primex_refresh"
REFRESH_PATH = "/api/v1/auth"  # cookie is only sent to auth endpoints


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    is_prod = settings.ENVIRONMENT != "development"
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=is_prod,                       # True in prod (HTTPS only)
        samesite="none" if is_prod else "lax",
        path=REFRESH_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    user, access_token, raw_refresh = await service.register(
        body.email, body.password, body.display_name
    )
    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    user, access_token, raw_refresh = await service.login(body.email, body.password)
    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    service = AuthService(db)
    access_token = await service.refresh(raw_refresh)
    # rotation produced a new refresh token; set it as the new cookie
    _set_refresh_cookie(response, service._last_refresh)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    await AuthService(db).logout(raw_refresh)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_PATH)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)