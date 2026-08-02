import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_licensing.db"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "segredo-de-teste-com-pelo-menos-32-caracteres"
os.environ["LICENSE_SIGNING_PRIVATE_KEY_B64"] = (
    "s4XavcQDAr9ba0MCDDPD8ArA5A+wyaNRoX+lhYxdT9A="
)
os.environ["LICENSE_SIGNING_PUBLIC_KEY_B64"] = (
    "vONy5XOTy2ABVWyIb5v7kncmKkhnP3HHdbeA6kqRkO0="
)

import httpx
import pytest
from httpx import ASGITransport

from app.core.database import engine
from app.core.security import hash_password
from app.main import app
from app.models import Base, Admin
from app.core.database import async_session
from sqlalchemy import select

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "senha-forte"


@pytest.fixture(autouse=True)
async def _db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        session.add(
            Admin(
                username=TEST_ADMIN_USERNAME,
                password_hash=hash_password(TEST_ADMIN_PASSWORD),
            )
        )
        await session.commit()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c


async def get_admin_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
async def admin_headers(client: httpx.AsyncClient) -> dict[str, str]:
    token = await get_admin_token(client)
    return {"Authorization": f"Bearer {token}"}
