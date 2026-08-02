import os
import time

import pytest

from app.core.signing import (
    ExpiredLicenseError,
    InvalidLicenseError,
    sign_license,
    verify_license,
)


def test_sign_and_verify_roundtrip():
    payload = {"iss": "licensing-api", "sub": "Cliente A", "lic": "123"}
    key = sign_license(payload)
    assert key.startswith("LIC1.")
    assert verify_license(key) == payload


def test_tampered_key_is_rejected():
    key = sign_license({"sub": "Cliente A"})
    tampered = key[:-2] + ("ab" if key[-2:] != "ab" else "cd")
    with pytest.raises(InvalidLicenseError):
        verify_license(tampered)


def test_wrong_public_key_is_rejected():
    from app.core.config import get_settings

    key = sign_license({"sub": "Cliente A"})
    get_settings.cache_clear()
    os.environ["LICENSE_SIGNING_PUBLIC_KEY_B64"] = (
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    )
    with pytest.raises(InvalidLicenseError):
        verify_license(key)
    get_settings.cache_clear()
    os.environ["LICENSE_SIGNING_PUBLIC_KEY_B64"] = (
        "vONy5XOTy2ABVWyIb5v7kncmKkhnP3HHdbeA6kqRkO0="
    )


def test_expired_key_is_rejected():
    key = sign_license({"sub": "Cliente A", "exp": int(time.time()) - 10})
    with pytest.raises(ExpiredLicenseError):
        verify_license(key)


def test_nonexpired_key_ok():
    key = sign_license({"sub": "Cliente A", "exp": int(time.time()) + 3600})
    assert verify_license(key)["sub"] == "Cliente A"
