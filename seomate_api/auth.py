"""HTTP Basic auth gate for the API.

The gate is OFF by default. Set both ``BASIC_AUTH_USER`` and
``BASIC_AUTH_PASSWORD`` env vars to turn it ON. The expected pattern:

- Local dev: leave both unset, no auth required (preserves prior workflow).
- Any cloud deploy: set both. The frontend (Server Components) sends the
  ``Authorization: Basic ...`` header from its own env var.

``/api/health`` is intentionally NOT covered by this gate so Render's
healthcheck succeeds without credentials.
"""
from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from seomate_api.settings import get_api_settings

# ``auto_error=False`` so we can return a 401 with a clean ``WWW-Authenticate``
# header ourselves rather than FastAPI's default.
_basic = HTTPBasic(auto_error=False)


def require_basic_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> None:
    settings = get_api_settings()
    if not settings.basic_auth_enabled:
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username, settings.BASIC_AUTH_USER)
    pass_ok = secrets.compare_digest(credentials.password, settings.BASIC_AUTH_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
