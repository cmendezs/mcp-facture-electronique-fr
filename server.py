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

from fastmcp import FastMCP
from mcp_einvoicing_core.logging_utils import get_logger, setup_logging

from tools.directory_tools import register_directory_tools
from tools.flow_tools import register_flow_tools

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

setup_logging()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server initialisation
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="mcp-facture-electronique-fr",
    instructions=(
        "MCP server for French electronic invoicing (2026 reform, AFNOR XP Z12-013). "
        "Compatible Solution (CS) mode: intermediary between the company's information system and "
        "an Approved Platform (AP).\n\n"
        "**Flow Service** — submit and track flows (B2B invoices Factur-X/UBL/CII, "
        "e-reportings B2BInt/B2C, CDAR lifecycle statuses):\n"
        "  • submit_flow: submit an invoice or an e-reporting\n"
        "  • submit_lifecycle_status: emit a status (Approved, Refused, Cashed…)\n"
        "  • search_flows: search flows by criteria\n"
        "  • get_flow: retrieve metadata or document of a flow\n"
        "  • healthcheck_flow: check the AP availability\n\n"
        "**Directory Service** — query and maintain the PPF directory:\n"
        "  • get_company_by_siren / search_company: verify a taxable entity\n"
        "  • get_establishment_by_siret / search_establishment: verify an establishment\n"
        "  • search/create/update_routing_code: manage routing codes\n"
        "  • get/search/create/update/delete_directory_line: manage receiving addresses\n\n"
        "**Recommended workflow before issuing an invoice:**\n"
        "1. get_directory_line(addressing_identifier=RECIPIENT_SIREN) → verify registration\n"
        "2. submit_flow(file_base64=..., processing_rule='B2B', flow_type='Invoice')\n"
        "3. get_flow(flow_id=...) → track status\n\n"
        "Auth: OAuth2 Bearer JWT (automatic renewal). "
        "Config via environment variables (.env)."
    ),
)

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

register_flow_tools(mcp)
register_directory_tools(mcp)

logger.info(
    "MCP server 'mcp-facture-electronique-fr' initialised — "
    "5 Flow Service tools + 12 Directory Service tools"
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server in stdio mode."""
    mcp.run()


if __name__ == "__main__":
    main()
