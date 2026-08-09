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
CHECK 2 (tool registry), CHECK 5 (FR-specific structural), CHECK 6
(parallel-implementation detector), and CHECK 7 (BLOCKING CII/UBL structural
roundtrip, FR-AG-2) are implemented here.
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
    # Factur-X/UBL/CII use XAdES-EPES via Chorus Pro PDP. load_certificate_der
    # (core v1.16.0) is a helper for country packages building custom auth
    # claims from a cert's public bytes (e.g. ES FACe's JWS "username" claim);
    # FR has no such flow.
    "mcp_einvoicing_core.digital_signature": {
        "ABC",
        "BaseDocumentSigner",
        "CAdESSigner",
        "CAdESSignerConfig",
        "XAdESEPESSigner",
        "XAdESSignerConfig",
        "XMLDSigSigner",
        "XMLDSigSignerConfig",
        "abstractmethod",
        "dataclass",
        "datetime",
        "field",
        "load_certificate_der",
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
    # token cache, re-exported stdlib) are not directly imported. JWSConfig
    # (core v1.16.0) configures RS256/x5c JWT auth for platforms like ES
    # FACe; FR's Flow/Directory/E-Reporting APIs use OAuth2, not JWS.
    "mcp_einvoicing_core.http_client": {
        "Any",
        "AuthenticationError",
        "BaseEInvoicingConfig",
        "BaseModel",
        "BaseSettings",
        "Enum",
        "Field",
        "JWSConfig",
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
    "mcp_facture_electronique_fr.models.invoice",
    "mcp_facture_electronique_fr.models.annuaire",
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

_REQUIRED_FACTURX_TOOLS: dict[str, str] = {
    "validate_facturx": "Validate a Factur-X CII payload against a Schematron profile",
}

_REQUIRED_EREPORTING_TOOLS: dict[str, str] = {
    "validate_ereporting_xml": "Validate a DGFiP Flux 10 e-reporting FRR XML payload",
    "submit_transaction_report": "Submit a Flux 10.1/10.3 transaction e-reporting flow",
    "submit_payment_report": "Submit a Flux 10.2/10.4 payment e-reporting flow",
}

_REQUIRED_WEBHOOK_TOOLS: dict[str, str] = {
    "list_webhooks": "List registered webhook subscriptions",
    "get_webhook": "Retrieve a webhook subscription by ID",
    "create_webhook": "Create a webhook subscription",
    "update_webhook": "Update an existing webhook subscription",
    "delete_webhook": "Delete a webhook subscription",
}

_REQUIRED_TOOL_CATEGORIES: dict[str, str] = {
    **_REQUIRED_FLOW_TOOLS,
    **_REQUIRED_DIRECTORY_TOOLS,
    **_REQUIRED_FACTURX_TOOLS,
    **_REQUIRED_EREPORTING_TOOLS,
    **_REQUIRED_WEBHOOK_TOOLS,
}


def _collect_registered_tools() -> set[str]:
    """Instantiate a test FastMCP and register every tool set; return tool names."""
    import asyncio  # noqa: PLC0415
    registered: set[str] = set()
    try:
        from fastmcp import FastMCP as _FastMCP  # noqa: PLC0415
        from mcp_facture_electronique_fr.tools.directory_tools import register_directory_tools  # noqa: PLC0415
        from mcp_facture_electronique_fr.tools.ereporting_tools import register_ereporting_tools  # noqa: PLC0415
        from mcp_facture_electronique_fr.tools.facturx_tools import register_facturx_tools  # noqa: PLC0415
        from mcp_facture_electronique_fr.tools.flow_tools import register_flow_tools  # noqa: PLC0415
        from mcp_facture_electronique_fr.tools.webhook_tools import register_webhook_tools  # noqa: PLC0415

        test_mcp = _FastMCP("fr-audit-test")
        register_flow_tools(test_mcp)
        register_directory_tools(test_mcp)
        register_facturx_tools(test_mcp)
        register_ereporting_tools(test_mcp)
        register_webhook_tools(test_mcp)

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


# ---------------------------------------------------------------------------
# CHECK 7 — CII / UBL generate -> parse structural roundtrip (FR-AG-2)
# ---------------------------------------------------------------------------

_ROUNDTRIP_PROFILE_URN = "urn:factur-x.eu:1p0:en16931"
_ROUNDTRIP_FACTURX_SCHEME_ID = "urn:cen.eu:en16931:2017"


def _build_roundtrip_invoice():
    """Build a minimal FRInvoice for the CHECK 7 structural roundtrip."""
    from decimal import Decimal  # noqa: PLC0415

    from mcp_facture_electronique_fr.models import FRInvoice, FRParty  # noqa: PLC0415

    address = {
        "line_one": "1 rue de Rivoli",
        "city": "Paris",
        "postcode": "75001",
        "country_code": "FR",
    }
    return FRInvoice(
        profile=_ROUNDTRIP_PROFILE_URN,
        invoice_number="AUDIT-CHECK-7",
        invoice_date="2026-07-01",
        currency_code="EUR",
        seller=FRParty(name="Vendeur SAS", siren="732829320", address=address),
        buyer=FRParty(name="Acheteur SARL", siren="404833048", address=address),
        sum_of_line_net_amounts=Decimal("1000.00"),
        allowances_total=Decimal("0.00"),
        charges_total=Decimal("0.00"),
        tax_exclusive_amount=Decimal("1000.00"),
        tax_total=Decimal("200.00"),
        tax_inclusive_amount=Decimal("1200.00"),
        amount_due=Decimal("1200.00"),
        tax_lines=[
            {
                "category": "S",
                "rate": Decimal("20.00"),
                "taxable_amount": Decimal("1000.00"),
                "tax_amount": Decimal("200.00"),
            }
        ],
    )


def run_check_7() -> CheckResult:
    """CHECK 7 — BLOCKING generate -> parse structural roundtrip for CII and UBL.

    This is the guardrail that would have caught FR-SC-1 (CII BT-24 profile
    URN emitted as a stray text= attribute with empty element text instead of
    real element text + schemeID). Deliberately does not depend on the
    optional saxonche/Schematron backend so it always runs in CI.
    """
    result = CheckResult(check_id="CHECK_7", name="CII/UBL structural roundtrip")

    try:
        from mcp_facture_electronique_fr.wire_formats import (  # noqa: PLC0415
            FRCIIParser,
            FRCIISerializer,
            FRUBLParser,
            FRUBLSerializer,
        )

        invoice = _build_roundtrip_invoice()
    except Exception as exc:  # noqa: BLE001
        result.findings.append(CheckFinding(
            check_id="CHECK_7", tag="[ERROR]", severity=SEVERITY_BLOCKING,
            symbol="roundtrip-setup",
            message=f"Could not construct the roundtrip fixture: {exc}",
        ))
        return result

    # --- CII ---
    try:
        from lxml import etree  # noqa: PLC0415

        cii_bytes = FRCIISerializer().serialize(invoice)
        root = etree.fromstring(cii_bytes)
        rsm_ns = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
        ram_ns = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
        guideline_id = root.find(
            f"{{{rsm_ns}}}ExchangedDocumentContext"
            f"/{{{ram_ns}}}GuidelineSpecifiedDocumentContextParameter"
            f"/{{{ram_ns}}}ID"
        )
        if guideline_id is None or guideline_id.text != invoice.profile:
            result.findings.append(CheckFinding(
                check_id="CHECK_7", tag="[CII_PROFILE_URN]", severity=SEVERITY_BLOCKING,
                symbol="FRCIISerializer",
                message=(
                    "GuidelineSpecifiedDocumentContextParameter/ID is missing or its "
                    f"text does not equal invoice.profile (got: "
                    f"{getattr(guideline_id, 'text', None)!r})."
                ),
            ))
        elif guideline_id.get("schemeID") != _ROUNDTRIP_FACTURX_SCHEME_ID:
            result.findings.append(CheckFinding(
                check_id="CHECK_7", tag="[CII_SCHEME_ID]", severity=SEVERITY_BLOCKING,
                symbol="FRCIISerializer",
                message=(
                    f"GuidelineSpecifiedDocumentContextParameter/ID schemeID is "
                    f"{guideline_id.get('schemeID')!r}, expected {_ROUNDTRIP_FACTURX_SCHEME_ID!r}."
                ),
            ))
        else:
            parsed = FRCIIParser().parse(cii_bytes)
            if parsed.profile != invoice.profile:
                result.findings.append(CheckFinding(
                    check_id="CHECK_7", tag="[CII_ROUNDTRIP]", severity=SEVERITY_BLOCKING,
                    symbol="FRCIIParser",
                    message=(
                        f"CII roundtrip did not preserve profile: got {parsed.profile!r}, "
                        f"expected {invoice.profile!r}."
                    ),
                ))
            else:
                result.findings.append(CheckFinding(
                    check_id="CHECK_7", tag="[OK]", severity=SEVERITY_OK,
                    symbol="FRCIISerializer/FRCIIParser",
                    message="CII generate -> parse roundtrip preserves BT-24 profile URN and schemeID.",
                ))
    except Exception as exc:  # noqa: BLE001
        result.findings.append(CheckFinding(
            check_id="CHECK_7", tag="[ERROR]", severity=SEVERITY_BLOCKING,
            symbol="FRCIISerializer",
            message=f"CII generate/parse roundtrip raised: {exc}",
        ))

    # --- UBL ---
    try:
        ubl_bytes = FRUBLSerializer().serialize(invoice)
        parsed_ubl = FRUBLParser().parse(ubl_bytes)
        if parsed_ubl.profile != invoice.profile:
            result.findings.append(CheckFinding(
                check_id="CHECK_7", tag="[UBL_ROUNDTRIP]", severity=SEVERITY_BLOCKING,
                symbol="FRUBLParser",
                message=(
                    f"UBL roundtrip did not preserve profile: got {parsed_ubl.profile!r}, "
                    f"expected {invoice.profile!r}."
                ),
            ))
        else:
            result.findings.append(CheckFinding(
                check_id="CHECK_7", tag="[OK]", severity=SEVERITY_OK,
                symbol="FRUBLSerializer/FRUBLParser",
                message="UBL generate -> parse roundtrip preserves BT-24 profile URN.",
            ))
    except Exception as exc:  # noqa: BLE001
        result.findings.append(CheckFinding(
            check_id="CHECK_7", tag="[ERROR]", severity=SEVERITY_BLOCKING,
            symbol="FRUBLSerializer",
            message=f"UBL generate/parse roundtrip raised: {exc}",
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
    report.checks.append(run_check_7())

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
