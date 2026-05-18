"""Pre-publish audit: verify mcp-facture-electronique-fr coherence against mcp-einvoicing-core.

Run standalone (from the workspace root):
    uv run python mcp-facture-electronique-fr/audit/audit_vs_core.py
    uv run python mcp-facture-electronique-fr/audit/audit_vs_core.py --output mcp-facture-electronique-fr/audit/report.json
    uv run python mcp-facture-electronique-fr/audit/audit_vs_core.py --fail-on blocking
    uv run python mcp-facture-electronique-fr/audit/audit_vs_core.py --fail-on warnings

Exit codes:
    0  All checks passed
    1  Warnings only (non-blocking)
    2  Blocking failures found

This script is designed to be importable with no side effects; all execution
is guarded by `if __name__ == "__main__"`.

CHECK 1 and CHECK 4 are delegated to mcp_einvoicing_core.audit.
CHECK 2 (tool registry) and CHECK 5 (FR-specific structural) are implemented here.
CHECK 3 is skipped: mcp-facture-electronique-fr is a Compatible Solution (CS)
with no primary invoice model class.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp_einvoicing_core.audit import (
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    SEVERITY_WARNING,
    AuditReport,
    CheckFinding,
    CheckResult,
    _try_import,
    make_report,
    parse_audit_args,
    render_summary_table,
    run_check_core_coverage,
    run_check_version_compatibility,
)

# ---------------------------------------------------------------------------
# CHECK 1 configuration — country-specific constants
# ---------------------------------------------------------------------------

# mcp-facture-electronique-fr is a Compatible Solution (CS) under XP Z12-013.
# It does not generate or validate invoice documents; it proxies pre-built flows
# to an Approved Platform (PA). There is no primary invoice model class.
# The invoice tree check is therefore skipped (is_en16931_family=None).
_IS_EN16931_FAMILY: bool | None = None  # skip — no invoice model
_PRIMARY_INVOICE_CLASS: tuple[str, str] | None = None  # skip — no invoice model

_INTENTIONAL_OVERRIDES: dict[str, set[str]] = {
    # FR uses EInvoicingMCPServer from base_server; ABC base classes are not subclassed.
    "mcp_einvoicing_core.base_server": {
        "BaseDocumentGenerator",
        "BaseDocumentParser",
        "BaseDocumentValidator",
        "BasePartyValidator",
    },
    # FR is a CS — no document-level signing (XAdES or otherwise).
    "mcp_einvoicing_core.digital_signature": {
        "BaseDocumentSigner",
        "XAdESEPESSigner",
        "XAdESSignerConfig",
    },
    # FR does not download validation schemas (no XSD, no Schematron).
    "mcp_einvoicing_core.download_rules": {
        "DownloadSpec",
        "download_artefacts",
    },
    # FR is non-EN 16931; EN 16931 semantic classes are not used.
    "mcp_einvoicing_core.en16931": {
        "EN16931Address",
        "EN16931AllowanceCharge",
        "EN16931Invoice",
        "EN16931LineItem",
        "EN16931Party",
        "EN16931PaymentMeans",
        "EN16931Tax",
    },
    # FR raises PlatformError and AuthenticationError; others are not raised.
    "mcp_einvoicing_core.exceptions": {
        "DocumentGenerationError",
        "PartyValidationError",
        "SchematronValidationError",
        "ValidationError",
    },
    # FR has no invoice model; model classes are not used at runtime.
    "mcp_einvoicing_core.models": {
        "InvoiceDocument",
        "InvoiceLine",
        "InvoiceParty",
        "InvoicePartyAddress",
        "PaymentTerms",
        "TaxBreakdown",
        "TaxIdentifier",
    },
    # FR does not generate or embed PDFs (CS — caller supplies the PDF).
    "mcp_einvoicing_core.pdf": {
        "PDFEmbedder",
    },
    # FR does not use Peppol (XP Z12-013 uses the PPF/PDP ecosystem).
    "mcp_einvoicing_core.peppol": {
        "PeppolClient",
        "PeppolParticipantId",
        "SMPClient",
        "lookup_peppol_participant",
    },
    # FR does not declare format profiles (CS — the AP handles profile routing).
    "mcp_einvoicing_core.profile_registry": {
        "ProfileRegistry",
        "SyntaxProfile",
        "get_profile_registry",
    },
    # FR does not generate QR codes.
    "mcp_einvoicing_core.qr": {
        "generate_qr_png_base64",
    },
    # FR does not perform Schematron validation (CS — the AP validates the document).
    "mcp_einvoicing_core.schematron": {
        "BaseStructuredValidator",
        "SchematronValidator",
        "ValidationMessage",
        "ValidationResult",
    },
    # FR builds CDAR XML via xml.sax.saxutils (not the core xml_utils helpers).
    "mcp_einvoicing_core.xml_utils": {
        "validate_iban",
        "xml_element",
        "xml_optional",
    },
}

_PKG_MODULES: list[str] = [
    "server",
    "config",
    "clients.flow_client",
    "clients.directory_client",
    "tools.flow_tools",
    "tools.directory_tools",
]

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


# ---------------------------------------------------------------------------
# CHECK 2 — Tool registry completeness
# ---------------------------------------------------------------------------

_REQUIRED_FLOW_TOOLS: dict[str, str] = {
    "submit_flow":             "Submit invoice, e-reporting, or CDAR to the Approved Platform",
    "search_flows":            "Search flows by criteria (status, type, period)",
    "get_flow":                "Retrieve flow metadata or document by flowId",
    "submit_lifecycle_status": "Emit CDAR lifecycle status (Refused, Approved, Cashed, etc.)",
    "healthcheck_flow":        "Check Flow Service availability",
}

_REQUIRED_DIRECTORY_TOOLS: dict[str, str] = {
    "search_company":          "Search companies (SIRENs) in the PPF directory",
    "get_company_by_siren":    "Look up a company by SIREN",
    "search_establishment":    "Search establishments (SIRETs) in the PPF directory",
    "get_establishment_by_siret": "Look up an establishment by SIRET",
    "search_routing_code":     "Search routing codes for a recipient",
    "create_routing_code":     "Create a routing code for a SIRET",
    "update_routing_code":     "Update an existing routing code",
    "search_directory_line":   "Search directory lines (receiving addresses)",
    "get_directory_line":      "Look up a directory line by addressing identifier",
    "create_directory_line":   "Create a directory line (receiving address)",
    "update_directory_line":   "Update an existing directory line",
    "delete_directory_line":   "Delete a directory line",
}

_REQUIRED_TOOL_CATEGORIES: dict[str, str] = {
    **_REQUIRED_FLOW_TOOLS,
    **_REQUIRED_DIRECTORY_TOOLS,
}


def _collect_registered_tools() -> set[str]:
    """Instantiate a test FastMCP and register both tool sets; return tool names."""
    import asyncio  # noqa: PLC0415
    registered: set[str] = set()
    try:
        from fastmcp import FastMCP as _FastMCP  # noqa: PLC0415
        from tools.directory_tools import register_directory_tools  # noqa: PLC0415
        from tools.flow_tools import register_flow_tools  # noqa: PLC0415

        test_mcp = _FastMCP("fr-audit-test")
        register_flow_tools(test_mcp)
        register_directory_tools(test_mcp)

        tools = asyncio.run(test_mcp.list_tools())
        registered = {t.name for t in tools}
    except Exception:
        pass
    return registered


def run_check_2() -> CheckResult:
    """CHECK 2 — Tool registry completeness."""
    result = CheckResult(check_id="CHECK_2", name="Tool registry completeness")
    registered = _collect_registered_tools()

    if not registered:
        result.findings.append(CheckFinding(
            check_id="CHECK_2", tag="[SKIP]", severity=SEVERITY_WARNING,
            symbol="FastMCP tool registry",
            message=(
                "Could not introspect FastMCP tool registry. "
                "Verify that register_flow_tools and register_directory_tools are importable."
            ),
        ))
        return result

    for tool_name, description in _REQUIRED_TOOL_CATEGORIES.items():
        tag = "[OK]" if tool_name in registered else "[MISSING_TOOL]"
        sev = SEVERITY_OK if tool_name in registered else SEVERITY_BLOCKING
        result.findings.append(CheckFinding(
            check_id="CHECK_2", tag=tag, severity=sev,
            symbol=tool_name,
            message=(
                f"Tool '{tool_name}' is registered. ({description})"
                if tool_name in registered
                else (
                    f"Required tool '{tool_name}' ({description}) not found in "
                    "the FastMCP tool registry. Ensure it is decorated with @mcp.tool."
                )
            ),
        ))

    for tool_name in sorted(registered - set(_REQUIRED_TOOL_CATEGORIES)):
        result.findings.append(CheckFinding(
            check_id="CHECK_2", tag="[EXTRA]", severity=SEVERITY_OK,
            symbol=tool_name,
            message=f"Tool '{tool_name}' is registered but not in the required spec.",
        ))

    return result


# ---------------------------------------------------------------------------
# CHECK 5 — FR-specific structural checks
# ---------------------------------------------------------------------------

def run_check_5() -> CheckResult:
    """CHECK 5 — FR-specific structural and completeness checks."""
    result = CheckResult(check_id="CHECK_5", name="FR-specific structural checks")

    # 5a: server module exports main and mcp
    server_mod, err = _try_import("server")
    if server_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_BLOCKING,
            symbol="server",
            message=f"Could not import server module: {err}",
        ))
    else:
        for attr in ("main", "mcp"):
            tag = "[OK]" if hasattr(server_mod, attr) else "[MISSING]"
            sev = SEVERITY_OK if hasattr(server_mod, attr) else SEVERITY_BLOCKING
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag=tag, severity=sev,
                symbol=f"server.{attr}",
                message=(
                    f"server.{attr} is present."
                    if hasattr(server_mod, attr)
                    else f"server.{attr} is missing — required for MCP server operation."
                ),
            ))

        mcp_obj = getattr(server_mod, "mcp", None)
        if mcp_obj is not None:
            mcp_type = type(mcp_obj).__name__
            tag = "[OK]" if mcp_type == "FastMCP" else "[UNEXPECTED_TYPE]"
            sev = SEVERITY_OK if mcp_type == "FastMCP" else SEVERITY_WARNING
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag=tag, severity=sev,
                symbol="server.mcp",
                message=(
                    "server.mcp is a FastMCP instance."
                    if mcp_type == "FastMCP"
                    else (
                        f"server.mcp is {mcp_type!r}, expected FastMCP. "
                        "Verify tool registration is using FastMCP decorators."
                    )
                ),
            ))

    # 5b: FlowClient and DirectoryClient are importable
    for sym in ("clients.flow_client.FlowClient", "clients.directory_client.DirectoryClient"):
        mod_path, cls_name = sym.rsplit(".", 1)
        mod, err = _try_import(mod_path)
        if mod is None:
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_BLOCKING,
                symbol=sym,
                message=f"Could not import {mod_path}: {err}",
            ))
        elif not hasattr(mod, cls_name):
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_BLOCKING,
                symbol=sym,
                message=f"{cls_name} not found in {mod_path}.",
            ))
        else:
            result.findings.append(CheckFinding(
                check_id="CHECK_5", tag="[OK]", severity=SEVERITY_OK,
                symbol=sym,
                message=f"{sym} is importable and present.",
            ))

    # 5c: specs/README.md exists (FR-11)
    specs_readme = Path(__file__).parent.parent / "specs" / "README.md"
    if specs_readme.exists():
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[OK]", severity=SEVERITY_OK,
            symbol="specs/README.md",
            message="specs/README.md index file is present.",
        ))
    else:
        result.findings.append(CheckFinding(
            check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_WARNING,
            symbol="specs/README.md",
            message=(
                "specs/README.md is missing. "
                "Add an index of spec files with source, version, and retrieval date (FR-11)."
            ),
        ))

    # 5d: PAConfig has per-service scope fields (FR-8)
    config_mod, err = _try_import("config")
    if config_mod is not None:
        cfg_cls = getattr(config_mod, "PAConfig", None)
        if cfg_cls is not None:
            for field_name in ("pa_oauth_scope_flow", "pa_oauth_scope_directory"):
                if hasattr(cfg_cls, "model_fields") and field_name in cfg_cls.model_fields:
                    result.findings.append(CheckFinding(
                        check_id="CHECK_5", tag="[OK]", severity=SEVERITY_OK,
                        symbol=f"PAConfig.{field_name}",
                        message=f"PAConfig.{field_name} is defined (FR-8 per-service scope).",
                    ))
                else:
                    result.findings.append(CheckFinding(
                        check_id="CHECK_5", tag="[MISSING]", severity=SEVERITY_WARNING,
                        symbol=f"PAConfig.{field_name}",
                        message=(
                            f"PAConfig.{field_name} is missing. "
                            "Add per-service OAuth2 scope fields (FR-8)."
                        ),
                    ))

    return result


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def run_audit() -> AuditReport:
    """Execute all checks and return the aggregated AuditReport. No side effects."""
    report = make_report("mcp-facture-electronique-fr", _PYPROJECT)

    report.checks.append(run_check_core_coverage(
        package_name="mcp-facture-electronique-fr",
        package_modules=_PKG_MODULES,
        intentional_overrides=_INTENTIONAL_OVERRIDES,
        is_en16931_family=_IS_EN16931_FAMILY,
        primary_invoice_class=_PRIMARY_INVOICE_CLASS,
    ))
    report.checks.append(run_check_2())
    report.checks.append(run_check_version_compatibility(
        package_name="mcp-facture-electronique-fr",
        pyproject_path=_PYPROJECT,
    ))
    report.checks.append(run_check_5())

    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_audit_args(
        "Pre-publish audit: mcp-facture-electronique-fr vs mcp-einvoicing-core", argv
    )
    report = run_audit()

    output_path = Path(args.output) if args.output else Path("audit/report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    if not args.quiet:
        print(render_summary_table(report))
        print(f"\nJSON report written to: {output_path}")

    if args.fail_on == "never":
        return 0
    if args.fail_on == "warnings":
        return min(report.exit_code, 2)
    return 2 if report.total_blocking > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
