import base64
import json
import time

import nacl.exceptions
import nacl.signing

from app.core.config import get_settings

KEY_PREFIX = "LIC1."


class LicenseError(Exception):
    """Erro base para problemas com a chave de licença."""


class InvalidLicenseError(LicenseError):
    pass


class ExpiredLicenseError(LicenseError):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def get_signing_key() -> nacl.signing.SigningKey:
    private_b64 = get_settings().license_signing_private_key_b64
    if not private_b64:
        raise LicenseError(
            "LICENSE_SIGNING_PRIVATE_KEY_B64 nao configurada. "
            "Rode: uv run scripts/generate_keys.py"
        )
    return nacl.signing.SigningKey(base64.b64decode(private_b64))


def get_verify_key() -> nacl.signing.VerifyKey:
    public_b64 = get_settings().license_signing_public_key_b64
    if not public_b64:
        raise LicenseError("LICENSE_SIGNING_PUBLIC_KEY_B64 nao configurada.")
    return nacl.signing.VerifyKey(base64.b64decode(public_b64))


def sign_license(payload: dict) -> str:
    """Assina o payload (dict) e devolve uma chave no formato:

    LIC1.<base64url(json)>.<base64url(assinatura_ed25519)>
    """
    body = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = get_signing_key().sign(body.encode("utf-8")).signature
    return f"{KEY_PREFIX}{body}.{_b64url_encode(signature)}"


def verify_license(key: str) -> dict:
    """Valida a assinatura e a expiração. Usado pelo cliente (offline) e
    pelo servidor como primeira checagem."""
    if not key.startswith(KEY_PREFIX):
        raise InvalidLicenseError("formato de chave invalido")

    try:
        _prefix, body, signature_b64 = key.split(".")
        payload = json.loads(_b64url_decode(body))
        get_verify_key().verify(
            body.encode("utf-8"), _b64url_decode(signature_b64)
        )
    except (ValueError, nacl.exceptions.BadSignatureError, json.JSONDecodeError):
        raise InvalidLicenseError("assinatura ou payload invalidos")

    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        raise ExpiredLicenseError("licenca expirada")

    return payload
