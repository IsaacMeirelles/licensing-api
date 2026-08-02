from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Licensing API"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://licensing:licensing@localhost:5432/licensing"
    )

    jwt_secret: str = "troque-este-segredo-em-producao"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    license_signing_private_key_b64: str = ""
    license_signing_public_key_b64: str = ""
    issuer: str = "licensing-api"

    cors_origins: list[str] = ["*"]

    rate_limit_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
