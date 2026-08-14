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

from dotenv import load_dotenv
from mcp_einvoicing_core.http_client import OAuthConfig, TokenCache
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

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
    pa_base_url_directory: str | None = Field(
        default=None,
        description=(
            "Deprecated, no longer read by DirectoryClient. Kept only so existing "
            "PA_BASE_URL_DIRECTORY values do not break config loading. DirectoryClient "
            "is now wired directly against the PPF Annuaire swagger; see "
            "ppf_annuaire_base_url."
        ),
    )
    ppf_annuaire_base_url: str = Field(
        default="https://aife.economie.gouv.fr/ppf/annuaire-public/v1",
        description=(
            "Base URL of the PPF Annuaire (directory) service, per the bundled "
            "ppf-openapi-annuaire-api-public-1.11.0-openapi.json swagger 'servers' "
            "block. Override for sandbox testing."
        ),
    )
    pa_client_id: str = Field(..., description="OAuth2 Client ID provided by the AP")
    pa_client_secret: str = Field(..., description="OAuth2 Client Secret provided by the AP")
    pa_token_url: str = Field(..., description="OAuth2 token endpoint URL")
    pa_oauth_scope: str | None = Field(
        default=None,
        description="OAuth2 scope shared by both services (backward-compatible alias)",
    )
    pa_oauth_scope_flow: str | None = Field(
        default=None,
        description="OAuth2 scope for the Flow Service (overrides pa_oauth_scope if set)",
    )
    pa_oauth_scope_directory: str | None = Field(
        default=None,
        description="OAuth2 scope for the Directory Service (overrides pa_oauth_scope if set)",
    )
    pa_organization_id: str | None = Field(
        default=None,
        description="Organization identifier for multi-tenant AP contexts (Organization-Id header)",
    )
    ppf_global_id: str | None = Field(
        default=None,
        description=(
            "PPF party GlobalID (CDAR MDT-57t) to add as a second RecipientTradeParty "
            "on CDAR lifecycle status documents, per the XP Z12-014 v1.4 worked examples "
            "(e.g. UC2_F202500004_02-CDV-213_Rejetee.xml). Unset by default: no bundled "
            "worked example value (9998, 0000) is a stable production identifier, so "
            "callers must supply their own real PPF GlobalID to enable this block."
        ),
    )
    ppf_scheme_id: str = Field(
        default="0238",
        description="schemeID attribute for ppf_global_id (0238 in every bundled worked example).",
    )
    ppf_name: str = Field(
        default="PPF",
        description="Name for the PPF RecipientTradeParty (CDAR MDT-58t).",
    )
    ppf_role_code: str = Field(
        default="DFH",
        description="RoleCode for the PPF RecipientTradeParty (CDAR MDT-59t).",
    )
    http_timeout: float = Field(default=30.0, description="HTTP timeout in seconds")
    debug: bool = Field(default=False, description="Enable debug logging")

    @field_validator("pa_base_url_flow", "pa_token_url", "ppf_annuaire_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("pa_base_url_directory")
    @classmethod
    def strip_trailing_slash_optional(cls, v: str | None) -> str | None:
        return v.rstrip("/") if v else v

    @model_validator(mode="after")
    def _sync_scope_aliases(self) -> PAConfig:
        if self.pa_oauth_scope_flow is None:
            self.pa_oauth_scope_flow = self.pa_oauth_scope
        if self.pa_oauth_scope_directory is None:
            self.pa_oauth_scope_directory = self.pa_oauth_scope
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def to_oauth_config_flow(self) -> OAuthConfig:
        """Return OAuthConfig for the Flow Service."""
        return OAuthConfig(
            token_url=self.pa_token_url,
            client_id=self.pa_client_id,
            client_secret=self.pa_client_secret,
            scope=self.pa_oauth_scope_flow,
            http_timeout=self.http_timeout,
        )

    def to_oauth_config_directory(self) -> OAuthConfig:
        """Return OAuthConfig for the Directory Service."""
        return OAuthConfig(
            token_url=self.pa_token_url,
            client_id=self.pa_client_id,
            client_secret=self.pa_client_secret,
            scope=self.pa_oauth_scope_directory,
            http_timeout=self.http_timeout,
        )

    def to_oauth_config(self) -> OAuthConfig:
        """Backward-compatible alias for to_oauth_config_flow()."""
        return self.to_oauth_config_flow()


# ---------------------------------------------------------------------------
# Application singletons
# ---------------------------------------------------------------------------

_config: PAConfig | None = None
_shared_token_cache: TokenCache | None = None


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
