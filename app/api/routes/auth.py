from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_session
from app.core.ratelimit import rate_limited
from app.core.security import create_access_token, verify_password
from app.models.admin import Admin
from app.schemas.auth import LoginRequest, Token

router = APIRouter()


@router.post("/auth/login", response_model=Token)
@rate_limited("5/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    admin = await session.scalar(
        select(Admin).where(Admin.username == payload.username)
    )
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="usuario ou senha invalidos",
        )
    return Token(access_token=create_access_token(str(admin.id)))


@router.get("/auth/me")
async def me(admin: Admin = Depends(get_current_admin)):
    return {"id": str(admin.id), "username": admin.username}
