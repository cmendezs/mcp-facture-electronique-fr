"""
MCP tools for French e-reporting (Flux 10) — DGFiP Dossier Spécifications Externes v3.2.

E-reporting covers:
  - Flux 10.1  IndividualCustomerTransactionReport  — individual B2C or international B2B
  - Flux 10.2  UnitaryCustomerPaymentReport         — individual payment for B2C/intl B2B
  - Flux 10.3  AggregatedCustomerTransactionReport  — aggregated B2C transactions
  - Flux 10.4  AggregatedCustomerPaymentReport      — aggregated B2C payments

E-reporting flows are submitted through the XP Z12-013 Flow Service (POST /v1/flows)
with flowSyntax="FRR" and the appropriate processingRule (B2BInt or B2C).

XML schemas: specs/dgfip/xsd/ (DGFiP Spécifications Externes v3.2, 30/04/2026)
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Annotated, Any, Literal, Optional
from xml.sax.saxutils import escape as _xml_escape

from fastmcp import FastMCP
from pydantic import Field

from clients.flow_client import FlowClient
from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type literals
# ---------------------------------------------------------------------------

EReportingFlowType = Literal[
    "IndividualCustomerTransactionReport",  # Flux 10.1 — unit B2C or intl B2B
    "AggregatedCustomerTransactionReport",  # Flux 10.3 — aggregated B2C
    "UnitaryCustomerPaymentReport",         # Flux 10.2 — unit payment (B2C/intl B2B)
    "AggregatedCustomerPaymentReport",      # Flux 10.4 — aggregated B2C payment
    "UnitarySupplierTransactionReport",     # Flux 10.1 — intl B2B purchases
    "MultiFlowReport",                      # Flux 10  — mixed types
]

EReportingProcessingRule = Literal[
    "B2BInt",  # International B2B e-reporting (outbound sales / inbound purchases)
    "B2C",     # B2C e-reporting (domestic and international)
]

# Sender/Issuer role codes (TT-10, TT-15)
ROLE_CODE_CS = "CS"    # Compatible Solution
ROLE_CODE_MOA = "MOA"  # Assujetti (declarant)
ROLE_CODE_PDP = "PDP"  # Plateforme de Dématérialisation Partenaire
ROLE_CODE_OD = "OD"    # Obligataire Délégant

# Path to the DGFiP XSD files (relative to this file's package root)
_XSD_DIR = pathlib.Path(__file__).parent.parent / "specs" / "dgfip" / "xsd"

# Shared client instance
_flow_client: Optional[FlowClient] = None


def _get_flow_client() -> FlowClient:
    global _flow_client
    if _flow_client is None:
        _flow_client = FlowClient()
    return _flow_client


# ---------------------------------------------------------------------------
# XSD validation helper (optional — requires lxml)
# ---------------------------------------------------------------------------

def _validate_against_xsd(xml_content: str) -> dict[str, Any]:
    """Validate XML against DGFiP ereporting.xsd.

    Falls back to well-formedness check if lxml is not installed.
    """
    xsd_path = _XSD_DIR / "ereporting.xsd"
    if not xsd_path.exists():
        return {
            "valid": None,
            "level": "none",
            "message": (
                f"XSD files not found at {_XSD_DIR}. "
                "Install the package from source to enable XSD validation."
            ),
        }

    # Try well-formedness first (always available)
    import xml.etree.ElementTree as ET  # noqa: PLC0415

    try:
        ET.fromstring(xml_content.encode("utf-8"))
    except ET.ParseError as exc:
        return {"valid": False, "level": "wellformedness", "errors": [str(exc)]}

    # Try lxml XSD validation
    try:
        from lxml import etree  # type: ignore[import-not-found]  # noqa: PLC0415

        xml_doc = etree.fromstring(xml_content.encode("utf-8"))
        xsd_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(xsd_doc)
        is_valid = schema.validate(xml_doc)
        errors = [str(e) for e in schema.error_log]
        return {
            "valid": is_valid,
            "level": "xsd",
            "errors": errors if not is_valid else [],
        }
    except ImportError:
        return {
            "valid": True,
            "level": "wellformedness",
            "message": (
                "Well-formed XML. Full XSD validation requires lxml "
                "(`pip install lxml`). Install it for strict DGFiP schema checks."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "valid": None,
            "level": "error",
            "message": f"Validation error: {exc}",
        }


# ---------------------------------------------------------------------------
# XML builder helpers
# ---------------------------------------------------------------------------

def _e(tag: str, value: str, attrs: Optional[dict[str, str]] = None) -> str:
    """Build a simple XML element with optional attributes."""
    attr_str = ""
    if attrs:
        attr_str = " " + " ".join(f'{k}="{_xml_escape(v)}"' for k, v in attrs.items())
    return f"<{tag}{attr_str}>{_xml_escape(value)}</{tag}>"


def _build_report_document(
    transmission_id: str,
    issue_datetime: str,
    type_code: str,
    sender_id: str,
    sender_id_scheme: str,
    sender_name: str,
    sender_role_code: str,
    issuer_id: str,
    issuer_id_scheme: str,
    issuer_name: str,
    issuer_role_code: str,
    transmission_name: Optional[str] = None,
) -> str:
    name_el = f"<Name>{_xml_escape(transmission_name)}</Name>" if transmission_name else ""
    return (
        "<ReportDocument>"
        f"{_e('Id', transmission_id)}"
        f"{name_el}"
        f"<IssueDateTime>{_e('DateTimeString', issue_datetime)}</IssueDateTime>"
        f"{_e('TypeCode', type_code)}"
        "<Sender>"
        f'<Id schemeId="{_xml_escape(sender_id_scheme)}">{_xml_escape(sender_id)}</Id>'
        f"{_e('Name', sender_name)}"
        f"{_e('RoleCode', sender_role_code)}"
        "</Sender>"
        "<Issuer>"
        f'<Id schemeId="{_xml_escape(issuer_id_scheme)}">{_xml_escape(issuer_id)}</Id>'
        f"{_e('Name', issuer_name)}"
        f"{_e('RoleCode', issuer_role_code)}"
        "</Issuer>"
        "</ReportDocument>"
    )


def _build_transaction_invoice(inv: dict[str, Any]) -> str:
    """Build one <Invoice> element for the TransactionsReport."""
    due_date_el = f"<DueDate>{_xml_escape(inv['due_date'])}</DueDate>" if inv.get("due_date") else ""
    tax_due_el = (
        f"<TaxDueDateTypeCode>{_xml_escape(inv['tax_due_date_type_code'])}</TaxDueDateTypeCode>"
        if inv.get("tax_due_date_type_code")
        else ""
    )

    # Seller block
    seller_tax_id_el = ""
    if inv.get("seller_tax_registration_id"):
        qualifier = _xml_escape(inv.get("seller_tax_registration_id_qualifier", "VA"))
        seller_tax_id_el = (
            f'<TaxRegistrationId qualifyingId="{qualifier}">'
            f'{_xml_escape(inv["seller_tax_registration_id"])}'
            "</TaxRegistrationId>"
        )
    seller_country_el = ""
    if inv.get("seller_country"):
        seller_country_el = (
            f"<PostalAddress><CountryId>{_xml_escape(inv['seller_country'])}</CountryId></PostalAddress>"
        )
    seller_block = (
        "<Seller>"
        f'<CompanyId schemeId="{_xml_escape(inv["seller_company_id_scheme"])}">'
        f'{_xml_escape(inv["seller_company_id"])}</CompanyId>'
        f"{seller_tax_id_el}"
        f"{seller_country_el}"
        "</Seller>"
    )

    # Buyer block (optional)
    buyer_block = ""
    if inv.get("buyer_company_id"):
        buyer_tax_id_el = ""
        if inv.get("buyer_tax_registration_id"):
            qualifier = _xml_escape(inv.get("buyer_tax_registration_id_qualifier", "VA"))
            buyer_tax_id_el = (
                f'<TaxRegistrationId qualifyingId="{qualifier}">'
                f'{_xml_escape(inv["buyer_tax_registration_id"])}'
                "</TaxRegistrationId>"
            )
        buyer_country_el = ""
        if inv.get("buyer_country"):
            buyer_country_el = (
                f"<PostalAddress><CountryId>{_xml_escape(inv['buyer_country'])}</CountryId></PostalAddress>"
            )
        buyer_block = (
            "<Buyer>"
            f'<CompanyId schemeId="{_xml_escape(inv["buyer_company_id_scheme"])}">'
            f'{_xml_escape(inv["buyer_company_id"])}</CompanyId>'
            f"{buyer_tax_id_el}"
            f"{buyer_country_el}"
            "</Buyer>"
        )

    # MonetaryTotal (required — TaxAmount mandatory, TaxExclusiveAmount optional)
    tax_exclusive_el = ""
    if inv.get("tax_exclusive_amount") is not None:
        tax_exclusive_el = f"<TaxExclusiveAmount>{inv['tax_exclusive_amount']}</TaxExclusiveAmount>"
    monetary_block = (
        "<MonetaryTotal>"
        f"{tax_exclusive_el}"
        f'<TaxAmount CurrencyCode="{_xml_escape(inv["monetary_total_currency"])}">'
        f'{inv["monetary_total_tax_amount"]}'
        "</TaxAmount>"
        "</MonetaryTotal>"
    )

    # TaxSubTotal (1..N)
    tax_subtotal_els = ""
    for ts in inv.get("tax_subtotals", []):
        code_el = f"<Code>{_xml_escape(ts['code'])}</Code>" if ts.get("code") else ""
        exemption_el = (
            f"<TaxExemptionReason>{_xml_escape(ts['exemption_reason'])}</TaxExemptionReason>"
            if ts.get("exemption_reason")
            else ""
        )
        exemption_code_el = (
            f"<TaxExemptionReasonCode>{_xml_escape(ts['exemption_reason_code'])}</TaxExemptionReasonCode>"
            if ts.get("exemption_reason_code")
            else ""
        )
        tax_subtotal_els += (
            "<TaxSubTotal>"
            f"<TaxableAmount>{ts['taxable_amount']}</TaxableAmount>"
            f"<TaxAmount>{ts['tax_amount']}</TaxAmount>"
            "<TaxCategory>"
            f"{code_el}"
            f"<Percent>{ts['tax_percent']}</Percent>"
            f"{exemption_el}"
            f"{exemption_code_el}"
            "</TaxCategory>"
            "</TaxSubTotal>"
        )

    return (
        "<Invoice>"
        f"{_e('ID', inv['id'])}"
        f"{_e('IssueDate', inv['issue_date'])}"
        f"{_e('TypeCode', inv['type_code'])}"
        f"{_e('CurrencyCode', inv['currency_code'])}"
        f"{due_date_el}"
        f"{tax_due_el}"
        "<BusinessProcess>"
        f"{_e('ID', inv['business_process_id'])}"
        f"{_e('TypeID', inv['business_process_type_id'])}"
        "</BusinessProcess>"
        f"{seller_block}"
        f"{buyer_block}"
        f"{monetary_block}"
        f"{tax_subtotal_els}"
        "</Invoice>"
    )


def _build_transaction_report_xml(
    transmission_id: str,
    issue_datetime: str,
    type_code: str,
    sender_id: str,
    sender_id_scheme: str,
    sender_name: str,
    sender_role_code: str,
    issuer_id: str,
    issuer_id_scheme: str,
    issuer_name: str,
    issuer_role_code: str,
    period_start: str,
    period_end: str,
    invoices: list[dict[str, Any]],
    transmission_name: Optional[str] = None,
) -> str:
    """Build a DGFiP Flux 10.1/10.3 FRR XML transaction report."""
    report_doc = _build_report_document(
        transmission_id=transmission_id,
        issue_datetime=issue_datetime,
        type_code=type_code,
        sender_id=sender_id,
        sender_id_scheme=sender_id_scheme,
        sender_name=sender_name,
        sender_role_code=sender_role_code,
        issuer_id=issuer_id,
        issuer_id_scheme=issuer_id_scheme,
        issuer_name=issuer_name,
        issuer_role_code=issuer_role_code,
        transmission_name=transmission_name,
    )
    invoice_els = "".join(_build_transaction_invoice(inv) for inv in invoices)
    transactions_report = (
        "<TransactionsReport>"
        "<ReportPeriod>"
        f"{_e('StartDate', period_start)}"
        f"{_e('EndDate', period_end)}"
        "</ReportPeriod>"
        f"{invoice_els}"
        "</TransactionsReport>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Report>"
        f"{report_doc}"
        f"{transactions_report}"
        "</Report>"
    )


def _build_payment_invoice(inv: dict[str, Any]) -> str:
    """Build one <Invoice> element for the PaymentsReport."""
    subtotals_els = ""
    for st in inv.get("subtotals", []):
        currency_el = (
            f"<CurrencyCode>{_xml_escape(st['currency_code'])}</CurrencyCode>"
            if st.get("currency_code")
            else ""
        )
        subtotals_els += (
            "<SubTotals>"
            f"<TaxPercent>{st['tax_percent']}</TaxPercent>"
            f"{currency_el}"
            f"<Amount>{st['amount']}</Amount>"
            "</SubTotals>"
        )
    return (
        "<Invoice>"
        f"{_e('InvoiceID', inv['invoice_id'])}"
        f"{_e('IssueDate', inv['issue_date'])}"
        "<Payment>"
        f"{_e('Date', inv['payment_date'])}"
        f"{subtotals_els}"
        "</Payment>"
        "</Invoice>"
    )


def _build_payment_report_xml(
    transmission_id: str,
    issue_datetime: str,
    type_code: str,
    sender_id: str,
    sender_id_scheme: str,
    sender_name: str,
    sender_role_code: str,
    issuer_id: str,
    issuer_id_scheme: str,
    issuer_name: str,
    issuer_role_code: str,
    period_start: str,
    period_end: str,
    invoices: list[dict[str, Any]],
    transmission_name: Optional[str] = None,
) -> str:
    """Build a DGFiP Flux 10.2/10.4 FRR XML payment report."""
    report_doc = _build_report_document(
        transmission_id=transmission_id,
        issue_datetime=issue_datetime,
        type_code=type_code,
        sender_id=sender_id,
        sender_id_scheme=sender_id_scheme,
        sender_name=sender_name,
        sender_role_code=sender_role_code,
        issuer_id=issuer_id,
        issuer_id_scheme=issuer_id_scheme,
        issuer_name=issuer_name,
        issuer_role_code=issuer_role_code,
        transmission_name=transmission_name,
    )
    invoice_els = "".join(_build_payment_invoice(inv) for inv in invoices)
    payments_report = (
        "<PaymentsReport>"
        "<ReportPeriod>"
        f"{_e('StartDate', period_start)}"
        f"{_e('EndDate', period_end)}"
        "</ReportPeriod>"
        f"{invoice_els}"
        "</PaymentsReport>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Report>"
        f"{report_doc}"
        f"{payments_report}"
        "</Report>"
    )


# ---------------------------------------------------------------------------
# Shared parameter documentation
# ---------------------------------------------------------------------------

_TRANSMISSION_HEADER_DOCS = """
Transmission header fields (DGFiP Spécifications Externes v3.2 — Flux 10 ReportDocument):

- transmission_id       TT-1  Unique ID generated by the sender for this transmission
- issue_datetime        TT-3  Creation timestamp, e.g. "20250115T120000+0100"
- type_code             TT-4  Transmission type code (e.g. "380" invoice, "381" credit note)
- sender_id             TT-8  ID of the sender (CS or PDP platform identifier)
- sender_id_scheme      TT-7  Scheme of sender ID: "SIREN", "SIRET", "TVA", "0088", etc.
- sender_name           TT-9  Legal name of the sender
- sender_role_code      TT-10 Role: "CS" (Compatible Solution), "PDP", "OD", "MOA"
- issuer_id             TT-13 ID of the declarant (the French taxable entity, usually SIREN)
- issuer_id_scheme      TT-12 Scheme of issuer ID: "SIREN", "SIRET", "TVA"
- issuer_name           TT-14 Legal name of the declarant
- issuer_role_code      TT-15 Role of declarant: "MOA" (assujetti), "OD" (obligataire délégant)
"""

_TRANSACTION_INVOICE_SCHEMA = """
Each invoice in the `invoices` JSON list must have:

Required fields:
  id                          TT-19  Invoice number / identifier
  issue_date                  TT-20  Issue date (ISO 8601, e.g. "2025-01-15")
  type_code                   TT-21  Invoice type: "380" (invoice), "381" (credit note), "389" (self-billed)
  currency_code               TT-22  ISO 4217 currency code (e.g. "EUR", "USD")
  business_process_id         TT-28  Business process ID (e.g. "A1", "A2")
  business_process_type_id    TT-29  Process type: "EREP" (e-reporting), "EINV" (e-invoicing)
  seller_company_id           TT-33  Seller identifier (SIREN, SIRET, VAT number, etc.)
  seller_company_id_scheme    TT-33-1 Scheme: "SIREN", "SIRET", "0088" (GLN), "TVA", etc.
  monetary_total_tax_amount   TT-52  Total VAT amount (decimal string, e.g. "200.00")
  monetary_total_currency     TT-202 Currency code for the tax amount (e.g. "EUR")
  tax_subtotals               TT-54..59  List of VAT breakdown objects (see below)

Optional fields:
  due_date                    TT-201 Payment due date (ISO 8601)
  tax_due_date_type_code      TT-24  VAT due date code ("3" cash, "4" invoice date, "5" delivery)
  tax_exclusive_amount        TT-51  Total amount excluding VAT
  seller_tax_registration_id  TT-34  Seller VAT number (e.g. "FR12345678901")
  seller_tax_registration_id_qualifier TT-34-0  Qualifier (default "VA")
  seller_country              TT-35  ISO 3166-1 alpha-2 country code
  buyer_company_id            TT-36  Buyer identifier (for international B2B)
  buyer_company_id_scheme     TT-37  Buyer ID scheme
  buyer_tax_registration_id   TT-38  Buyer VAT number
  buyer_tax_registration_id_qualifier TT-38-0  Qualifier (default "VA")
  buyer_country               TT-39  Buyer country code

tax_subtotals list entries:
  taxable_amount              TT-54  Tax base amount (decimal string)
  tax_amount                  TT-55  VAT amount for this category (decimal string)
  tax_percent                 TT-57  VAT rate (decimal, e.g. "20.0", "5.5", "0.0")
  code                        TT-56  (optional) VAT category code: "S" standard, "Z" zero, "E" exempt
  exemption_reason            TT-58  (optional) Exemption reason text
  exemption_reason_code       TT-59  (optional) Exemption reason code
"""

_PAYMENT_INVOICE_SCHEMA = """
Each invoice in the `invoices` JSON list must have:

Required fields:
  invoice_id    TT-91  Invoice number (reference to the original invoice)
  issue_date    TT-102 Invoice issue date (ISO 8601)
  payment_date  TT-92  Payment date (ISO 8601)
  subtotals     TT-93..95  List of payment breakdown objects

subtotals list entries:
  tax_percent   TT-93  VAT rate (decimal, e.g. "20.0")
  amount        TT-95  Collected amount at this rate (decimal string)
  currency_code TT-94  (optional) Currency code (e.g. "EUR")
"""


# ---------------------------------------------------------------------------
# MCP tool handlers
# ---------------------------------------------------------------------------


def register_ereporting_tools(mcp: FastMCP) -> None:
    """Register all e-reporting tools with the MCP server."""

    @mcp.tool()
    async def validate_ereporting_xml(
        xml_content: Annotated[
            str,
            Field(
                description=(
                    "FRR XML content to validate. Must be a complete Report document "
                    "per DGFiP Spécifications Externes v3.2 ereporting.xsd. "
                    "Full XSD validation requires lxml (`pip install lxml`); "
                    "otherwise well-formedness is checked."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Validate a DGFiP e-reporting (Flux 10) FRR XML payload.

        Checks the XML against the DGFiP Spécifications Externes v3.2 ereporting.xsd.
        Returns validation result with errors if any. Use this before submitting to
        catch structural problems early.

        Validation levels (in order of preference):
          - xsd           — full schema validation (requires lxml)
          - wellformedness — basic XML parsing only (stdlib fallback)
          - none          — XSD files not found on disk
        """
        return _validate_against_xsd(xml_content)

    @mcp.tool()
    async def submit_transaction_report(
        transmission_id: Annotated[
            str,
            Field(description="TT-1: Unique identifier for this transmission (generated by sender)."),
        ],
        issue_datetime: Annotated[
            str,
            Field(description="TT-3: Transmission creation timestamp, e.g. '20250115T120000+0100'."),
        ],
        type_code: Annotated[
            str,
            Field(description="TT-4: Transmission type code, e.g. '380' (invoice report)."),
        ],
        sender_id: Annotated[
            str,
            Field(description="TT-8: Identifier of the CS/PDP platform submitting the report."),
        ],
        sender_id_scheme: Annotated[
            str,
            Field(description="TT-7: ID scheme for sender, e.g. 'SIREN', 'SIRET', 'TVA', '0088'."),
        ],
        sender_name: Annotated[str, Field(description="TT-9: Legal name of the sender platform.")],
        sender_role_code: Annotated[
            str,
            Field(
                description=(
                    "TT-10: Sender role code. Use 'CS' (Compatible Solution), 'PDP', "
                    "'OD' (obligataire délégant), or 'MOA' (assujetti)."
                )
            ),
        ],
        issuer_id: Annotated[
            str,
            Field(description="TT-13: SIREN or SIRET of the French taxable entity (déclarant)."),
        ],
        issuer_id_scheme: Annotated[
            str,
            Field(description="TT-12: ID scheme for issuer, typically 'SIREN' or 'SIRET'."),
        ],
        issuer_name: Annotated[str, Field(description="TT-14: Legal name of the declarant.")],
        issuer_role_code: Annotated[
            str,
            Field(
                description=(
                    "TT-15: Issuer role code. Use 'MOA' (assujetti / declarant) or "
                    "'OD' (obligataire délégant)."
                )
            ),
        ],
        period_start: Annotated[
            str,
            Field(description="TT-17: Report period start date in ISO 8601 format (e.g. '2025-01-01')."),
        ],
        period_end: Annotated[
            str,
            Field(description="TT-18: Report period end date in ISO 8601 format (e.g. '2025-01-31')."),
        ],
        invoices_json: Annotated[
            str,
            Field(
                description=(
                    "JSON array of invoice transaction records. "
                    + _TRANSACTION_INVOICE_SCHEMA
                )
            ),
        ],
        flow_type: Annotated[
            EReportingFlowType,
            Field(
                description=(
                    "XP Z12-013 FlowType for this e-reporting submission:\n"
                    "  IndividualCustomerTransactionReport — Flux 10.1 individual B2C or intl B2B\n"
                    "  AggregatedCustomerTransactionReport — Flux 10.3 aggregated B2C\n"
                    "  UnitarySupplierTransactionReport    — Flux 10.1 intl B2B purchases\n"
                    "  MultiFlowReport                     — mixed flow types"
                )
            ),
        ],
        processing_rule: Annotated[
            EReportingProcessingRule,
            Field(
                description=(
                    "XP Z12-013 ProcessingRule:\n"
                    "  B2BInt — international B2B e-reporting\n"
                    "  B2C    — B2C e-reporting"
                )
            ),
        ],
        transmission_name: Annotated[
            Optional[str],
            Field(description="TT-2: Optional human-readable name for the transmission."),
        ] = None,
        tracking_id: Annotated[
            Optional[str],
            Field(description="Optional external tracking identifier for this flow."),
        ] = None,
        confirmation_token: Annotated[
            Optional[str],
            Field(description="Confirmation token returned by a prior pending response."),
        ] = None,
    ) -> dict[str, Any]:
        """Submit a DGFiP Flux 10.1 / 10.3 transaction e-reporting flow.

        Builds a FRR XML payload conforming to DGFiP Spécifications Externes v3.2
        (transaction.xsd / ereporting.xsd) and submits it to the Approved Platform
        via POST /v1/flows with flowSyntax="FRR".

        Use for:
          - International B2B outbound sales (processing_rule=B2BInt,
            flow_type=IndividualCustomerTransactionReport)
          - International B2B inbound purchases (processing_rule=B2BInt,
            flow_type=UnitarySupplierTransactionReport)
          - B2C individual transactions (processing_rule=B2C,
            flow_type=IndividualCustomerTransactionReport)
          - Aggregated B2C reports (processing_rule=B2C,
            flow_type=AggregatedCustomerTransactionReport)
        """
        assert_not_read_only("FR_READ_ONLY")

        try:
            invoices = json.loads(invoices_json)
        except json.JSONDecodeError as exc:
            return {"error": f"invoices_json is not valid JSON: {exc}"}

        if not isinstance(invoices, list):
            return {"error": "invoices_json must be a JSON array."}

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="submit_transaction_report",
                summary=(
                    f"Submit {flow_type} e-reporting ({len(invoices)} invoice(s), "
                    f"period {period_start} to {period_end}, issuer {issuer_id_scheme}:{issuer_id}). "
                    "This transmits the FRR payload to the Approved Platform via POST /v1/flows."
                ),
                token=confirmation_token,
            )

        try:
            xml_content = _build_transaction_report_xml(
                transmission_id=transmission_id,
                issue_datetime=issue_datetime,
                type_code=type_code,
                sender_id=sender_id,
                sender_id_scheme=sender_id_scheme,
                sender_name=sender_name,
                sender_role_code=sender_role_code,
                issuer_id=issuer_id,
                issuer_id_scheme=issuer_id_scheme,
                issuer_name=issuer_name,
                issuer_role_code=issuer_role_code,
                period_start=period_start,
                period_end=period_end,
                invoices=invoices,
                transmission_name=transmission_name,
            )
        except (KeyError, TypeError) as exc:
            return {"error": f"Invoice data error: {exc}. Check invoices_json structure."}

        client = _get_flow_client()
        file_name = f"ereporting_{transmission_id}.xml"
        result = await client.submit_flow(
            file_content=xml_content.encode("utf-8"),
            file_name=file_name,
            flow_syntax="FRR",
            processing_rule=processing_rule,
            flow_type=flow_type,
            tracking_id=tracking_id,
        )
        gate.consume(confirmation_token)
        return result

    @mcp.tool()
    async def submit_payment_report(
        transmission_id: Annotated[
            str,
            Field(description="TT-1: Unique identifier for this transmission (generated by sender)."),
        ],
        issue_datetime: Annotated[
            str,
            Field(description="TT-3: Transmission creation timestamp, e.g. '20250115T120000+0100'."),
        ],
        type_code: Annotated[
            str,
            Field(description="TT-4: Transmission type code, e.g. '380'."),
        ],
        sender_id: Annotated[
            str,
            Field(description="TT-8: Identifier of the CS/PDP platform submitting the report."),
        ],
        sender_id_scheme: Annotated[
            str,
            Field(description="TT-7: ID scheme for sender, e.g. 'SIREN', 'SIRET'."),
        ],
        sender_name: Annotated[str, Field(description="TT-9: Legal name of the sender platform.")],
        sender_role_code: Annotated[
            str,
            Field(description="TT-10: Sender role code: 'CS', 'PDP', 'OD', or 'MOA'."),
        ],
        issuer_id: Annotated[
            str,
            Field(description="TT-13: SIREN or SIRET of the French declarant."),
        ],
        issuer_id_scheme: Annotated[
            str,
            Field(description="TT-12: ID scheme for issuer: 'SIREN' or 'SIRET'."),
        ],
        issuer_name: Annotated[str, Field(description="TT-14: Legal name of the declarant.")],
        issuer_role_code: Annotated[
            str,
            Field(description="TT-15: Issuer role: 'MOA' or 'OD'."),
        ],
        period_start: Annotated[
            str,
            Field(description="TT-89: Report period start date (ISO 8601, e.g. '2025-01-01')."),
        ],
        period_end: Annotated[
            str,
            Field(description="TT-90: Report period end date (ISO 8601, e.g. '2025-01-31')."),
        ],
        invoices_json: Annotated[
            str,
            Field(
                description=(
                    "JSON array of payment records. "
                    + _PAYMENT_INVOICE_SCHEMA
                )
            ),
        ],
        flow_type: Annotated[
            EReportingFlowType,
            Field(
                description=(
                    "XP Z12-013 FlowType for this payment report:\n"
                    "  UnitaryCustomerPaymentReport    — Flux 10.2 unit payment\n"
                    "  AggregatedCustomerPaymentReport — Flux 10.4 aggregated B2C payment"
                )
            ),
        ],
        processing_rule: Annotated[
            EReportingProcessingRule,
            Field(description="B2BInt for international B2B payments, B2C for B2C payments."),
        ],
        transmission_name: Annotated[
            Optional[str],
            Field(description="TT-2: Optional human-readable name for the transmission."),
        ] = None,
        tracking_id: Annotated[
            Optional[str],
            Field(description="Optional external tracking identifier for this flow."),
        ] = None,
        confirmation_token: Annotated[
            Optional[str],
            Field(description="Confirmation token returned by a prior pending response."),
        ] = None,
    ) -> dict[str, Any]:
        """Submit a DGFiP Flux 10.2 / 10.4 payment e-reporting flow.

        Builds a FRR XML payload conforming to DGFiP Spécifications Externes v3.2
        (payment.xsd / ereporting.xsd) and submits it to the Approved Platform
        via POST /v1/flows with flowSyntax="FRR".

        Use for:
          - International B2B payment reporting (processing_rule=B2BInt,
            flow_type=UnitaryCustomerPaymentReport)
          - B2C individual payment reporting (processing_rule=B2C,
            flow_type=UnitaryCustomerPaymentReport)
          - Aggregated B2C payment reporting (processing_rule=B2C,
            flow_type=AggregatedCustomerPaymentReport)
        """
        assert_not_read_only("FR_READ_ONLY")

        try:
            invoices = json.loads(invoices_json)
        except json.JSONDecodeError as exc:
            return {"error": f"invoices_json is not valid JSON: {exc}"}

        if not isinstance(invoices, list):
            return {"error": "invoices_json must be a JSON array."}

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="submit_payment_report",
                summary=(
                    f"Submit {flow_type} payment e-reporting ({len(invoices)} invoice(s), "
                    f"period {period_start} to {period_end}, issuer {issuer_id_scheme}:{issuer_id}). "
                    "This transmits the FRR payload to the Approved Platform via POST /v1/flows."
                ),
                token=confirmation_token,
            )

        try:
            xml_content = _build_payment_report_xml(
                transmission_id=transmission_id,
                issue_datetime=issue_datetime,
                type_code=type_code,
                sender_id=sender_id,
                sender_id_scheme=sender_id_scheme,
                sender_name=sender_name,
                sender_role_code=sender_role_code,
                issuer_id=issuer_id,
                issuer_id_scheme=issuer_id_scheme,
                issuer_name=issuer_name,
                issuer_role_code=issuer_role_code,
                period_start=period_start,
                period_end=period_end,
                invoices=invoices,
                transmission_name=transmission_name,
            )
        except (KeyError, TypeError) as exc:
            return {"error": f"Payment data error: {exc}. Check invoices_json structure."}

        client = _get_flow_client()
        file_name = f"ereporting_payment_{transmission_id}.xml"
        result = await client.submit_flow(
            file_content=xml_content.encode("utf-8"),
            file_name=file_name,
            flow_syntax="FRR",
            processing_rule=processing_rule,
            flow_type=flow_type,
            tracking_id=tracking_id,
        )
        gate.consume(confirmation_token)
        return result
