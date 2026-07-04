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

# All formats accepted by the French reform (Factur-X, UBL 2.1, CII) are
# based on EN 16931 (NF EN 16931-1).  FRInvoice extends EN16931Invoice.
_IS_EN16931_FAMILY: bool | None = True
_PRIMARY_INVOICE_CLASS: tuple[str, str] | None = ("mcp_facture_electronique_fr.models", "FRInvoice")

_INTENTIONAL_OVERRIDES: dict[str, set[str]] = {
    # OVERRIDE-REASON: FR uses EInvoicingMCPServer from base_server; ABC base
    # classes and lifecycle/generator/parser/validator ABCs are not subclassed
    # (CS architecture delegates document handling to the AP).
    "mcp_einvoicing_core.base_server": {
        "ABC",
        "Any",
        "BaseDocumentGenerator",
        "BaseDocumentParser",
        "BaseDocumentValidator",
        "BaseLifecycleManager",
        "BaseModel",
        "BasePartyValidator",
        "DocumentValidationResult",
        "FastMCP",
        "Field",
        "Generic",
        "InvoiceDocument",
        "InvoiceParty",
        "SubmitResult",
        "TaxIdValidationResult",
        "TypeVar",
        "abstractmethod",
        "scrub",
    },
    # OVERRIDE-REASON: FR is a CS, no document-level signing (XAdES or
    # XML-DSig). XMLDSigSigner (core v1.4.0) is the BR NF-e enveloped signer;
    # Factur-X/UBL/CII use XAdES-EPES via Chorus Pro PDP.
    "mcp_einvoicing_core.digital_signature": {
        "ABC",
        "BaseDocumentSigner",
        "XAdESEPESSigner",
        "XAdESSignerConfig",
        "XMLDSigSigner",
        "XMLDSigSignerConfig",
        "abstractmethod",
        "dataclass",
        "datetime",
        "field",
        "safe_fromstring",
        "timezone",
    },
    # OVERRIDE-REASON: FR does not download validation schemas (no XSD, no
    # Schematron). The AP validates documents.
    "mcp_einvoicing_core.download_rules": {
        "DownloadSpec",
        "Path",
        "dataclass",
        "download_artefacts",
        "entry_points",
        "field",
        "main",
    },
    # OVERRIDE-REASON: FR uses EN16931Invoice and EN16931Party via subclassing;
    # other EN 16931 helper classes and re-exported Pydantic symbols are not
    # directly imported.
    "mcp_einvoicing_core.en16931": {
        "BaseModel",
        "Decimal",
        "EN16931Address",
        "EN16931AllowanceCharge",
        "EN16931LineItem",
        "EN16931PaymentMeans",
        "EN16931Tax",
        "Field",
        "date",
        "field_validator",
        "model_validator",
    },
    # OVERRIDE-REASON: FR raises PlatformError and AuthenticationError via
    # BaseEInvoicingClient; other exception classes are not raised.
    "mcp_einvoicing_core.exceptions": {
        "AuthenticationError",
        "DocumentGenerationError",
        "EInvoicingError",
        "PartyValidationError",
        "PlatformError",
        "SchematronValidationError",
        "ValidationError",
        "XSDValidationError",
    },
    # OVERRIDE-REASON: FR uses BaseEInvoicingClient and AuthMode via
    # FlowClient/DirectoryClient; other http_client symbols (config classes,
    # token cache, re-exported stdlib) are not directly imported.
    "mcp_einvoicing_core.http_client": {
        "Any",
        "AuthenticationError",
        "BaseEInvoicingConfig",
        "BaseModel",
        "BaseSettings",
        "Enum",
        "Field",
        "OAuthValues",
        "Path",
        "PlatformError",
        "field_validator",
        "parsedate_to_datetime",
        "urlparse",
    },
    # OVERRIDE-REASON: FR does not use InvoiceDocument-family models (non-EN
    # 16931 pathway unused). TaxIdentifier is used indirectly via FRParty
    # field_validator but not imported at module level by FR source files.
    "mcp_einvoicing_core.models": {
        "BaseModel",
        "Decimal",
        "DocumentValidationResult",
        "Field",
        "InvoiceDocument",
        "InvoiceLine",
        "InvoiceLineItem",
        "InvoiceParty",
        "InvoicePartyAddress",
        "PartyAddress",
        "PaymentTerms",
        "TaxBreakdown",
        "TaxIdValidationResult",
        "TaxIdentifier",
        "VATSummary",
        "field_validator",
        "model_validator",
    },
    # OVERRIDE-REASON: FR does not generate or embed PDFs (CS architecture,
    # caller supplies the PDF/A-3).
    "mcp_einvoicing_core.pdf": {
        "PDFEmbedder",
    },
    # OVERRIDE-REASON: FR does not use Peppol (XP Z12-013 uses the PPF/PDP
    # ecosystem, not the Peppol 4-corner model).
    "mcp_einvoicing_core.peppol": {
        "Enum",
        "PeppolClient",
        "PeppolEnvironment",
        "PeppolLookupResult",
        "PeppolParticipantId",
        "PeppolSMPClient",
        "PeppolServiceInfo",
        "PlatformError",
        "SMPClient",
        "dataclass",
        "field",
        "lookup_peppol_participant",
        "safe_fromstring",
    },
    # OVERRIDE-REASON: FR does not declare format profiles (CS architecture,
    # the AP handles profile routing).
    "mcp_einvoicing_core.profile_registry": {
        "ProfileEntry",
        "ProfileRegistry",
        "SyntaxProfile",
        "dataclass",
        "get_profile_registry",
        "set_profile_registry",
    },
    # OVERRIDE-REASON: FR does not generate QR codes.
    "mcp_einvoicing_core.qr": {
        "generate_qr_png_base64",
    },
    # OVERRIDE-REASON: FR does not perform Schematron/XSD/JSON validation (CS
    # architecture, the AP validates the document).
    "mcp_einvoicing_core.schematron": {
        "ABC",
        "BaseJSONValidator",
        "BaseStructuredValidator",
        "BaseXSDValidator",
        "Path",
        "SchematronValidator",
        # SaxonSchematronValidator/get_xslt_version are used transitively via
        # load_schematron_validator() (FR-XSLT2-1) — not imported by name.
        "SaxonSchematronValidator",
        "get_xslt_version",
        "ValidationMessage",
        "ValidationResult",
        "abstractmethod",
        "dataclass",
        "field",
        "safe_fromstring",
        "safe_parser",
    },
    # OVERRIDE-REASON: FR builds CDAR XML via xml.sax.saxutils and delegates
    # invoice XML to core serializers; xml_utils helpers are not directly used.
    "mcp_einvoicing_core.xml_utils": {
        "Any",
        "Decimal",
        "filter_empty_values",
        "format_amount",
        "format_error",
        "format_quantity",
        "mark_untrusted",
        "mark_untrusted_fields",
        "resolve_xml_input",
        "safe_fromstring",
        "safe_parser",
        "validate_date_iso",
        "validate_iban",
        "xml_element",
        "xml_escape",
        "xml_optional",
    },
}

_PKG_MODULES: list[str] = [
    "mcp_facture_electronique_fr.server",
    "mcp_facture_electronique_fr.config",
    "mcp_facture_electronique_fr.models",
    "mcp_facture_electronique_fr.wire_formats",
    "mcp_facture_electronique_fr.clients.flow_client",
    "mcp_facture_electronique_fr.clients.directory_client",
    "mcp_facture_electronique_fr.tools.flow_tools",
    "mcp_facture_electronique_fr.tools.directory_tools",
    "mcp_facture_electronique_fr.validators",
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
        from mcp_facture_electronique_fr.tools.directory_tools import register_directory_tools  # noqa: PLC0415
        from mcp_facture_electronique_fr.tools.flow_tools import register_flow_tools  # noqa: PLC0415

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
    server_mod, err = _try_import("mcp_facture_electronique_fr.server")
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
    for sym in ("mcp_facture_electronique_fr.clients.flow_client.FlowClient", "mcp_facture_electronique_fr.clients.directory_client.DirectoryClient"):
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
    config_mod, err = _try_import("mcp_facture_electronique_fr.config")
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

# ---------------------------------------------------------------------------
# CHECK 6 — Parallel-implementation detector (Phase 0a.2)
# ---------------------------------------------------------------------------

_CORE_CAPABILITIES: list[tuple[str, str, list[str]]] = [
    ("cii_ubl_conversion", "mcp_einvoicing_core.convert", [
        "convert_wire_format",
    ]),
    ("peppol_participant_lookup", "mcp_einvoicing_core.peppol", [
        "PeppolSMPClient",
    ]),
    ("en16931_cii_parsing", "mcp_einvoicing_core.wire_formats", [
        "EN16931CIIParser", "EN16931CIISerializer",
    ]),
    ("en16931_ubl_parsing", "mcp_einvoicing_core.wire_formats", [
        "EN16931UBLParser", "EN16931UBLSerializer",
    ]),
    ("schematron_validation", "mcp_einvoicing_core.schematron", [
        "SchematronValidator",
    ]),
    ("xades_xmldsig_signing", "mcp_einvoicing_core.digital_signature", [
        "XAdESEPESSigner", "XMLDSigSigner",
    ]),
    ("http_client", "mcp_einvoicing_core.http_client", [
        "BaseEInvoicingClient",
    ]),
    ("routing_identifier_validation", "mcp_einvoicing_core.routing", [
        "RoutingIdentifier",
    ]),
    ("peppol_as4_transport", "mcp_einvoicing_core.peppol.transport", [
        "AS4MessageEnvelope", "AS4TransportClient", "PeppolTransmitter",
    ]),
]

_INTENTIONAL_PARALLEL_IMPLEMENTATIONS: dict[tuple[str, str], str] = {}


def run_check_6() -> CheckResult:
    """CHECK 6 — Parallel-implementation scan."""
    import ast

    result = CheckResult(check_id="CHECK_6", name="Parallel-implementation detector")

    pkg_root = Path(__file__).parent.parent / "src" / "mcp_facture_electronique_fr"
    if not pkg_root.is_dir():
        result.findings.append(CheckFinding(
            check_id="CHECK_6", tag="[SKIP]", severity=SEVERITY_OK,
            symbol="mcp_facture_electronique_fr",
            message="Package source directory not found; skipping parallel-implementation scan.",
        ))
        return result

    defined_names: dict[str, str] = {}
    for py_file in pkg_root.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_names[node.name] = str(py_file.relative_to(pkg_root.parent.parent))

    found_any = False
    for cap_tag, core_module, symbols in _CORE_CAPABILITIES:
        for symbol in symbols:
            if symbol not in defined_names:
                continue

            override_key = (cap_tag, symbol)
            if override_key in _INTENTIONAL_PARALLEL_IMPLEMENTATIONS:
                result.findings.append(CheckFinding(
                    check_id="CHECK_6", tag="[OVERRIDE]", severity=SEVERITY_OK,
                    symbol=symbol,
                    message=(
                        f"Parallel implementation of {symbol} ({cap_tag}) in "
                        f"{defined_names[symbol]} is intentional: "
                        f"{_INTENTIONAL_PARALLEL_IMPLEMENTATIONS[override_key]}"
                    ),
                ))
                continue

            found_any = True
            result.findings.append(CheckFinding(
                check_id="CHECK_6", tag="[PARALLEL]", severity=SEVERITY_WARNING,
                symbol=symbol,
                message=(
                    f"Country package defines {symbol!r} in {defined_names[symbol]}, "
                    f"which mirrors core capability {cap_tag!r} from {core_module}. "
                    "Delegate to the core symbol or register in "
                    "_INTENTIONAL_PARALLEL_IMPLEMENTATIONS with a justification."
                ),
            ))

    if not found_any and not result.findings:
        result.findings.append(CheckFinding(
            check_id="CHECK_6", tag="[OK]", severity=SEVERITY_OK,
            symbol="*",
            message="No parallel implementations of core capabilities detected.",
        ))

    return result


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
    report.checks.append(run_check_6())

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
