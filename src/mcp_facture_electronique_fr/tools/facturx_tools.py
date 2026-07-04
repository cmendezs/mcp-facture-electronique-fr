"""MCP tools for Factur-X CII XML validation (Schematron / SVRL).

Scope: structural/business-rule validation of the embedded CII XML against
the bundled Factur-X 1.08 Schematron rulesets. This is a document-format
check, independent of the XP Z12-013 flow-submission lifecycle — it does not
call the PDP/PPF API. See mcp_facture_electronique_fr/validators.py for the
supported profile list and the EXTENDED-CTC-FR caveat.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from mcp_facture_electronique_fr.validators import (
    SUPPORTED_FACTURX_PROFILES,
    FacturXStylesheetUnsupportedError,
    UnsupportedFacturXProfileError,
    get_facturx_validator,
)

logger = logging.getLogger(__name__)


def register_facturx_tools(mcp: FastMCP) -> None:
    """Register Factur-X validation tools with the MCP server."""

    @mcp.tool()
    async def validate_facturx(
        xml_content: Annotated[
            str,
            Field(description="Factur-X CII XML content to validate (the embedded XML, not the PDF/A-3)."),
        ],
        profile: Annotated[
            str,
            Field(
                description=(
                    "Factur-X profile to validate against. One of: "
                    + ", ".join(SUPPORTED_FACTURX_PROFILES)
                    + ". EXTENDED-CTC-FR is validated against the generic EXTENDED "
                    "ruleset only — AFNOR has not published a CTC-FR-specific "
                    "Schematron; French-specific rules beyond EXTENDED are not checked."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """Validate a Factur-X CII XML document against its profile's Schematron ruleset.

        Scope: Schematron (SVRL) business-rule validation only, no XSD structural
        check. Returns is_valid, errors, and warnings (rule_id, location, text).
        Use this before embedding the XML into a PDF/A-3 or submitting via submit_flow.

        Requires the optional `saxonche` extra (FR-XSLT2-1, resolved in
        mcp-einvoicing-core 1.14.0): the bundled Factur-X 1.08 Schematron
        stylesheets require XSLT 2.0, which lxml/libxslt (XSLT 1.0 only) cannot
        compile. Install with `pip install mcp-facture-electronique-fr[xslt2]`.
        If it is missing, this tool returns level="unavailable" with
        is_valid=None instead of raising.
        """
        try:
            validator = get_facturx_validator(profile)
        except UnsupportedFacturXProfileError as exc:
            return {
                "is_valid": False,
                "level": "profile-error",
                "profile": profile,
                "error_count": 1,
                "warning_count": 0,
                "errors": [{"severity": "error", "rule_id": "PROFILE", "location": "", "text": str(exc)}],
                "warnings": [],
            }
        except FacturXStylesheetUnsupportedError as exc:
            return {
                "is_valid": None,
                "level": "unavailable",
                "profile": profile,
                "message": str(exc),
                "error_count": 0,
                "warning_count": 0,
                "errors": [],
                "warnings": [],
            }

        result = validator.validate(xml_content.encode("utf-8"), profile=profile, syntax="CII")
        result_dict = result.to_dict()
        result_dict["level"] = "schematron"
        return result_dict
