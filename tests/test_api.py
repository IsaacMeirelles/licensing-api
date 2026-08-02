import datetime as dt
import time

import pytest


def _parse_dt(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


async def _create_license(client, admin_headers, **overrides):
    data = {
        "customer_name": "Empresa XPTO",
        "email": "contato@xpto.com",
        "tier": "standard",
        "max_activations": 2,
    }
    data.update(overrides)
    resp = await client.post(
        "/api/v1/admin/licenses", json=data, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_login_wrong_password(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "errada"},
    )
    assert resp.status_code == 401


async def test_create_and_list_license(client, admin_headers):
    created = await _create_license(client, admin_headers)
    assert created["key"].startswith("LIC1.")
    assert created["customer_name"] == "Empresa XPTO"
    assert created["revoked"] is False

    resp = await client.get("/api/v1/admin/licenses", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_admin_endpoints_require_token(client):
    resp = await client.post(
        "/api/v1/admin/licenses",
        json={"customer_name": "Sem Token"},
    )
    assert resp.status_code == 401


async def test_full_activation_flow(client, admin_headers):
    lic = await _create_license(client, admin_headers)
    key = lic["key"]

    resp = await client.post(
        "/api/v1/activate",
        json={"license_key": key, "machine_id": "machine-a"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["machine_id"] == "machine-a"

    resp = await client.post(
        "/api/v1/activate",
        json={"license_key": key, "machine_id": "machine-b"},
    )
    assert resp.status_code == 201

    # terceira maquina ultrapassa o limite (max_activations=2)
    resp = await client.post(
        "/api/v1/activate",
        json={"license_key": key, "machine_id": "machine-c"},
    )
    assert resp.status_code == 409

    # mesma maquina reativa sem estourar o limite
    resp = await client.post(
        "/api/v1/activate",
        json={"license_key": key, "machine_id": "machine-a"},
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/validate", json={"license_key": key}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["active_activations"] == 2


async def test_validate_revoked_license(client, admin_headers):
    lic = await _create_license(client, admin_headers)
    key = lic["key"]
    lic_id = lic["id"]

    resp = await client.patch(
        f"/api/v1/admin/licenses/{lic_id}",
        json={"revoked": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == key

    resp = await client.post("/api/v1/validate", json={"license_key": key})
    body = resp.json()
    assert body["valid"] is False
    assert body["reason"] == "licenca revogada"


async def test_validate_forged_key(client):
    resp = await client.post(
        "/api/v1/validate",
        json={"license_key": "LIC1.eyJmYWtlIjoxfQ.xassinatura"},
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


async def test_revoke_activation_frees_slot(client, admin_headers):
    lic = await _create_license(client, admin_headers)
    key = lic["key"]
    lic_id = lic["id"]

    for machine in ("machine-a", "machine-b"):
        resp = await client.post(
            "/api/v1/activate", json={"license_key": key, "machine_id": machine}
        )
        assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/activate", json={"license_key": key, "machine_id": "machine-c"}
    )
    assert resp.status_code == 409

    resp = await client.get(
        f"/api/v1/admin/licenses/{lic_id}/activations", headers=admin_headers
    )
    activations = resp.json()
    assert len(activations) == 2

    resp = await client.delete(
        f"/api/v1/admin/licenses/{lic_id}/activations/{activations[0]['id']}",
        headers=admin_headers,
    )
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/activate", json={"license_key": key, "machine_id": "machine-c"}
    )
    assert resp.status_code == 201


async def test_update_license_regenerates_key(client, admin_headers):
    lic = await _create_license(client, admin_headers)
    resp = await client.patch(
        f"/api/v1/admin/licenses/{lic['id']}",
        json={"max_activations": 5},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["key"] != lic["key"]
    assert body["max_activations"] == 5


async def test_admin_crud_flow(client, admin_headers):
    resp = await client.post(
        "/api/v1/admin/admins",
        json={"username": "gestor", "password": "senha-do-gestor"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    new_admin = resp.json()
    assert new_admin["username"] == "gestor"

    resp = await client.get("/api/v1/admin/admins", headers=admin_headers)
    assert resp.status_code == 200
    assert {a["username"] for a in resp.json()} == {"admin", "gestor"}

    resp = await client.patch(
        f"/api/v1/admin/admins/{new_admin['id']}",
        json={"password": "nova-senha-do-gestor"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "gestor", "password": "nova-senha-do-gestor"},
    )
    assert resp.status_code == 200
    gestor_token = resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "gestor", "password": "senha-do-gestor"},
    )
    assert resp.status_code == 401

    resp = await client.delete(
        f"/api/v1/admin/admins/{new_admin['id']}", headers=admin_headers
    )
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "gestor", "password": "nova-senha-do-gestor"},
    )
    assert resp.status_code == 401


async def test_cannot_delete_self(client, admin_headers):
    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    my_id = resp.json()["id"]
    resp = await client.delete(f"/api/v1/admin/admins/{my_id}", headers=admin_headers)
    assert resp.status_code == 400


async def test_duplicate_username_conflict(client, admin_headers):
    resp = await client.post(
        "/api/v1/admin/admins",
        json={"username": "admin", "password": "outra-senha-123"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


async def test_default_expiry_is_one_year(client, admin_headers):
    before = dt.datetime.now(dt.timezone.utc)
    lic = await _create_license(client, admin_headers)

    expiry = _parse_dt(lic["expires_at"])
    assert before + dt.timedelta(days=364) < expiry < before + dt.timedelta(days=366)

    from app.core.signing import verify_license

    payload = verify_license(lic["key"])
    assert "exp" in payload
    assert abs(payload["exp"] - int(expiry.timestamp())) < 2


async def test_custom_expiry_is_respected(client, admin_headers):
    custom = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
    lic = await _create_license(
        client, admin_headers, expires_at=custom.isoformat()
    )
    expiry = _parse_dt(lic["expires_at"])
    assert abs((expiry - custom).total_seconds()) < 2
