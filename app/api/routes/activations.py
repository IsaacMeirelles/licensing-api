from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.ratelimit import rate_limited
from app.core.signing import (
    ExpiredLicenseError,
    InvalidLicenseError,
    LicenseError,
    verify_license,
)
from app.models.license import License
from app.schemas.activation import (
    ActivateRequest,
    ActivationRead,
    ValidateRequest,
    ValidateResponse,
)
from app.services.license_service import (
    MAX_ACTIVATIONS_OVER_LIMIT,
    activate_machine,
    count_active_activations,
)

router = APIRouter()


async def _load_license(session: AsyncSession, license_key: str) -> tuple[dict, License]:
    try:
        payload = verify_license(license_key)
    except ExpiredLicenseError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="licenca expirada"
        )
    except InvalidLicenseError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="chave invalida"
        )
    except LicenseError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )

    license_id = payload.get("lic")
    license = None
    if license_id:
        license = await session.get(License, UUID(license_id))
    if license is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="licenca nao encontrada"
        )
    if license.key != license_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="chave nao corresponde"
        )
    if license.revoked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="licenca revogada"
        )
    return payload, license


@router.post(
    "/activate",
    response_model=ActivationRead,
    status_code=status.HTTP_201_CREATED,
)
@rate_limited("10/minute")
async def activate(
    request: Request,
    payload: ActivateRequest,
    session: AsyncSession = Depends(get_session),
):
    _payload, license = await _load_license(session, payload.license_key)
    try:
        activation, _ = await activate_machine(
            session, license, payload.machine_id, payload.hostname
        )
    except LicenseError as exc:
        if str(exc) == MAX_ACTIVATIONS_OVER_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    return activation


@router.post("/validate", response_model=ValidateResponse)
@rate_limited("30/minute")
async def validate(
    request: Request,
    payload: ValidateRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        _key_payload, license = await _load_license(session, payload.license_key)
    except HTTPException as exc:
        if exc.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND):
            return ValidateResponse(valid=False, reason=exc.detail)
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            return ValidateResponse(valid=False, reason=exc.detail)
        raise

    active = await count_active_activations(session, license.id)
    expires_at = license.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        return ValidateResponse(valid=False, reason="licenca expirada")

    return ValidateResponse(
        valid=True,
        customer_name=license.customer_name,
        tier=license.tier,
        expires_at=license.expires_at,
        max_activations=license.max_activations,
        active_activations=active,
    )
