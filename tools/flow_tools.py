"""
MCP tools for the Flow Service XP Z12-013 (Annex A v1.1.0).

These tools are exposed via FastMCP and allow Claude to submit,
search, and retrieve flows (invoices, e-reportings, statuses) from
the Approved Platform.
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated, Literal, Optional

# Normalised values XP Z12-013 Annex A §FlowInfo.processingRule
ProcessingRule = Literal[
    "B2B",          # domestic invoice between French taxable entities
    "B2BInt",       # international invoice / e-reporting
    "B2C",          # invoice to non-taxable entity / B2C e-reporting
    "OutOfScope",   # outside reform scope
    "ArchiveOnly",  # archiving without routing
    "NotApplicable",# lifecycle status (CDAR)
]

from fastmcp import FastMCP
from pydantic import Field

from clients.flow_client import FlowClient

logger = logging.getLogger(__name__)

# Client instantiated once and shared across tools
_flow_client: Optional[FlowClient] = None


def get_flow_client() -> FlowClient:
    global _flow_client
    if _flow_client is None:
        _flow_client = FlowClient()
    return _flow_client


def register_flow_tools(mcp: FastMCP) -> None:
    """Registers the 5 Flow Service tools on the FastMCP instance."""

    @mcp.tool()
    async def submit_flow(
        file_base64: Annotated[
            str,
            Field(
                description=(
                    "File content encoded in base64. "
                    "Accepted formats: Factur-X (PDF/A-3 with embedded XML), UBL 2.1 (XML), UN/CEFACT CII D22B (XML). "
                    "Maximum file size is defined by the Approved Platform (typically a few MB)."
                )
            ),
        ],
        file_name: Annotated[
            str,
            Field(
                description=(
                    "File name with extension (e.g. 'invoice_2024_001.xml', 'invoice_2024_001.pdf'). "
                    "The AP uses the extension to detect the format when flow_syntax is ambiguous."
                )
            ),
        ],
        flow_syntax: Annotated[
            str,
            Field(
                description=(
                    "Syntax/format of the submitted file (required). Common values: "
                    "FacturX — PDF/A-3 with embedded Factur-X XML; "
                    "UBL — UBL 2.1 XML invoice or credit note; "
                    "CII — UN/CEFACT CII D22B XML invoice; "
                    "CDAR — XML lifecycle status document; "
                    "EReporting — B2B or B2C e-reporting flow."
                )
            ),
        ],
        processing_rule: Annotated[
            ProcessingRule,
            Field(
                description=(
                    "Processing rule that determines routing and PPF transmission obligations. "
                    "B2B: domestic invoice between French VAT-registered entities (routed + reported to PPF). "
                    "B2BInt: international invoice or cross-border e-reporting. "
                    "B2C: invoice to a non-taxable entity or B2C e-reporting. "
                    "OutOfScope: transaction outside the reform scope (archived only). "
                    "ArchiveOnly: archiving without routing to recipient. "
                    "NotApplicable: used for lifecycle status (CDAR) flows."
                )
            ),
        ],
        flow_type: Annotated[
            str,
            Field(
                description=(
                    "Business type of the submitted flow. Common values: "
                    "Invoice, CreditNote, DebitNote, EReportingB2B, EReportingB2C, LifecycleStatus. "
                    "Refer to your Approved Platform's documentation for the exhaustive list."
                )
            ),
        ],
        tracking_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Sender-assigned tracking identifier (free-form, maxLength 36). "
                    "Recommended: use the invoice number or an internal UUID. "
                    "Allows retrieving this specific flow later via search_flows(tracking_id=...)."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Submit an electronic invoice, e-reporting, or lifecycle status to the Approved Platform.

        This is the primary action for sending B2B invoices (Factur-X, UBL, CII),
        B2BInt/B2C e-reportings, or CDAR lifecycle status messages.

        BEHAVIOR:
        - Submission is asynchronous: the AP returns a flowId and an initial status (typically 'Deposited'),
          not the final delivery status. Poll get_flow(flow_id) or search_flows to track processing.
        - Returns an error dict (with 'error' key) if the base64 encoding is invalid.
        - The AP may reject the flow synchronously (e.g. malformed XML, unknown recipient, quota exceeded);
          in that case the response contains an error code and message.
        - If processing_rule is B2B, the recipient must be registered in the PPF directory with an active
          directory line; verify with get_directory_line before submitting.

        RESPONSE on success: includes flowId (AP-assigned identifier), trackingId (echoed back),
        status (initial processing status), and submittedAt timestamp.

        USAGE GUIDELINES:
        - Always call get_directory_line (or search_directory_line) first to confirm the recipient is
          reachable and to identify their Approved Platform before submitting a B2B invoice.
        - Set a meaningful tracking_id (invoice number or UUID) to simplify later retrieval via search_flows.
        - After submission, use get_flow(flow_id, doc_type='Metadata') to monitor the flow status.
        - For lifecycle statuses on received invoices (Refused, Approved, etc.), prefer submit_lifecycle_status
          which provides structured status fields and handles mandatory PPF transmissions.
        - Call healthcheck_flow before a batch submission to confirm the AP is available.
        """
        try:
            file_content = base64.b64decode(file_base64)
        except Exception as e:
            return {"error": f"base64 decode failed: {e}"}

        client = get_flow_client()
        result = await client.submit_flow(
            file_content=file_content,
            file_name=file_name,
            flow_syntax=flow_syntax,
            processing_rule=processing_rule,
            flow_type=flow_type,
            tracking_id=tracking_id,
        )
        return result

    @mcp.tool()
    async def search_flows(
        processing_rule: Annotated[
            Optional[ProcessingRule],
            Field(
                default=None,
                description=(
                    "Filter by processing rule: B2B, B2BInt, B2C, "
                    "OutOfScope, ArchiveOnly, NotApplicable."
                ),
            ),
        ] = None,
        flow_type: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Filter by flow type: Invoice, CreditNote, "
                    "EReportingB2B, EReportingB2C, LifecycleStatus, etc."
                ),
            ),
        ] = None,
        status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Filter by flow status. Examples: Deposited, Processing, "
                    "Delivered, Rejected, Approved, Refused. "
                    "Refer to the AP documentation for the complete list."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Pagination: only return flows updated after this date/time "
                    "(ISO 8601 format, e.g. 2024-09-01T00:00:00Z). "
                    "Use the 'nextUpdatedAfter' value from the previous response to paginate."
                ),
            ),
        ] = None,
        tracking_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filter by trackingId (sender free-form identifier, maxLength 36).",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                default=50,
                ge=1,
                le=500,
                description="Maximum number of flows to return (1-500, default 50).",
            ),
        ] = 50,
    ) -> dict:
        """
        Search flows (invoices, statuses, e-reportings) in the Approved Platform
        by criteria: flow type, status, processingRule, period, trackingId.
        Pagination via updatedAfter: use the 'nextUpdatedAfter' field from the response
        as the updated_after parameter value to get the next page.
        """
        client = get_flow_client()
        return await client.search_flows(
            processing_rule=processing_rule,
            flow_type=flow_type,
            status=status,
            updated_after=updated_after,
            tracking_id=tracking_id,
            limit=limit,
        )

    @mcp.tool()
    async def get_flow(
        flow_id: Annotated[
            str,
            Field(
                description=(
                    "Flow identifier assigned by the Approved Platform "
                    "(returned by submit_flow or search_flows, maxLength 36)."
                )
            ),
        ],
        doc_type: Annotated[
            str,
            Field(
                default="Metadata",
                description=(
                    "Document type to retrieve: "
                    "Metadata (default, returns the flow's JSON metadata — recommended), "
                    "Original (original submitted document, returned as base64), "
                    "Converted (document converted by the AP, returned as base64), "
                    "ReadableView (human-readable PDF representation, returned as base64)."
                ),
            ),
        ] = "Metadata",
    ) -> dict:
        """
        Retrieve a flow by its identifier. docType allows choosing between
        JSON metadata (Metadata), the original document (Original), the converted
        document (Converted), or the readable representation (ReadableView).
        By default, returns the JSON metadata (status, dates, identifiers).
        """
        client = get_flow_client()
        result = await client.get_flow(flow_id=flow_id, doc_type=doc_type)

        if isinstance(result, bytes):
            # Encode as base64 for JSON serialisation
            return {
                "flowId": flow_id,
                "docType": doc_type,
                "contentBase64": base64.b64encode(result).decode(),
            }
        return result

    @mcp.tool()
    async def submit_lifecycle_status(
        referenced_flow_id: Annotated[
            str,
            Field(
                description=(
                    "Identifier of the invoice flow to which this status applies "
                    "(flowId returned upon receipt, maxLength 36)."
                )
            ),
        ],
        status_code: Annotated[
            str,
            Field(
                description=(
                    "Lifecycle status code to emit. Values defined in XP Z12-014: "
                    "Refused (transmitted to PPF), "
                    "Approved, "
                    "PartiallyApproved, "
                    "Disputed, "
                    "Suspended, "
                    "Cashed (transmitted to PPF), "
                    "PaymentTransmitted, "
                    "Cancelled. "
                    "Refused and Cashed are mandatory transmissions to PPF."
                )
            ),
        ],
        reason: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Status reason, mandatory for Refused and Disputed. "
                    "Free text describing the reason for refusal or dispute."
                ),
            ),
        ] = None,
        payment_date: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Payment date (ISO 8601 format: YYYY-MM-DD). "
                    "Provided for Cashed and PaymentTransmitted statuses."
                ),
            ),
        ] = None,
        payment_amount: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Payment amount (decimal string, e.g. '1250.00'). "
                    "Provided for Cashed and PaymentTransmitted statuses."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Emit a processing status on a received invoice: Refused, Approved,
        PartiallyApproved, Disputed, Suspended, Cashed, PaymentTransmitted,
        Cancelled. Refused and Cashed are mandatory transmissions to PPF.
        Reason is mandatory for Refused and Disputed.
        """
        client = get_flow_client()
        return await client.submit_lifecycle_status(
            referenced_flow_id=referenced_flow_id,
            status_code=status_code,
            reason=reason,
            payment_date=payment_date,
            payment_amount=payment_amount,
        )

    @mcp.tool()
    async def healthcheck_flow() -> dict:
        """
        Check the availability of the Approved Platform's Flow Service.
        Returns the operational status of the service (ok/degraded/unavailable).
        Use before an invoice submission session to ensure the AP is reachable.
        """
        client = get_flow_client()
        return await client.healthcheck()
