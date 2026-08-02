from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_session
from app.core.security import hash_password
from app.models.admin import Admin
from app.schemas.admin import AdminCreate, AdminRead, AdminUpdate

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_admin_or_404(session: AsyncSession, admin_id: UUID) -> Admin:
    admin = await session.get(Admin, admin_id)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="admin nao encontrado"
        )
    return admin


async def _ensure_username_free(
    session: AsyncSession, username: str | None, exclude_id: UUID | None = None
) -> None:
    if username is None:
        return
    stmt = select(Admin).where(Admin.username == username)
    if exclude_id is not None:
        stmt = stmt.where(Admin.id != exclude_id)
    existing = await session.scalar(stmt)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="username ja em uso"
        )


@router.post(
    "/admins", response_model=AdminRead, status_code=status.HTTP_201_CREATED
)
async def create_admin(
    payload: AdminCreate,
    session: AsyncSession = Depends(get_session),
):
    await _ensure_username_free(session, payload.username)
    admin = Admin(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


@router.get("/admins", response_model=list[AdminRead])
async def list_admins(session: AsyncSession = Depends(get_session)):
    result = await session.scalars(
        select(Admin).order_by(Admin.created_at)
    )
    return result.all()


@router.get("/admins/{admin_id}", response_model=AdminRead)
async def get_admin(
    admin_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await _get_admin_or_404(session, admin_id)


@router.patch("/admins/{admin_id}", response_model=AdminRead)
async def update_admin(
    admin_id: UUID,
    payload: AdminUpdate,
    session: AsyncSession = Depends(get_session),
):
    admin = await _get_admin_or_404(session, admin_id)
    await _ensure_username_free(session, payload.username, exclude_id=admin.id)
    if payload.username is not None:
        admin.username = payload.username
    if payload.password is not None:
        admin.password_hash = hash_password(payload.password)
    await session.commit()
    await session.refresh(admin)
    return admin


@router.delete(
    "/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_admin(
    admin_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_admin: Admin = Depends(get_current_admin),
):
    if admin_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="voce nao pode excluir o proprio usuario",
        )
    admin = await _get_admin_or_404(session, admin_id)
    await session.delete(admin)
    await session.commit()
