import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
SettingsDependency = Annotated[Settings, Depends(get_settings)]
ApiKeyDependency = Annotated[str | None, Security(api_key_header)]


def require_api_key(
    api_key: ApiKeyDependency,
    settings: SettingsDependency,
) -> None:
    expected_api_key = (settings.dlens_api_key or "").strip()
    if not expected_api_key:
        if settings.env.lower() in {"dev", "test"}:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key authentication is not configured",
        )

    provided_api_key = (api_key or "").strip()
    if not hmac.compare_digest(provided_api_key, expected_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
