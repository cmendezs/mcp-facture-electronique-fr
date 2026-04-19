"""
HTTP client for the Flow Service XP Z12-013 (Annex A v1.1.0).

Inherits BaseEInvoicingClient from mcp-einvoicing-core, which provides:
  - OAuth2 client_credentials token management (shared TokenCache)
  - Automatic 401 retry
  - Structured PlatformError on HTTP failures

Only FR-specific logic remains here: multipart flow submission, CDAR XML
building, and the XP Z12-013 endpoint paths.
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any, Literal, Optional

from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient, TokenCache

from config import PAConfig, get_config, get_shared_token_cache

logger = logging.getLogger(__name__)

ProcessingRule = Literal[
    "B2B",
    "B2BInt",
    "B2C",
    "OutOfScope",
    "ArchiveOnly",
    "NotApplicable",
]


class FlowClient(BaseEInvoicingClient):
    """Async client for the XP Z12-013 Flow Service (Annex A v1.1.0).

    Uses OAuth2 client_credentials with a shared token cache so FlowClient
    and DirectoryClient never fetch redundant tokens.
    """

    def __init__(
        self,
        config: Optional[PAConfig] = None,
        token_cache: Optional[TokenCache] = None,
    ) -> None:
        cfg = config or get_config()
        super().__init__(
            base_url=cfg.pa_base_url_flow,
            auth_mode=AuthMode.OAUTH2_CLIENT_CREDENTIALS,
            oauth_config=cfg.to_oauth_config(),
            token_cache=token_cache if token_cache is not None else get_shared_token_cache(),
            http_timeout=cfg.http_timeout,
        )

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
        """POST /v1/flows — Submit a flow (invoice, e-reporting, CDAR status)."""
        flow_info: dict[str, Any] = {"flowSyntax": flow_syntax, "name": file_name}
        if processing_rule:
            flow_info["processingRule"] = processing_rule
        if flow_type:
            flow_info["flowType"] = flow_type
        if tracking_id:
            flow_info["trackingId"] = tracking_id
        if sha256:
            flow_info["sha256"] = sha256

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
        """POST /v1/flows — Submit a CDAR lifecycle status."""
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
        """POST /v1/flows/search — Search flows by criteria."""
        where: dict[str, Any] = {}
        if processing_rule:
            where["processingRule"] = (
                processing_rule if isinstance(processing_rule, list) else [processing_rule]
            )
        if flow_type:
            where["flowType"] = flow_type if isinstance(flow_type, list) else [flow_type]
        if status:
            where["status"] = status if isinstance(status, list) else [status]
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
        self, flow_id: str, doc_type: str = "Metadata"
    ) -> dict[str, Any] | bytes:
        """GET /v1/flows/{flowId} — Retrieve a flow by identifier."""
        response = await self._request(
            "GET", f"/v1/flows/{flow_id}", params={"docType": doc_type}
        )
        if doc_type == "Metadata":
            return response.json()
        return response.content

    async def healthcheck(self) -> dict[str, Any]:
        """GET /v1/healthcheck — Check Flow Service availability."""
        response = await self._request("GET", "/v1/healthcheck")
        try:
            return response.json()
        except Exception:
            return {"status": "ok", "http_status": response.status_code}


# ------------------------------------------------------------------
# CDAR XML helper (FR-specific — XP Z12-014 lifecycle statuses)
# ------------------------------------------------------------------

def _build_lifecycle_status_xml(
    referenced_flow_id: str,
    status_code: str,
    reason: Optional[str] = None,
    payment_date: Optional[str] = None,
    payment_amount: Optional[str] = None,
) -> str:
    """Build a CDAR lifecycle status XML document (XP Z12-014)."""
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
