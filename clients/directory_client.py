"""
HTTP client for the Directory Service XP Z12-013 (Annex B v1.1.0).

Handles automatic OAuth2 authentication and HTTP error management.
The PPF directory is the source of truth for receiving addresses
of entities subject to electronic invoicing.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from config import OAuthClient, PAConfig, get_config, get_oauth_client

logger = logging.getLogger(__name__)

_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Bad request — check the SIREN/SIRET format or search parameters",
    401: "Unauthenticated — invalid or expired OAuth2 token",
    403: "Access denied — insufficient rights on this directory resource",
    404: "Resource not found — the provided identifier does not exist in the directory",
    413: "Request body too large",
    422: "Unprocessable entity — invalid directory data",
    429: "Too many requests — rate limit exceeded, retry later",
    500: "Internal Directory Service error — contact the Approved Platform",
    503: "Directory Service unavailable — the Approved Platform is under maintenance",
}


def _raise_for_status(response: httpx.Response) -> None:
    """Raises an exception with a business message based on the HTTP code."""
    if response.is_success:
        return

    code = response.status_code
    base_msg = _HTTP_ERROR_MESSAGES.get(code, f"HTTP error {code}")

    detail = ""
    try:
        body = response.json()
        detail = body.get("detail") or body.get("message") or body.get("error_description") or ""
    except Exception:
        detail = response.text[:200] if response.text else ""

    full_msg = f"{base_msg}" + (f" — {detail}" if detail else "")
    logger.error("Directory Service %d: %s", code, full_msg)
    response.raise_for_status()


class DirectoryClient:
    """
    Async wrapper for the Directory Service XP Z12-013.

    All methods automatically renew the OAuth2 token.
    On a 401, the token is invalidated and the request is retried once.
    """

    def __init__(
        self,
        config: Optional[PAConfig] = None,
        oauth: Optional[OAuthClient] = None,
    ) -> None:
        self._config = config or get_config()
        self._oauth = oauth or get_oauth_client()
        self._base_url = self._config.pa_base_url_directory

    async def _get_headers(self) -> dict[str, str]:
        token = await self._oauth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """Executes an HTTP request with automatic retry on 401."""
        url = f"{self._base_url}{path}"
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=self._config.http_timeout) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )

        if response.status_code == 401 and retry_on_401:
            logger.info("OAuth2 token rejected (401), renewing and retrying")
            self._oauth.invalidate_token()
            return await self._request(
                method, path, params=params, json=json, retry_on_401=False
            )

        _raise_for_status(response)
        return response

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
        """POST /v1/siren/search — Search legal units in the directory."""
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
        self,
        siret: str,
        routing_code: str,
        label: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST /v1/routing-code — Create a routing code for a SIRET."""
        body: dict[str, Any] = {
            "siret": siret,
            "routingCode": routing_code,
        }
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
        """
        GET /v1/directory-line/code:{addressing-identifier} — Look up a directory line.

        The addressing-identifier is composed of SIREN, SIREN/SIRET, or SIREN/SIRET/routing-code.
        """
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
        body: dict[str, Any] = {
            "siren": siren,
            "platformId": platform_id,
        }
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
        # DELETE may return 204 No Content
        if response.status_code == 204 or not response.content:
            return {"deleted": True, "instanceId": instance_id}
        return response.json()
