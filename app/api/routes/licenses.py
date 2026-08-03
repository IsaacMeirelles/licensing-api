from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_session
from app.models.activation import Activation
from app.models.admin import Admin
from app.models.license import License
from app.schemas.activation import ActivationRead
from app.schemas.license import (
    LicenseCreate,
    LicenseRead,
    LicenseReadWithKey,
    LicenseRenew,
    LicenseUpdate,
)
from app.services.license_service import (
    create_license,
    renew_license,
    update_license,
)

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.post("/licenses", response_model=LicenseReadWithKey, status_code=status.HTTP_201_CREATED)
async def create_license_endpoint(
    payload: LicenseCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_license(session, payload)


@router.get("/licenses", response_model=list[LicenseRead])
async def list_licenses(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    result = await session.scalars(
        select(License).order_by(License.created_at.desc()).offset(skip).limit(limit)
    )
    return result.all()


@router.get("/licenses/{license_id}", response_model=LicenseRead)
async def get_license(
    license_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    license = await session.get(License, license_id)
    if license is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada")
    return license


@router.get("/licenses/{license_id}/key")
async def get_license_key(
    license_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    license = await session.get(License, license_id)
    if license is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada")
    return {"key": license.key}


@router.patch("/licenses/{license_id}", response_model=LicenseReadWithKey)
async def update_license_endpoint(
    license_id: UUID,
    payload: LicenseUpdate,
    session: AsyncSession = Depends(get_session),
):
    license = await session.get(License, license_id)
    if license is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada")
    return await update_license(session, license, payload)


@router.post("/licenses/{license_id}/renew", response_model=LicenseReadWithKey)
async def renew_license_endpoint(
    license_id: UUID,
    payload: LicenseRenew,
    session: AsyncSession = Depends(get_session),
):
    license = await session.get(License, license_id)
    if license is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada")
    return await renew_license(session, license, payload.validity_years)


@router.delete("/licenses/{license_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_license(
    license_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    license = await session.get(License, license_id)
    if license is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada")
    await session.delete(license)
    await session.commit()


@router.get("/licenses/{license_id}/activations", response_model=list[ActivationRead])
async def list_activations(
    license_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    license = await session.get(License, license_id)
    if license is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada")
    result = await session.scalars(
        select(Activation)
        .where(Activation.license_id == license_id)
        .order_by(Activation.activated_at)
    )
    return result.all()


@router.delete(
    "/licenses/{license_id}/activations/{activation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_activation(
    license_id: UUID,
    activation_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    activation = await session.scalar(
        select(Activation).where(
            Activation.id == activation_id,
            Activation.license_id == license_id,
        )
    )
    if activation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ativacao nao encontrada")
    activation.revoked = True
    await session.commit()


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    licenses = await session.scalar(select(func.count()).select_from(License))
    activations = await session.scalar(select(func.count()).select_from(Activation))
    return {"licenses": licenses, "activations": activations}
