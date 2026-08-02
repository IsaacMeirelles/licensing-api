import time
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.signing import LicenseError, sign_license
from app.models.activation import Activation
from app.models.license import License
from app.schemas.license import LicenseCreate, LicenseUpdate

MAX_ACTIVATIONS_OVER_LIMIT = "limite de ativacoes atingido"

# campos que fazem parte do payload assinado; altera-los exige re-assinar
PAYLOAD_FIELDS = {"customer_name", "tier", "max_activations", "expires_at"}


def _build_payload(license: License) -> dict:
    payload = {
        "iss": get_settings().issuer,
        "sub": license.customer_name,
        "lic": str(license.id),
        "iat": int(time.time()),
        "tier": license.tier,
        "max": license.max_activations,
    }
    if license.expires_at is not None:
        payload["exp"] = int(license.expires_at.timestamp())
    return payload


def _assign(license: License, data: dict) -> None:
    for field, value in data.items():
        setattr(license, field, value)


async def create_license(session: AsyncSession, data: LicenseCreate) -> License:
    license = License(
        id=uuid4(),
        customer_name=data.customer_name,
        email=str(data.email) if data.email else None,
        tier=data.tier,
        expires_at=data.expires_at,
        max_activations=data.max_activations,
    )
    license.key = sign_license(_build_payload(license))
    session.add(license)
    await session.commit()
    await session.refresh(license)
    return license


async def update_license(
    session: AsyncSession, license: License, data: LicenseUpdate
) -> License:
    fields = data.model_dump(exclude_unset=True)
    if fields.get("email") is not None:
        fields["email"] = str(fields["email"])
    _assign(license, fields)
    if PAYLOAD_FIELDS & set(fields):
        license.key = sign_license(_build_payload(license))
    await session.commit()
    await session.refresh(license)
    return license


async def count_active_activations(session: AsyncSession, license_id: UUID) -> int:
    result = await session.scalar(
        select(func.count())
        .select_from(Activation)
        .where(
            Activation.license_id == license_id,
            Activation.revoked.is_(False),
        )
    )
    return int(result or 0)


async def activate_machine(
    session: AsyncSession,
    license: License,
    machine_id: str,
    hostname: str | None,
) -> tuple[Activation, int]:
    """Registra/renova a ativação de uma máquina na licença.

    Retorna (ativacao, total_de_ativacoes_ativas)."""
    activation = await session.scalar(
        select(Activation).where(
            Activation.license_id == license.id,
            Activation.machine_id == machine_id,
        )
    )

    if activation is not None:
        activation.revoked = False
        activation.hostname = hostname
        active_count = await count_active_activations(session, license.id)
        await session.commit()
        await session.refresh(activation)
        return activation, active_count

    active_count = await count_active_activations(session, license.id)
    if active_count >= license.max_activations:
        raise LicenseError(MAX_ACTIVATIONS_OVER_LIMIT)

    activation = Activation(
        license_id=license.id, machine_id=machine_id, hostname=hostname
    )
    session.add(activation)
    await session.commit()
    await session.refresh(activation)
    return activation, active_count + 1
