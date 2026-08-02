"""Cria um usuario administrador.

Uso:
    uv run scripts/create_admin.py --username admin --password 'senha-forte'

Requer o banco rodando (docker compose up -d db) e o .env configurado.
"""
import argparse
import asyncio

from sqlalchemy import select

from app.core.database import async_session
from app.core.security import hash_password
from app.models.admin import Admin


async def create_admin(username: str, password: str) -> None:
    async with async_session() as session:
        existing = await session.scalar(select(Admin).where(Admin.username == username))
        if existing is not None:
            raise SystemExit(f"admin '{username}' ja existe")
        session.add(Admin(username=username, password_hash=hash_password(password)))
        await session.commit()
    print(f"admin '{username}' criado com sucesso")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria um usuario administrador")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(create_admin(args.username, args.password))


if __name__ == "__main__":
    main()
