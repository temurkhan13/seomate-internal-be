"""API runtime settings, env-driven."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """API-side runtime settings.

    The DB connection is read by the shared ``seomate.storage.db`` module
    via its own DatabaseSettings; we only need API-specific knobs here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # CORS comma-separated list of allowed origins. Local dev default lets the
    # Next.js dev server in. In cloud, this should include the Vercel URL of
    # the `seomate-fe` deploy (e.g. "https://seomate-fe.vercel.app").
    CORS_ORIGINS: str = "http://localhost:3000"

    # Optional HTTP Basic auth gate. Both env vars must be set to enable.
    # Leave both empty (default) for unauthenticated local dev. Set both on
    # any cloud deploy: the audit data we serve includes Pixelette competitive
    # analysis and is not intended to be publicly readable even when the source
    # code is public.
    BASIC_AUTH_USER: str = ""
    BASIC_AUTH_PASSWORD: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def basic_auth_enabled(self) -> bool:
        return bool(self.BASIC_AUTH_USER) and bool(self.BASIC_AUTH_PASSWORD)


def get_api_settings() -> ApiSettings:
    return ApiSettings()
