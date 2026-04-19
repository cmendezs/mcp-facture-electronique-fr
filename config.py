"""
Configuration for the Approved Platform (AP) — mcp-facture-electronique-fr.

PAConfig holds the FR-specific environment variables (PA_ prefix).
TokenCache and OAuth mechanics are provided by mcp-einvoicing-core and are
no longer duplicated here.

The two HTTP clients (FlowClient, DirectoryClient) share a single TokenCache
instance so one token fetch serves both services simultaneously.
"""

from __future__ import annotations

import logging
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from mcp_einvoicing_core.http_client import OAuthConfig, TokenCache

load_dotenv()

logger = logging.getLogger(__name__)


class PAConfig(BaseSettings):
    """Approved Platform configuration loaded from environment variables.

    Environment variables (unchanged from v0.1.x):
        PA_BASE_URL_FLOW, PA_BASE_URL_DIRECTORY,
        PA_CLIENT_ID, PA_CLIENT_SECRET, PA_TOKEN_URL,
        PA_OAUTH_SCOPE (optional), HTTP_TIMEOUT, DEBUG
    """

    pa_base_url_flow: str = Field(
        ...,
        description="Base URL of the Flow Service (e.g. https://api.flow.your-ap.com/flow-service)",
    )
    pa_base_url_directory: str = Field(
        ...,
        description="Base URL of the Directory Service",
    )
    pa_client_id: str = Field(..., description="OAuth2 Client ID provided by the AP")
    pa_client_secret: str = Field(..., description="OAuth2 Client Secret provided by the AP")
    pa_token_url: str = Field(..., description="OAuth2 token endpoint URL")
    pa_oauth_scope: Optional[str] = Field(default=None, description="OAuth2 scope (optional)")
    http_timeout: float = Field(default=30.0, description="HTTP timeout in seconds")
    debug: bool = Field(default=False, description="Enable debug logging")

    @field_validator("pa_base_url_flow", "pa_base_url_directory", "pa_token_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def to_oauth_config(self) -> OAuthConfig:
        """Return a base OAuthConfig suitable for BaseEInvoicingClient."""
        return OAuthConfig(
            token_url=self.pa_token_url,
            client_id=self.pa_client_id,
            client_secret=self.pa_client_secret,
            scope=self.pa_oauth_scope,
            http_timeout=self.http_timeout,
        )


# ---------------------------------------------------------------------------
# Application singletons
# ---------------------------------------------------------------------------

_config: Optional[PAConfig] = None
_shared_token_cache: Optional[TokenCache] = None


def get_config() -> PAConfig:
    """Return the singleton PAConfig (loaded from .env)."""
    global _config
    if _config is None:
        _config = PAConfig()  # type: ignore[call-arg]
        if _config.debug:
            logging.getLogger().setLevel(logging.DEBUG)
    return _config


def get_shared_token_cache() -> TokenCache:
    """Return a shared TokenCache used by both FlowClient and DirectoryClient.

    Sharing a single cache means one OAuth2 token fetch serves both services,
    matching the previous behaviour where both clients used the same OAuthClient.
    """
    global _shared_token_cache
    if _shared_token_cache is None:
        _shared_token_cache = TokenCache()
    return _shared_token_cache
