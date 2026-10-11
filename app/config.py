"""
Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""


from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Only ever used for local development / tests. Production refuses to start with it.
_DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/gatewayguard"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = _DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # How many reverse proxies sit in front of the app and append to X-Forwarded-For.
    # 0 = trust nobody: the TCP peer address is the client (safe default; X-Forwarded-For
    # is ignored because any client can forge it).
    TRUSTED_PROXY_COUNT: int = 0

    @property
    def ALLOWED_ORIGINS_LIST(self) -> list[str]:
        """Return list of allowed origins."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> "Settings":
        """Fail at startup instead of silently running with a publicly known secret."""
        weak = self.JWT_SECRET == _DEV_JWT_SECRET or len(self.JWT_SECRET) < 32
        if self.is_production and weak:
            raise ValueError(
                "JWT_SECRET must be set to a random value of at least 32 characters "
                "when ENVIRONMENT=production"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
