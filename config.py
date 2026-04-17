"""
Configuration and OAuth2 management for the Approved Platform (AP).

Handles obtaining and automatically renewing the Bearer JWT token
used by the Flow Service and Directory Service (XP Z12-013).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

load_dotenv()

logger = logging.getLogger(__name__)


class PAConfig(BaseSettings):
    """Approved Platform configuration loaded from environment variables."""

    pa_base_url_flow: str = Field(
        ...,
        description="Base URL of the Flow Service (e.g. https://api.flow.your-ap.com/flow-service)",
    )
    pa_base_url_directory: str = Field(
        ...,
        description="Base URL of the Directory Service (e.g. https://api.directory.your-ap.com/directory-service)",
    )
    pa_client_id: str = Field(..., description="OAuth2 Client ID provided by the AP")
    pa_client_secret: str = Field(..., description="OAuth2 Client Secret provided by the AP")
    pa_token_url: str = Field(
        ..., description="OAuth2 token endpoint URL (e.g. https://auth.your-ap.com/oauth/token)"
    )
    pa_oauth_scope: Optional[str] = Field(
        default=None, description="OAuth2 scope (optional, depends on the AP)"
    )
    http_timeout: float = Field(default=30.0, description="HTTP timeout in seconds")
    debug: bool = Field(default=False, description="Enable debug logging")

    @field_validator("pa_base_url_flow", "pa_base_url_directory", "pa_token_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class TokenCache:
    """
    OAuth2 token cache with expiry management.

    The token is automatically renewed 30 seconds before expiry
    to avoid 401 rejections during in-flight requests.
    """

    EXPIRY_MARGIN_SECONDS = 30

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def is_valid(self) -> bool:
        """Returns True if the cached token is still valid."""
        return (
            self._access_token is not None
            and time.monotonic() < self._expires_at - self.EXPIRY_MARGIN_SECONDS
        )

    def set(self, access_token: str, expires_in: int) -> None:
        """Stores a new token with its validity duration."""
        self._access_token = access_token
        self._expires_at = time.monotonic() + expires_in
        logger.debug("OAuth2 token renewed, expires in %ds", expires_in)

    def get(self) -> Optional[str]:
        """Returns the current token or None if expired."""
        if self.is_valid():
            return self._access_token
        return None

    def invalidate(self) -> None:
        """Forces renewal on the next call."""
        self._access_token = None
        self._expires_at = 0.0


class OAuthClient:
    """
    OAuth2 client shared between Flow Service and Directory Service.

    Uses the client_credentials flow (machine-to-machine) as required
    by Annex A/B XP Z12-013.
    """

    def __init__(self, config: PAConfig) -> None:
        self._config = config
        self._cache = TokenCache()

    async def get_token(self) -> str:
        """
        Returns a valid Bearer token.

        If the cached token is still valid, returns it directly.
        Otherwise, obtains a new one from the AP's authorisation server.

        Raises:
            httpx.HTTPStatusError: On HTTP error during token retrieval.
            ValueError: If the response does not contain an access_token.
        """
        cached = self._cache.get()
        if cached:
            return cached

        return await self._fetch_token()

    async def _fetch_token(self) -> str:
        """Calls the OAuth2 token endpoint with client_credentials."""
        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": self._config.pa_client_id,
            "client_secret": self._config.pa_client_secret,
        }
        if self._config.pa_oauth_scope:
            data["scope"] = self._config.pa_oauth_scope

        async with httpx.AsyncClient(timeout=self._config.http_timeout) as client:
            response = await client.post(self._config.pa_token_url, data=data)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OAuth2 token retrieval failed: %s %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError(
                f"Invalid OAuth2 token response — access_token missing: {payload}"
            )

        expires_in = int(payload.get("expires_in", 3600))
        self._cache.set(access_token, expires_in)
        return access_token

    def invalidate_token(self) -> None:
        """Invalidates the cached token (call after a 401)."""
        self._cache.invalidate()


# ---------------------------------------------------------------------------
# Application singletons — instantiated once at server startup
# ---------------------------------------------------------------------------

_config: Optional[PAConfig] = None
_oauth_client: Optional[OAuthClient] = None


def get_config() -> PAConfig:
    """Returns the singleton configuration (loaded from .env)."""
    global _config
    if _config is None:
        _config = PAConfig()  # type: ignore[call-arg]
        if _config.debug:
            logging.basicConfig(level=logging.DEBUG)
    return _config


def get_oauth_client() -> OAuthClient:
    """Returns the singleton OAuth2 client."""
    global _oauth_client
    if _oauth_client is None:
        _oauth_client = OAuthClient(get_config())
    return _oauth_client
