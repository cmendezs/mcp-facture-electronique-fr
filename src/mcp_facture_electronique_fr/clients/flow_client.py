"""
HTTP client for the Flow Service XP Z12-013 (Annex A v1.2.0).

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
from datetime import UTC, datetime
from typing import Any, Literal
from xml.sax.saxutils import escape as _xml_escape

import httpx
from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient, TokenCache

from mcp_facture_electronique_fr.config import PAConfig, get_config, get_shared_token_cache

logger = logging.getLogger(__name__)

ProcessingRule = Literal[
    "B2B",
    "B2BInt",
    "B2C",
    "OutOfScope",
    "ArchiveOnly",
    "NotApplicable",
    # Added in XP Z12-013 v1.2.0
    "B2G",
    "B2GInt",
    "B2GOutOfScope",
]

LifecycleStatusCode = Literal[
    "Refused",
    "Approved",
    "PartiallyApproved",
    "Disputed",
    "Suspended",
    "Cashed",
    "PaymentTransmitted",
    "Cancelled",
]


class FlowClient(BaseEInvoicingClient):
    """Async client for the XP Z12-013 Flow Service (Annex A v1.1.0).

    Uses OAuth2 client_credentials with a shared token cache so FlowClient
    and DirectoryClient never fetch redundant tokens.
    """

    def __init__(
        self,
        config: PAConfig | None = None,
        token_cache: TokenCache | None = None,
    ) -> None:
        cfg = config or get_config()
        self._organization_id: str | None = cfg.pa_organization_id
        self._ppf_global_id: str | None = cfg.ppf_global_id
        self._ppf_scheme_id: str = cfg.ppf_scheme_id
        self._ppf_name: str = cfg.ppf_name
        self._ppf_role_code: str = cfg.ppf_role_code
        super().__init__(
            base_url=cfg.pa_base_url_flow,
            auth_mode=AuthMode.OAUTH2_CLIENT_CREDENTIALS,
            oauth_config=cfg.to_oauth_config_flow(),
            token_cache=token_cache if token_cache is not None else get_shared_token_cache(),
            http_timeout=cfg.http_timeout,
        )

    async def _get_headers(self) -> dict[str, str]:
        headers = await super()._get_headers()
        if self._organization_id:
            headers["Organization-Id"] = self._organization_id
        return headers

    def _parse_error_body(self, response: httpx.Response) -> tuple[str, str | None]:
        try:
            body = response.json()
            return body.get("errorMessage") or "", body.get("errorCode")
        except (ValueError, AttributeError):
            return super()._parse_error_body(response)

    # ------------------------------------------------------------------
    # Flow Service — endpoints
    # ------------------------------------------------------------------

    async def submit_flow(
        self,
        file_content: bytes,
        file_name: str,
        flow_syntax: str,
        processing_rule: ProcessingRule | None = None,
        flow_type: str | None = None,
        tracking_id: str | None = None,
        sha256: str | None = None,
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
        status_code: LifecycleStatusCode,
        *,
        invoice_id: str,
        invoice_issue_date: str,
        issuer_party_id: str,
        issuer_party_name: str,
        issuer_role_code: str,
        recipient_party_id: str,
        recipient_party_name: str,
        recipient_role_code: str,
        party_id_scheme: str = "0002",
        recipient_uri: str | None = None,
        invoice_type_code: str = "380",
        receipt_datetime: str | None = None,
        reason: str | None = None,
        reason_code: str | None = None,
        payment_date: str | None = None,
        payment_amount: str | None = None,
        currency: str = "EUR",
        requested_action_code: str | None = None,
        requested_action: str | None = None,
        included_note: str | None = None,
    ) -> dict[str, Any]:
        """POST /v1/flows — Submit a CDAR lifecycle status.

        referenced_flow_id links this submission to the original invoice's
        flow via the platform's own tracking (flowInfo.trackingId) — it is not
        part of the CDAR document content itself. See _build_lifecycle_status_xml
        for the remaining parameters (all correspond to CDAR MDT-* fields).

        The PPF RecipientTradeParty (ppf_global_id and friends) is read from
        this client's PAConfig, not from a call argument — see PAConfig.ppf_global_id.
        """
        status_xml = _build_lifecycle_status_xml(
            invoice_id=invoice_id,
            invoice_issue_date=invoice_issue_date,
            status_code=status_code,
            issuer_party_id=issuer_party_id,
            issuer_party_name=issuer_party_name,
            issuer_role_code=issuer_role_code,
            recipient_party_id=recipient_party_id,
            recipient_party_name=recipient_party_name,
            recipient_role_code=recipient_role_code,
            party_id_scheme=party_id_scheme,
            recipient_uri=recipient_uri,
            invoice_type_code=invoice_type_code,
            receipt_datetime=receipt_datetime,
            reason=reason,
            reason_code=reason_code,
            payment_date=payment_date,
            payment_amount=payment_amount,
            currency=currency,
            ppf_global_id=self._ppf_global_id,
            ppf_scheme_id=self._ppf_scheme_id,
            ppf_name=self._ppf_name,
            ppf_role_code=self._ppf_role_code,
            requested_action_code=requested_action_code,
            requested_action=requested_action,
            included_note=included_note,
        )
        flow_info: dict[str, Any] = {
            "flowSyntax": "CDAR",
            "processingRule": "NotApplicable",
            "flowType": "SupplierInvoiceLC",
            "name": "lifecycle_status.xml",
            "trackingId": referenced_flow_id,
        }
        files = {
            "file": ("lifecycle_status.xml", status_xml.encode("utf-8"), "application/xml"),
            "flowInfo": (None, _json.dumps(flow_info), "application/json"),
        }
        response = await self._request("POST", "/v1/flows", files=files)
        return response.json()

    async def search_flows(
        self,
        processing_rule: ProcessingRule | list[ProcessingRule] | None = None,
        flow_type: str | list[str] | None = None,
        status: str | list[str] | None = None,
        flow_direction: str | list[str] | None = None,
        ack_status: str | None = None,
        updated_after: str | None = None,
        updated_before: str | None = None,
        tracking_id: str | None = None,
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
        except ValueError:
            return {"status": "ok", "http_status": response.status_code}

    # ------------------------------------------------------------------
    # Webhook Service — endpoints (XP Z12-013 v1.2.0)
    # ------------------------------------------------------------------

    async def list_webhooks(self) -> dict[str, Any]:
        """GET /v1/webhooks — List all webhook subscription IDs."""
        response = await self._request("GET", "/v1/webhooks")
        return response.json()

    async def create_webhook(self, params: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/webhooks — Create a webhook subscription."""
        response = await self._request("POST", "/v1/webhooks", json=params)
        return response.json()

    async def get_webhook(self, webhook_uid: str) -> dict[str, Any]:
        """GET /v1/webhooks/{webhookUid} — Get a webhook's full details."""
        response = await self._request("GET", f"/v1/webhooks/{webhook_uid}")
        return response.json()

    async def update_webhook(self, webhook_uid: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH /v1/webhooks/{webhookUid} — Update a webhook's technical parameters."""
        response = await self._request("PATCH", f"/v1/webhooks/{webhook_uid}", json=patch)
        if response.status_code == 204:
            return {"status": "updated", "webhookUid": webhook_uid}
        return response.json()

    async def delete_webhook(self, webhook_uid: str) -> dict[str, Any]:
        """DELETE /v1/webhooks/{webhookUid} — Delete a webhook subscription."""
        response = await self._request("DELETE", f"/v1/webhooks/{webhook_uid}")
        if response.status_code == 204:
            return {"status": "deleted", "webhookUid": webhook_uid}
        return response.json()


# ------------------------------------------------------------------
# CDAR XML builder (FR-specific — XP Z12-014 v1.4 CrossDomainAcknowledgementAndResponse)
#
# FR-CDAR-MISMATCH-1 (resolved): the previous implementation emitted a custom
# <LifecycleStatus> shape that did not match any part of the real AFNOR CDAR
# schema. The real schema is the UN/CEFACT rsm:CrossDomainAcknowledgementAndResponse
# document (~100 MDT-* fields per XP Z12-012 Annex A v1.4, sheet "CDV FE - CDAR"),
# confirmed against 11 official worked examples under specs/examples/cdar/ and
# specs/XP_Z12-014_V1.4_annexes/.../Cycle de Vie - CDAR/. Only the "phase de
# traitement" statuses (business statuses posed by companies, AcknowledgementDocument
# TypeCode=23) are in scope here — "phase de transmission" statuses (Déposée, Reçue,
# Mise à disposition, Rejetée; TypeCode=305) are generated by the Approved Platform
# itself, not emitted by this tool.
# ------------------------------------------------------------------

PartyRoleCode = Literal["SE", "BY"]  # UN/CEFACT: SE=Seller, BY=Buyer


class _StatusMapEntry:
    """One row of the MDT-105/MDT-88/MDT-77 mapping (Annex A v1.4, shared string
    confirming: "Si présent, MDT-88 DOIT ETRE dans la liste UNTDID 1373, avec les
    correspondances suivantes ... Phase Traitement : MDT-77 = 23")."""

    __slots__ = (
        "mandatory_to_ppf",
        "payment_type_code",  # MDT-207 on SpecifiedDocumentCharacteristic: MPA or MEN
        "process_condition_code",  # MDT-105
        "process_condition_label",  # MDT-106
        "reason_mandatory",
        "untdid_status_code",  # MDT-88 (UNTDID 1373); None when the example omits it (Annulée)
    )

    def __init__(
        self,
        process_condition_code: str,
        process_condition_label: str,
        untdid_status_code: str | None,
        *,
        mandatory_to_ppf: bool = False,
        reason_mandatory: bool = False,
        payment_type_code: str | None = None,
    ) -> None:
        self.process_condition_code = process_condition_code
        self.process_condition_label = process_condition_label
        self.untdid_status_code = untdid_status_code
        self.mandatory_to_ppf = mandatory_to_ppf
        self.reason_mandatory = reason_mandatory
        self.payment_type_code = payment_type_code


# Confirmed against specs/examples/cdar/ (all rows below have a matching worked
# example) except PartiallyApproved's process_condition_label, which follows the
# same underscore-joined multi-word convention as the other labels but has no
# worked example in the bundled specs — [Inference].
_STATUS_MAP: dict[str, _StatusMapEntry] = {
    "Refused": _StatusMapEntry("210", "Refusée", "50", mandatory_to_ppf=True, reason_mandatory=True),
    "Approved": _StatusMapEntry("205", "Approuvée", "1"),
    "PartiallyApproved": _StatusMapEntry(
        "206", "Approuvée_Partiellement", "49", reason_mandatory=True
    ),
    "Disputed": _StatusMapEntry("207", "En_litige", "46", reason_mandatory=True),
    "Suspended": _StatusMapEntry("208", "Suspendue", "39", reason_mandatory=True),
    "Cashed": _StatusMapEntry("212", "Encaissée", "47", mandatory_to_ppf=True, payment_type_code="MEN"),
    "PaymentTransmitted": _StatusMapEntry("211", "Paiement_transmis", "47", payment_type_code="MPA"),
    "Cancelled": _StatusMapEntry("220", "Annulée", None),
}


def _utc_timestamp_204() -> str:
    """Current UTC timestamp in CDAR format 204 (CCYYMMDDHHMMSS)."""
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def _build_lifecycle_status_xml(
    *,
    invoice_id: str,
    invoice_issue_date: str,
    status_code: str,
    issuer_party_id: str,
    issuer_party_name: str,
    issuer_role_code: str,
    recipient_party_id: str,
    recipient_party_name: str,
    recipient_role_code: str,
    party_id_scheme: str = "0002",
    recipient_uri: str | None = None,
    invoice_type_code: str = "380",
    receipt_datetime: str | None = None,
    reason: str | None = None,
    reason_code: str | None = None,
    payment_date: str | None = None,
    payment_amount: str | None = None,
    currency: str = "EUR",
    ppf_global_id: str | None = None,
    ppf_scheme_id: str = "0238",
    ppf_name: str = "PPF",
    ppf_role_code: str = "DFH",
    requested_action_code: str | None = None,
    requested_action: str | None = None,
    included_note: str | None = None,
) -> str:
    """Build a CDAR (CrossDomainAcknowledgementAndResponse) lifecycle status
    document (XP Z12-014 v1.4), for one of the "phase de traitement" statuses.

    Args:
        invoice_id: BT-1 invoice number (MDT-87).
        invoice_issue_date: BT-2 invoice date, ISO YYYY-MM-DD (MDT-100).
        status_code: One of LifecycleStatusCode (Refused, Approved, ...).
        issuer_party_id: GlobalID of the party emitting *this* status
            (MDT-38, e.g. SIREN).
        issuer_party_name: Name of the emitting party (MDT-39).
        issuer_role_code: "SE" (seller) or "BY" (buyer) — the emitting party's
            role (MDT-40).
        recipient_party_id: GlobalID of the counterparty receiving the status
            (MDT-57).
        recipient_party_name: Name of the counterparty (MDT-58).
        recipient_role_code: "SE" or "BY" — opposite of issuer_role_code.
        party_id_scheme: schemeID attribute for both party GlobalIDs (default
            "0002" = SIRENE, per every bundled worked example).
        recipient_uri: Optional electronic address for the counterparty
            (MDT-73, CEF network address).
        invoice_type_code: BT-3 invoice type code (MDT-91, default "380").
        receipt_datetime: Original receipt timestamp of the referenced invoice,
            ISO 8601 (MDT-95). Not tracked internally by this server; defaults
            to the current UTC time if omitted (approximation — supply the
            real value when known).
        reason: Free-text reason (MDT-114). Mandatory per Annex A for Refused,
            Disputed, PartiallyApproved, and Suspended — not enforced here,
            consistent with this server's no-payload-semantic-validation design.
        reason_code: Coded reason (MDT-113) from the per-status motif list in
            XP Z12-014 Annex A "Tableau des motifs de STATUTS" (e.g.
            TX_TVA_ERR, DOUBLON). Not validated against that list.
        payment_date: Payment date, ISO YYYY-MM-DD (MDT-219). Cashed/PaymentTransmitted only.
        payment_amount: Payment amount, decimal string (MDT-215).
        currency: ISO 4217 currency code for payment_amount (MDT-216, default EUR).
        ppf_global_id: PPF GlobalID (MDT-57t). When set, a second
            RecipientTradeParty for PPF is emitted alongside the counterparty
            recipient, matching the three-recipient shape seen in the bundled
            UC2_F202500004_02-CDV-213_Rejetee.xml worked example. Unset by
            default — no second recipient is emitted.
        ppf_scheme_id: schemeID for ppf_global_id (MDT-57t attribute, default "0238").
        ppf_name: Name for the PPF RecipientTradeParty (MDT-58t, default "PPF").
        ppf_role_code: RoleCode for the PPF RecipientTradeParty (MDT-59t, default "DFH").
        requested_action_code: Coded requested action (MDT-121), e.g. "CNF"
            ("Créer un Avoir total") per the bundled En_litige worked example.
        requested_action: Free-text requested action (MDT-122).
        included_note: Free-text note (MDT-... IncludedNote/Content) per the
            bundled Rejetee worked example.

    Raises:
        KeyError: status_code is not a recognised LifecycleStatusCode.
    """
    entry = _STATUS_MAP[status_code]
    seller_party_id = issuer_party_id if issuer_role_code == "SE" else recipient_party_id

    now_ts = _utc_timestamp_204()
    invoice_date_compact = invoice_issue_date.replace("-", "")
    doc_id = (
        f"{invoice_id}_{entry.process_condition_code}_{now_ts}"
        f"#{invoice_type_code}_{invoice_date_compact}"
    )
    receipt_ts = (
        receipt_datetime.replace("-", "").replace(":", "").replace("T", "") + "000000"
        if receipt_datetime
        else now_ts
    )[:14]

    recipient_uri_el = (
        "<ram:URIUniversalCommunication>"
        f"<ram:URIID>{_xml_escape(recipient_uri)}</ram:URIID>"
        "</ram:URIUniversalCommunication>"
        if recipient_uri
        else ""
    )

    status_code_el = (
        f"<ram:StatusCode>{_xml_escape(entry.untdid_status_code)}</ram:StatusCode>"
        if entry.untdid_status_code
        else ""
    )

    ppf_recipient_el = (
        "<ram:RecipientTradeParty>"
        f'<ram:GlobalID schemeID="{_xml_escape(ppf_scheme_id)}">{_xml_escape(ppf_global_id)}</ram:GlobalID>'
        f"<ram:Name>{_xml_escape(ppf_name)}</ram:Name>"
        f"<ram:RoleCode>{_xml_escape(ppf_role_code)}</ram:RoleCode>"
        "</ram:RecipientTradeParty>"
        if ppf_global_id
        else ""
    )

    requested_action_code_el = (
        f"<ram:RequestedActionCode>{_xml_escape(requested_action_code)}</ram:RequestedActionCode>"
        if requested_action_code
        else ""
    )
    requested_action_el = (
        f"<ram:RequestedAction>{_xml_escape(requested_action)}</ram:RequestedAction>"
        if requested_action
        else ""
    )
    included_note_el = (
        f"<ram:IncludedNote><ram:Content>{_xml_escape(included_note)}</ram:Content></ram:IncludedNote>"
        if included_note
        else ""
    )

    reason_body_el = ""
    if reason or reason_code or requested_action_code or requested_action or included_note:
        reason_code_el = f"<ram:ReasonCode>{_xml_escape(reason_code)}</ram:ReasonCode>" if reason_code else ""
        reason_el = f"<ram:Reason>{_xml_escape(reason)}</ram:Reason>" if reason else ""
        reason_body_el = (
            f"{reason_code_el}{reason_el}{requested_action_code_el}{requested_action_el}{included_note_el}"
        )

    payment_characteristic_el = ""
    if entry.payment_type_code and (payment_date or payment_amount):
        amount_el = (
            f'<ram:ValueAmount currencyID="{_xml_escape(currency)}">{_xml_escape(payment_amount)}</ram:ValueAmount>'
            if payment_amount
            else ""
        )
        date_el = (
            "<ram:ValueDateTime>"
            f'<udt:DateTimeString format="102">{_xml_escape(payment_date.replace("-", "") if payment_date else "")}</udt:DateTimeString>'
            "</ram:ValueDateTime>"
            if payment_date
            else ""
        )
        payment_characteristic_el = (
            "<ram:SpecifiedDocumentCharacteristic>"
            f"<ram:TypeCode>{entry.payment_type_code}</ram:TypeCode>"
            f"{amount_el}{date_el}"
            "</ram:SpecifiedDocumentCharacteristic>"
        )

    # FR-LC-1: every bundled Annex B / examples/cdar worked example emits at
    # most one <ram:SpecifiedDocumentStatus> per ReferenceReferencedDocument.
    # No CDAR XSD is bundled to confirm the max cardinality directly
    # [Unverified], so reason and payment content are merged into a single
    # status block rather than emitted as two siblings.
    status_block = ""
    if reason_body_el or payment_characteristic_el:
        status_block = (
            "<ram:SpecifiedDocumentStatus>"
            f"{reason_body_el}{payment_characteristic_el}"
            "</ram:SpecifiedDocumentStatus>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rsm:CrossDomainAcknowledgementAndResponse'
        ' xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100"'
        ' xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"'
        ' xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"'
        ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossDomainAcknowledgementAndResponse:100"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<rsm:ExchangedDocumentContext>"
        "<ram:BusinessProcessSpecifiedDocumentContextParameter><ram:ID>REGULATED</ram:ID>"
        "</ram:BusinessProcessSpecifiedDocumentContextParameter>"
        "<ram:GuidelineSpecifiedDocumentContextParameter>"
        "<ram:ID>urn.cpro.gouv.fr:1p0:CDV:invoice</ram:ID>"
        "</ram:GuidelineSpecifiedDocumentContextParameter>"
        "</rsm:ExchangedDocumentContext>"
        "<rsm:ExchangedDocument>"
        f"<ram:ID>{_xml_escape(doc_id)}</ram:ID>"
        f"<ram:Name>{_xml_escape(entry.process_condition_label)}</ram:Name>"
        f'<ram:IssueDateTime><udt:DateTimeString format="204">{now_ts}</udt:DateTimeString></ram:IssueDateTime>'
        "<ram:SenderTradeParty><ram:RoleCode>WK</ram:RoleCode></ram:SenderTradeParty>"
        "<ram:IssuerTradeParty>"
        f'<ram:GlobalID schemeID="{_xml_escape(party_id_scheme)}">{_xml_escape(issuer_party_id)}</ram:GlobalID>'
        f"<ram:Name>{_xml_escape(issuer_party_name)}</ram:Name>"
        f"<ram:RoleCode>{_xml_escape(issuer_role_code)}</ram:RoleCode>"
        "</ram:IssuerTradeParty>"
        "<ram:RecipientTradeParty>"
        f'<ram:GlobalID schemeID="{_xml_escape(party_id_scheme)}">{_xml_escape(recipient_party_id)}</ram:GlobalID>'
        f"<ram:Name>{_xml_escape(recipient_party_name)}</ram:Name>"
        f"<ram:RoleCode>{_xml_escape(recipient_role_code)}</ram:RoleCode>"
        f"{recipient_uri_el}"
        "</ram:RecipientTradeParty>"
        f"{ppf_recipient_el}"
        "</rsm:ExchangedDocument>"
        "<rsm:AcknowledgementDocument>"
        "<ram:MultipleReferencesIndicator><udt:Indicator>false</udt:Indicator></ram:MultipleReferencesIndicator>"
        "<ram:TypeCode>23</ram:TypeCode>"
        f'<ram:IssueDateTime><udt:DateTimeString format="204">{now_ts}</udt:DateTimeString></ram:IssueDateTime>'
        "<ram:ReferenceReferencedDocument>"
        f"<ram:IssuerAssignedID>{_xml_escape(invoice_id)}</ram:IssuerAssignedID>"
        f"{status_code_el}"
        f"<ram:TypeCode>{_xml_escape(invoice_type_code)}</ram:TypeCode>"
        f'<ram:ReceiptDateTime><udt:DateTimeString format="204">{receipt_ts}</udt:DateTimeString></ram:ReceiptDateTime>'
        f'<ram:FormattedIssueDateTime><qdt:DateTimeString format="102">{invoice_date_compact}</qdt:DateTimeString></ram:FormattedIssueDateTime>'
        f"<ram:ProcessConditionCode>{entry.process_condition_code}</ram:ProcessConditionCode>"
        f"<ram:ProcessCondition>{entry.process_condition_label}</ram:ProcessCondition>"
        "<ram:IssuerTradeParty>"
        f'<ram:GlobalID schemeID="{_xml_escape(party_id_scheme)}">{_xml_escape(seller_party_id)}</ram:GlobalID>'
        "</ram:IssuerTradeParty>"
        f"{status_block}"
        "</ram:ReferenceReferencedDocument>"
        "</rsm:AcknowledgementDocument>"
        "</rsm:CrossDomainAcknowledgementAndResponse>"
    )
