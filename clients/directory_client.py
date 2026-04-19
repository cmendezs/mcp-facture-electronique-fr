"""
HTTP client for the Directory Service XP Z12-013 (Annex B v1.1.0).

Inherits BaseEInvoicingClient from mcp-einvoicing-core, which provides:
  - OAuth2 client_credentials token management (shared TokenCache with FlowClient)
  - Automatic 401 retry
  - Structured PlatformError on HTTP failures

Only FR-specific logic remains here: PPF directory endpoint paths and
SIREN/SIRET/routing-code/directory-line business methods.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient, TokenCache

from config import PAConfig, get_config, get_shared_token_cache

logger = logging.getLogger(__name__)


class DirectoryClient(BaseEInvoicingClient):
    """Async client for the XP Z12-013 Directory Service (Annex B v1.1.0).

    Shares its OAuth2 token cache with FlowClient to avoid redundant fetches.
    """

    def __init__(
        self,
        config: Optional[PAConfig] = None,
        token_cache: Optional[TokenCache] = None,
    ) -> None:
        cfg = config or get_config()
        super().__init__(
            base_url=cfg.pa_base_url_directory,
            auth_mode=AuthMode.OAUTH2_CLIENT_CREDENTIALS,
            oauth_config=cfg.to_oauth_config(),
            token_cache=token_cache if token_cache is not None else get_shared_token_cache(),
            http_timeout=cfg.http_timeout,
        )

    # ------------------------------------------------------------------
    # SIREN — Legal units
    # ------------------------------------------------------------------

    async def search_company(
        self,
        name: Optional[str] = None,
        siren: Optional[str] = None,
        status: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/siren/search — Search legal units in the PPF directory."""
        body: dict[str, Any] = {"limit": limit}
        if name:
            body["name"] = name
        if siren:
            body["siren"] = siren
        if status:
            body["status"] = status
        if updated_after:
            body["updatedAfter"] = updated_after
        response = await self._request("POST", "/v1/siren/search", json=body)
        return response.json()

    async def get_company_by_siren(self, siren: str) -> dict[str, Any]:
        """GET /v1/siren/code-insee:{siren} — Look up a legal unit by SIREN."""
        response = await self._request("GET", f"/v1/siren/code-insee:{siren}")
        return response.json()

    # ------------------------------------------------------------------
    # SIRET — Establishments
    # ------------------------------------------------------------------

    async def search_establishment(
        self,
        siret: Optional[str] = None,
        siren: Optional[str] = None,
        administrative_status: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/siret/search — Search establishments in the directory."""
        body: dict[str, Any] = {"limit": limit}
        if siret:
            body["siret"] = siret
        if siren:
            body["siren"] = siren
        if administrative_status:
            body["administrativeStatus"] = administrative_status
        if updated_after:
            body["updatedAfter"] = updated_after
        response = await self._request("POST", "/v1/siret/search", json=body)
        return response.json()

    async def get_establishment_by_siret(self, siret: str) -> dict[str, Any]:
        """GET /v1/siret/code-insee:{siret} — Look up an establishment by SIRET."""
        response = await self._request("GET", f"/v1/siret/code-insee:{siret}")
        return response.json()

    # ------------------------------------------------------------------
    # Routing Code
    # ------------------------------------------------------------------

    async def search_routing_code(
        self,
        siret: Optional[str] = None,
        siren: Optional[str] = None,
        routing_code: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/routing-code/search — Search routing codes."""
        body: dict[str, Any] = {"limit": limit}
        if siret:
            body["siret"] = siret
        if siren:
            body["siren"] = siren
        if routing_code:
            body["routingCode"] = routing_code
        response = await self._request("POST", "/v1/routing-code/search", json=body)
        return response.json()

    async def create_routing_code(
        self, siret: str, routing_code: str, label: Optional[str] = None
    ) -> dict[str, Any]:
        """POST /v1/routing-code — Create a routing code for a SIRET."""
        body: dict[str, Any] = {"siret": siret, "routingCode": routing_code}
        if label:
            body["label"] = label
        response = await self._request("POST", "/v1/routing-code", json=body)
        return response.json()

    async def update_routing_code(
        self,
        instance_id: str,
        routing_code: Optional[str] = None,
        label: Optional[str] = None,
    ) -> dict[str, Any]:
        """PATCH /v1/routing-code/id-instance:{id} — Update a routing code."""
        body: dict[str, Any] = {}
        if routing_code:
            body["routingCode"] = routing_code
        if label:
            body["label"] = label
        response = await self._request(
            "PATCH", f"/v1/routing-code/id-instance:{instance_id}", json=body
        )
        return response.json()

    # ------------------------------------------------------------------
    # Directory Line
    # ------------------------------------------------------------------

    async def search_directory_line(
        self,
        siren: Optional[str] = None,
        siret: Optional[str] = None,
        routing_code: Optional[str] = None,
        platform_id: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/directory-line/search — Search directory lines."""
        body: dict[str, Any] = {"limit": limit}
        if siren:
            body["siren"] = siren
        if siret:
            body["siret"] = siret
        if routing_code:
            body["routingCode"] = routing_code
        if platform_id:
            body["platformId"] = platform_id
        if updated_after:
            body["updatedAfter"] = updated_after
        response = await self._request("POST", "/v1/directory-line/search", json=body)
        return response.json()

    async def get_directory_line(self, addressing_identifier: str) -> dict[str, Any]:
        """GET /v1/directory-line/code:{identifier} — Look up a directory line."""
        response = await self._request(
            "GET", f"/v1/directory-line/code:{addressing_identifier}"
        )
        return response.json()

    async def create_directory_line(
        self,
        siren: str,
        platform_id: str,
        siret: Optional[str] = None,
        routing_code: Optional[str] = None,
        technical_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST /v1/directory-line — Create a directory line."""
        body: dict[str, Any] = {"siren": siren, "platformId": platform_id}
        if siret:
            body["siret"] = siret
        if routing_code:
            body["routingCode"] = routing_code
        if technical_address:
            body["technicalAddress"] = technical_address
        response = await self._request("POST", "/v1/directory-line", json=body)
        return response.json()

    async def update_directory_line(
        self,
        instance_id: str,
        platform_id: Optional[str] = None,
        technical_address: Optional[str] = None,
        routing_code: Optional[str] = None,
    ) -> dict[str, Any]:
        """PATCH /v1/directory-line/id-instance:{id} — Update a directory line."""
        body: dict[str, Any] = {}
        if platform_id:
            body["platformId"] = platform_id
        if technical_address:
            body["technicalAddress"] = technical_address
        if routing_code:
            body["routingCode"] = routing_code
        response = await self._request(
            "PATCH", f"/v1/directory-line/id-instance:{instance_id}", json=body
        )
        return response.json()

    async def delete_directory_line(self, instance_id: str) -> dict[str, Any]:
        """DELETE /v1/directory-line/id-instance:{id} — Delete a directory line."""
        response = await self._request(
            "DELETE", f"/v1/directory-line/id-instance:{instance_id}"
        )
        if response.status_code == 204 or not response.content:
            return {"deleted": True, "instanceId": instance_id}
        return response.json()
