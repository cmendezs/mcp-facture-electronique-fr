"""
Entry point for the MCP server mcp-facture-electronique-fr.

Exposes the standardised AFNOR XP Z12-013 APIs (Flow Service + Directory Service)
via the MCP (Model Context Protocol) in Compatible Solution (CS) mode.

Usage:
    python server.py                    # stdio mode (Claude Desktop / claude.ai/code)
    fastmcp dev server.py               # development mode with inspector
    fastmcp install server.py           # install in Claude Desktop
"""

from __future__ import annotations

from mcp_einvoicing_core import EInvoicingMCPServer
from mcp_einvoicing_core.logging_utils import get_logger, setup_logging

from tools.directory_tools import register_directory_tools
from tools.ereporting_tools import register_ereporting_tools
from tools.flow_tools import register_flow_tools

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

setup_logging()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Server initialisation
# ---------------------------------------------------------------------------

_server = EInvoicingMCPServer(
    name="mcp-facture-electronique-fr",
    instructions=(
        "MCP server for French electronic invoicing (2026 reform, AFNOR XP Z12-013). "
        "Compatible Solution (CS) mode: intermediary between the company's information system and "
        "an Approved Platform (AP).\n\n"
        "**Flow Service** — submit and track flows (B2B invoices Factur-X/UBL/CII, "
        "e-reportings B2BInt/B2C, CDAR lifecycle statuses):\n"
        "  • submit_flow: submit a pre-built invoice or e-reporting binary\n"
        "  • submit_lifecycle_status: emit a CDAR status (Approved, Refused, Cashed…)\n"
        "  • search_flows: search flows by criteria\n"
        "  • get_flow: retrieve metadata or document of a flow\n"
        "  • healthcheck_flow: check the AP availability\n\n"
        "**E-Reporting Service** — build and submit DGFiP Flux 10 FRR payloads:\n"
        "  • submit_transaction_report: Flux 10.1/10.3 — B2C and international B2B transactions\n"
        "  • submit_payment_report: Flux 10.2/10.4 — payment data for B2C/intl B2B invoices\n"
        "  • validate_ereporting_xml: validate FRR XML against DGFiP v3.2 XSD\n\n"
        "**Directory Service** — query and maintain the PPF directory:\n"
        "  • get_company_by_siren / search_company: verify a taxable entity\n"
        "  • get_establishment_by_siret / search_establishment: verify an establishment\n"
        "  • search_routing_code: look up routing codes\n"
        "  • get/search_directory_line: look up receiving addresses\n\n"
        "**Recommended workflow — invoicing:**\n"
        "1. get_directory_line(addressing_identifier=RECIPIENT_SIREN) → verify registration\n"
        "2. submit_flow(file_base64=..., processing_rule='B2B', flow_type='CustomerInvoice')\n"
        "3. get_flow(flow_id=...) → track status\n\n"
        "**Recommended workflow — international B2B e-reporting:**\n"
        "1. submit_transaction_report(processing_rule='B2BInt', "
        "flow_type='IndividualCustomerTransactionReport', invoices_json=[...])\n"
        "2. submit_payment_report(processing_rule='B2BInt', "
        "flow_type='UnitaryCustomerPaymentReport', invoices_json=[...])  # when payment received\n\n"
        "Auth: OAuth2 Bearer JWT (automatic renewal). "
        "Config via environment variables (.env)."
    ),
)
mcp = _server.mcp

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

register_flow_tools(mcp)
register_ereporting_tools(mcp)
register_directory_tools(mcp)

logger.info(
    "MCP server 'mcp-facture-electronique-fr' initialised — "
    "5 Flow Service tools + 3 E-Reporting tools + 12 Directory Service tools"
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server in stdio mode."""
    _server.run()


if __name__ == "__main__":
    main()
