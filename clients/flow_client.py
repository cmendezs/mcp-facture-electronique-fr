"""
HTTP client for the Flow Service XP Z12-013 (Annex A v1.1.0).

Handles automatic OAuth2 authentication and HTTP error management
in accordance with the return codes defined in the standard.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

import httpx

# Normalised values XP Z12-013 Annex A §FlowInfo.processingRule
ProcessingRule = Literal[
    "B2B",
    "B2BInt",
    "B2C",
    "OutOfScope",
    "ArchiveOnly",
    "NotApplicable",
]

from config import OAuthClient, PAConfig, get_config, get_oauth_client

logger = logging.getLogger(__name__)

# HTTP error codes handled explicitly (XP Z12-013 §5.x)
_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Bad request — check the flow format or parameters",
    401: "Unauthenticated — invalid or expired OAuth2 token",
    403: "Access denied — insufficient rights on this flow or operation",
    404: "Flow not found — the provided identifier does not exist",
    413: "Flow too large — exceeds the maximum size accepted by the AP",
    422: "Unprocessable entity — the flow is syntactically invalid",
    429: "Too many requests — rate limit exceeded, retry later",
    500: "Internal Flow Service error — contact the Approved Platform",
    503: "Flow Service unavailable — the Approved Platform is under maintenance",
}


def _raise_for_status(response: httpx.Response) -> None:
    """
    Raises an exception with a clear business message based on the HTTP code.

    Attempts to include the detail returned by the AP (fields 'errorCode'/'errorMessage'
    defined in the XP Z12-013 Error schema, or falls back to the text body).
    """
    if response.is_success:
        return

    code = response.status_code
    base_msg = _HTTP_ERROR_MESSAGES.get(code, f"HTTP error {code}")

    detail = ""
    try:
        body = response.json()
        # XP Z12-013 Error schema: { errorCode, errorMessage }
        detail = body.get("errorMessage") or body.get("errorCode") or ""
    except Exception:
        detail = response.text[:200] if response.text else ""

    full_msg = f"{base_msg}" + (f" — {detail}" if detail else "")
    logger.error("Flow Service %d: %s", code, full_msg)
    response.raise_for_status()  # preserves standard httpx semantics


class FlowClient:
    """
    Async wrapper for the Flow Service XP Z12-013.

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
        self._base_url = self._config.pa_base_url_flow

    async def _get_headers(self) -> dict[str, str]:
        token = await self._oauth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """
        Executes an HTTP request with automatic retry on 401.

        A 401 invalidates the token and retries the request once
        (the authorisation server may have revoked the token).
        """
        url = f"{self._base_url}{path}"
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=self._config.http_timeout) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                files=files,
            )

        if response.status_code == 401 and retry_on_401:
            logger.info("OAuth2 token rejected (401), renewing and retrying")
            self._oauth.invalidate_token()
            return await self._request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                retry_on_401=False,
            )

        _raise_for_status(response)
        return response

    # ------------------------------------------------------------------
    # Flow Service — endpoints
    # ------------------------------------------------------------------

    async def submit_flow(
        self,
        file_content: bytes,
        file_name: str,
        flow_syntax: str,
        processing_rule: Optional[ProcessingRule] = None,
        flow_type: Optional[str] = None,
        tracking_id: Optional[str] = None,
        sha256: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        POST /v1/flows — Submit a flow (invoice, e-reporting, CDAR status).

        The flow is sent as multipart/form-data with:
        - `file`     : the binary document
        - `flowInfo` : JSON metadata (flowSyntax required, XP Z12-013 Annex A)
        """
        import json as _json

        # flowSyntax is the only required field in FlowInfo (spec Annex A 1.1.0)
        flow_info: dict[str, Any] = {"flowSyntax": flow_syntax}
        if processing_rule:
            flow_info["processingRule"] = processing_rule
        if flow_type:
            flow_info["flowType"] = flow_type
        if tracking_id:
            flow_info["trackingId"] = tracking_id
        if sha256:
            flow_info["sha256"] = sha256
        # 'name' in flowInfo corresponds to the file name (spec §FlowInfo)
        flow_info["name"] = file_name

        files = {
            "file": (file_name, file_content, "application/octet-stream"),
            "flowInfo": (None, _json.dumps(flow_info), "application/json"),
        }

        response = await self._request("POST", "/v1/flows", files=files)
        return response.json()

    async def submit_lifecycle_status(
        self,
        referenced_flow_id: str,
        status_code: str,
        reason: Optional[str] = None,
        payment_date: Optional[str] = None,
        payment_amount: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        POST /v1/flows — Submit a lifecycle status (CDAR).

        Builds a CDAR flow (flowSyntax='CDAR', flowType='CustomerInvoiceLC'
        or 'SupplierInvoiceLC' depending on context) and submits it via POST /v1/flows.
        """
        import json as _json

        status_xml = _build_lifecycle_status_xml(
            referenced_flow_id=referenced_flow_id,
            status_code=status_code,
            reason=reason,
            payment_date=payment_date,
            payment_amount=payment_amount,
        )

        flow_info: dict[str, Any] = {
            "flowSyntax": "CDAR",
            "processingRule": "NotApplicable",
            # SupplierInvoiceLC = status on a received invoice (supplier → customer)
            "flowType": "SupplierInvoiceLC",
            "name": "lifecycle_status.xml",
        }

        files = {
            "file": ("lifecycle_status.xml", status_xml.encode("utf-8"), "application/xml"),
            "flowInfo": (None, _json.dumps(flow_info), "application/json"),
        }

        response = await self._request("POST", "/v1/flows", files=files)
        return response.json()

    async def search_flows(
        self,
        processing_rule: Optional[ProcessingRule | list[ProcessingRule]] = None,
        flow_type: Optional[str | list[str]] = None,
        status: Optional[str | list[str]] = None,
        flow_direction: Optional[str | list[str]] = None,
        ack_status: Optional[str] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        tracking_id: Optional[str] = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        POST /v1/flows/search — Search flows by criteria.

        Body structure: { "limit": N, "where": { <criteria> } }
        (spec SearchFlowParams Annex A 1.1.0 — 'where' wrapper required).

        Pagination is done via `updatedAfter` (ISO 8601).
        processingRule and flowType accept a single value or a list.
        """
        where: dict[str, Any] = {}

        if processing_rule:
            where["processingRule"] = (
                processing_rule if isinstance(processing_rule, list) else [processing_rule]
            )
        if flow_type:
            where["flowType"] = (
                flow_type if isinstance(flow_type, list) else [flow_type]
            )
        if status:
            where["status"] = (
                status if isinstance(status, list) else [status]
            )
        if flow_direction:
            where["flowDirection"] = (
                flow_direction if isinstance(flow_direction, list) else [flow_direction]
            )
        if ack_status:
            where["ackStatus"] = ack_status
        if updated_after:
            where["updatedAfter"] = updated_after
        if updated_before:
            where["updatedBefore"] = updated_before
        if tracking_id:
            where["trackingId"] = tracking_id

        body: dict[str, Any] = {"limit": limit, "where": where}
        response = await self._request("POST", "/v1/flows/search", json=body)
        return response.json()

    async def get_flow(
        self,
        flow_id: str,
        doc_type: str = "Metadata",
    ) -> dict[str, Any] | bytes:
        """
        GET /v1/flows/{flowId} — Retrieve a flow by its identifier.

        - `Metadata` (default): returns the flow's JSON metadata
        - `Original`: returns the original document (binary)
        - `Converted`: returns the converted document (binary)
        - `ReadableView`: returns the human-readable representation (binary PDF)
        """
        params = {"docType": doc_type}
        response = await self._request("GET", f"/v1/flows/{flow_id}", params=params)

        if doc_type == "Metadata":
            return response.json()
        return response.content

    async def healthcheck(self) -> dict[str, Any]:
        """GET /v1/healthcheck — Check the availability of the Flow Service."""
        response = await self._request("GET", "/v1/healthcheck")
        try:
            return response.json()
        except Exception:
            return {"status": "ok", "http_status": response.status_code}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_lifecycle_status_xml(
    referenced_flow_id: str,
    status_code: str,
    reason: Optional[str] = None,
    payment_date: Optional[str] = None,
    payment_amount: Optional[str] = None,
) -> str:
    """
    Builds a CDAR lifecycle status XML document.

    The exact format depends on the AP — this helper produces a generic XML
    conforming to the statuses defined in XP Z12-014 (42 B2B cases).
    """
    reason_el = f"<Reason>{reason}</Reason>" if reason else ""
    payment_el = ""
    if payment_date or payment_amount:
        payment_el = (
            "<Payment>"
            + (f"<Date>{payment_date}</Date>" if payment_date else "")
            + (f"<Amount>{payment_amount}</Amount>" if payment_amount else "")
            + "</Payment>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<LifecycleStatus xmlns="urn:xp-z12-013:lifecycle-status:1.0">'
        f"<ReferencedFlowId>{referenced_flow_id}</ReferencedFlowId>"
        f"<StatusCode>{status_code}</StatusCode>"
        f"{reason_el}"
        f"{payment_el}"
        "</LifecycleStatus>"
    )
