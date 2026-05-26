"""Application settings, loaded once from the environment.

All configuration enters the app here. Domains read settings from this
module rather than touching ``os.environ`` directly, so the full surface
of what the service needs is visible in one place.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for the API service."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # Async SQLAlchemy DSN, e.g. postgresql+asyncpg://user:pass@host/db
    database_url: str = Field(
        default="postgresql+asyncpg://hangpost:hangpost@localhost:5432/hangpost"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Optional integrations — left unset in local dev.
    sentry_dsn: str | None = Field(default=None)
    clerk_jwks_url: str | None = Field(default=None)

    # Browser origins allowed to call the API (CORS). Comma-separated so it
    # can be set from a single env var; the web app on Vercel goes here.
    cors_origins: str = Field(default="http://localhost:3000")

    # Identifies which ranker produced an impression, logged on every row.
    model_version: str = Field(default="rules-v1")

    @property
    def cors_origin_list(self) -> list[str]:
        """Parsed, trimmed list of allowed browser origins."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the parsed settings."""
    return Settings()
