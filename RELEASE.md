# Release Process

This document describes how to release a new version of `mcp-facture-electronique-fr` to PyPI and the official MCP registry.

## One-Time Setup Requirements

### PyPI Trusted Publishing

PyPI publishing is fully automated via OIDC (no token stored). The Trusted Publisher is configured on PyPI under `cmendezs/mcp-facture-electronique-fr`, workflow `publish.yml`, environment `pypi`. No `.env` or secret needed.

### MCP Publisher CLI

Binary installed at `~/.local/bin/mcp-publisher` (already in `PATH`). To update to a newer version:

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_darwin_arm64.tar.gz" \
  | tar xzf - -C ~/.local/bin/
```

### MCP Registry Authentication

Authenticate once with GitHub (device flow):

```bash
mcp-publisher login github
```

---

## Release Steps

### 1. Bump the version

Edit **both** files — replace `X.X.X` with the new version (e.g. `0.1.3` → `0.1.4`):

- `pyproject.toml` → `version = "X.X.X"`
- `server.json` → `"version": "X.X.X"` and `"version": "X.X.X"` (in `packages[]`)

### 2. Commit, tag and push

GitHub Actions publishes to PyPI automatically on tag push.

```bash
git add pyproject.toml server.json
git commit -m "chore: bump version to X.X.X"
git push origin main
git tag vX.X.X
git push origin vX.X.X
```

### 3. Publish to the MCP registry

```bash
mcp-publisher publish
```

Expected output:
```
✓ Successfully published
✓ Server io.github.cmendezs/mcp-facture-electronique-fr version X.X.X
```

---

## Changelog

### [0.8.0] - 2026-07-15
Remediation sprint for the 2026-07 full-sweep audit
(`audit/2026-07-audit-fr.md`). Core pin bumped to `>=1.15.0,<2.0.0`.
#### Fixed
- **FR-SC-1 (HIGH):** `FRCIISerializer._build_root` no longer builds a
  parallel `ExchangedDocumentContext` subtree via `etree.SubElement(...,
  text=invoice.profile)` — lxml turns an unrecognised `text=` kwarg into a
  real XML attribute named `text`, leaving the actual element text empty.
  The serialiser now delegates fully to `super()._build_root()` (which
  also correctly emits BT-23 `BusinessProcessSpecifiedDocumentContextParameter`
  when `business_process` is set) and only adds the `schemeID` attribute
  onto the existing `GuidelineSpecifiedDocumentContextParameter/ID` element.
- **FR-SH-2 (MEDIUM):** `_validate_against_xsd` (e-reporting XSD validation)
  parsed untrusted XML with the stdlib `xml.etree.ElementTree` parser and a
  bare `lxml.etree.fromstring`. Both call sites now route through core's
  `safe_fromstring` (XXE / DoS hardened).
- **FR-SH-1 (MEDIUM):** e-reporting XML builders (`_build_transaction_invoice`,
  `_build_payment_invoice`) interpolated caller-supplied amount/percent
  fields into XML templates without escaping. All amount/percent fields are
  now coerced through `Decimal` first (new `_decimal_str` helper), rejecting
  injected markup with a structured `{"error": ...}` response.
- **FR-SH-3 (LOW):** `FRParty.siret` / `FRParty.siren` were pattern-only
  (14/9 digits) with no check-digit enforcement despite the docstring
  claiming Luhn validation. Added `field_validator`s delegating to core's
  `TaxIdentifier.validate_fr_siret` / `validate_fr_siren`.
- **FR-LC-1 (LOW, `[Unverified]` — no CDAR XSD bundled to confirm max
  cardinality directly):** `_build_lifecycle_status_xml` could emit two
  sibling `<ram:SpecifiedDocumentStatus>` elements when both a reason and a
  payment were set on the same status. Every bundled Annex B / `examples/cdar`
  worked example shows at most one status block per
  `ReferenceReferencedDocument`, so reason and payment content are now
  merged into a single block.
#### Added
- `tests/test_wire_formats.py` (FR-TC-1): `wire_formats.py` was previously
  at 0% test coverage; now at 100%. Covers CII BT-24 roundtrip (schemeID +
  text, no stray `text=` attributes) across every bundled Factur-X profile,
  UBL BT-23/BT-24 roundtrip, e-reporting XXE/injection guards, and SIRET/SIREN
  Luhn validation.
- Audit gate CHECK 7 (FR-AG-2): BLOCKING CII/UBL generate → parse structural
  roundtrip — the guardrail that would have caught FR-SC-1. Does not depend
  on the optional `saxonche` backend, so it always runs in CI. CHECK 2 also
  now covers the Factur-X, e-reporting, and webhook tool groups (previously
  only flow/directory tools were required).
#### Changed
- `FRInvoice.business_process` docstring documents Chorus Pro / PDP routing
  usage (FR-SC-2); consumer wiring itself required no code change beyond the
  core pin bump — `mcp-einvoicing-core` 1.15.0 already emits
  `<cbc:ProfileID>` for UBL when `business_process` is set.
#### Documentation
- `context-library/formats/facturx.md` (FR-DOC-1): corrected base standard
  from NF XP Z12-013 (API spec) to NF XP Z12-012 (formats spec), and pathway
  from `InvoiceDocument` to `EN16931Invoice` (matches `FRInvoice(EN16931Invoice)`).
- `context-library/countries/fr.md` (FR-DOC-2): flipped FR-SC-1 / FR-CORE-1 /
  FR-CORE-2 from BLOCKING/`[CONFIRMED GAP]` to `[DONE]` (resolved in Sprint 1,
  v0.4.0). Added an `FR_VAT_RATES` reference table by territory (FR-TL-1):
  metropolitan (20/10/5.5/2.1), Corsica (20/13/10/2.1/0.9), DOM
  (8.5/2.1/1.75/1.05) — advisory only, not enforced by this CS-architecture
  package.

### [0.7.0] - 2026-07-05
#### Added
- **CDAR PPF recipient + dispute fields (FR-CDAR-PPF-RECIPIENT-2026-07,
  resolved):** `PAConfig` gained optional `ppf_global_id` / `ppf_scheme_id`
  (default `0238`) / `ppf_name` (default `PPF`) / `ppf_role_code` (default
  `DFH`). `ppf_global_id` is unset by default — no bundled worked-example
  value (`9998`, `0000`) is a stable production identifier, so callers must
  supply their own. When set, `flow_client._build_lifecycle_status_xml`
  emits a second `RecipientTradeParty` sibling, matching the three-recipient
  shape confirmed in `UC2_F202500004_02-CDV-213_Rejetee.xml`. `submit_lifecycle_status`
  also gained `requested_action_code` / `requested_action` (MDT-121/122, per
  the `En_litige` worked example) and `included_note` (per the `Rejetee`
  worked example).
- **PPF Annuaire (directory) wiring (FR-FLUX11-2026-06, closed for the CRUD
  surface):** the directory tools are now wired directly against the
  bundled PPF-platform swagger `ppf-openapi-annuaire-api-public-1.11.0-openapi.json`
  (20 tools covering SIREN/SIRET lookup and search, code-routage CRUD,
  ligne-annuaire CRUD, and healthcheck). This is a deliberate framing
  shift: the tools are now PPF-platform-specific, not a PDP-agnostic Annex
  B abstraction — see the README "PPF Annuaire" note. New
  `models/annuaire.py` module for the write-path request bodies. The bulk
  `AnnuaireConsultationF11` full/differential sync flow remains out of
  scope, re-parked as `FR-FLUX11-BULK-2026-07` (blocked on the XP Z12-013
  swagger resupply).
- **Annex B v1.4 regression fixtures (FR-UC-CATALOG-2026-06, closed):**
  `tests/conftest.py` discovers the bundled Annex B v1.4 worked-example
  catalog (skips cleanly on wheel installs, where `specs/` is excluded).
  `tests/test_annex_b_regression.py` runs Factur-X Schematron validation
  and CDAR shape parsing over the discovered examples.
  `tests/test_flow.py` gained a worked-example reconstruction test
  comparing `_build_lifecycle_status_xml` output against the bundled CDAR
  examples that correspond to a `_STATUS_MAP` entry.
#### Changed
- `PA_BASE_URL_DIRECTORY` is deprecated (no longer read); the PPF Annuaire
  client now uses `PPF_ANNUAIRE_BASE_URL`, defaulting to the swagger's
  production `servers` URL.
- Several directory-tool parameter names changed to match the PPF Annuaire
  swagger contract (e.g. `addressing_identifier` → `id_instance`,
  `platform_id` → `matricule_plateforme`).
#### Fixed
- SIREN/SIRET validation in `tools/directory_tools.py` now delegates to
  core's `TaxIdentifier.validate_fr_siren()` / `validate_fr_siret()` instead
  of a duplicate inline Luhn implementation.

### [0.6.0] - 2026-07-03
#### Changed
- Bundled specs refreshed to the June 2026 AFNOR delivery: XP Z12-012 v1.4
  (FA301169) + Annex A/B v1.4, XP Z12-013 June 2026 text (FA301171, v1.2.0
  wire contract unchanged), XP Z12-014 v1.4 (FA301170) + Annex A/B v1.4.
  Docs and docstrings updated to cite the new versions. See `specs/README.md`
  for the full version history.
- `VATEX_CODES_EU` / `VATEX_CODES_FR` constants added to `ereporting_tools.py`
  (NF XP Z12-012 Annex A v1.4 "Codelists for XML Fx" worksheet). Documented,
  not enforced — `exemption_reason_code` (TT-59) remains free-form, consistent
  with this server's no-payload-semantic-validation design.
- **Packaging fix:** Factur-X 1.08 Schematron stylesheets (FNFE-MPE, no AFNOR
  restriction) and the DGFiP e-reporting XSDs are now bundled under
  `src/mcp_facture_electronique_fr/resources/`, shipped in the wheel/sdist.
  Previously `_XSD_DIR` in `ereporting_tools.py` resolved to `specs/dgfip/xsd/`,
  which `pyproject.toml` excludes from both build targets — `validate_ereporting_xml`'s
  `xsd` validation level was non-functional for any `pip`/`uvx`-installed copy
  of the server, silently falling back to well-formedness-only checks. Fixed.
#### Added
- `validate_facturx` MCP tool (`tools/facturx_tools.py`, `validators.py`):
  Schematron (SVRL) validation for Factur-X CII XML against MINIMUM, BASICWL,
  BASIC, EN16931, EXTENDED, and EXTENDED-CTC-FR (mapped to the generic
  EXTENDED ruleset — AFNOR has not published a CTC-FR-specific Schematron).
#### Fixed
- **FR-XSLT2-1 (resolved):** all five bundled Factur-X 1.08 Schematron
  stylesheets use XPath 2.0 constructs that `lxml`/`libxslt` (XSLT 1.0 only)
  cannot compile. `validators.py` now dispatches through
  `mcp_einvoicing_core.schematron.load_schematron_validator()` (core v1.14.0),
  which resolves these stylesheets to `SaxonSchematronValidator` (Saxon-HE via
  the optional `saxonche` extra). `validate_facturx` now returns real
  Schematron findings instead of `level="unavailable"`. Requires
  `pip install mcp-facture-electronique-fr[xslt2]` (or `mcp-einvoicing-core[xslt2]`
  directly); without it, the tool still degrades gracefully to
  `level="unavailable"`, `is_valid=None`. Same root cause as `DE-XSLT2-1`
  (ZUGFeRD), resolved once in core rather than duplicated per package. Core
  dependency bumped to `>=1.14.0`. See `context-library/audit-history.md` and
  `roadmap-2026.md`.
#### Fixed
- **FR-CDAR-MISMATCH-1 (resolved):** `flow_client._build_lifecycle_status_xml`
  previously emitted a custom `<LifecycleStatus>` shape matching no part of
  the real AFNOR CDAR schema. Rewritten to emit the actual UN/CEFACT
  `rsm:CrossDomainAcknowledgementAndResponse` document (`ExchangedDocumentContext`,
  `ExchangedDocument` with Sender/Issuer/Recipient trade parties,
  `AcknowledgementDocument`/`ReferenceReferencedDocument` with `StatusCode`/
  `ProcessConditionCode`/`ProcessCondition`, `SpecifiedDocumentStatus` for
  reasons and payment characteristics), verified field-by-field against 11
  official AFNOR worked examples under `specs/examples/cdar/` and the v1.4
  annex, plus the MDT-88/MDT-105/MDT-106 status code mapping table
  (`XP_Z12-012_Annexe_A_2026_V1.4_VF.xlsx`, sheet "CDV FE - CDAR"). The
  `submit_lifecycle_status` tool gained required party/invoice-reference
  parameters (`invoice_id`, `invoice_issue_date`, `issuer_party_*`,
  `recipient_party_*`) needed to build a structurally valid document — these
  were previously absent from the API entirely. `PartiallyApproved`'s
  `ProcessCondition` label text is `[Inference]` (pattern-matched from the
  other multi-word labels; no worked example ships one). A second
  `RecipientTradeParty` for the PPF and the optional `RequestedActionCode`/
  `IncludedNote` fields seen in one example are deliberately not modelled —
  deferred, see `context-library/roadmap-2026.md`.
#### Deferred (see `context-library/roadmap-2026.md` "FR June 2026 follow-up")
- Flux 11 (directory-service `AnnuaireConsultationF11`): data shape confirmed
  via Annex A v1.4, but no swagger endpoint was resupplied for June 2026 — no
  client method added; fabricating an unverified endpoint path was rejected.
- Credit-note prohibition, discount/charge refinement, rounding-rule
  reconciliation, and the ~44-scenario use-case catalog: confirmed doc-only —
  this CS server does not model invoice content, so no code change applies.
  See `context-library/countries/fr.md` "June 2026 substantive deltas".

### [0.5.0] - 2026-06-25
#### Added
- `FRParty.tva_intra` field with `@field_validator` calling
  `TaxIdentifier.validate_fr_tva_intra()` from core v1.9.0. Model validator
  auto-syncs `tva_intra` to `vat_id` (BT-31/BT-48) for UBL/CII emission.
- **Webhook Service** (XP Z12-013 v1.2.0): 5 new MCP tools (`list_webhooks`,
  `get_webhook`, `create_webhook`, `update_webhook`, `delete_webhook`) and
  corresponding `FlowClient` methods. Human-in-the-loop for create/delete.
- `PA_ORGANIZATION_ID` config field and `Organization-Id` header injection
  in both `FlowClient` and `DirectoryClient` for multi-tenant AP contexts
  (FR-14, XP Z12-013 v1.2.0).
- "Scope (Compatible Solution)" section in README.md and README.fr.md (FR-9/FR-10).
- Scope notes added to `submit_flow`, `validate_ereporting_xml`,
  `submit_transaction_report`, and `submit_payment_report` docstrings.
- `FR_EXTENDED_CTC_FR_PROFILE_URN` constant for the EXTENDED-CTC-FR profile
  (NF XP Z12-012 v1.3 §4.4.2).
#### Fixed
- `FR_UBL_PROFILE_URN` corrected from Peppol BIS 3.0 placeholder to
  `urn:cen.eu:en16931:2017` (NF XP Z12-012 v1.3 §4.4.2, FR-INV-1).
- Rounding mode confirmed as HALF_UP per NF XP Z12-012 v1.3 §4.4.6 (FR-INV-3).
- Removed stale `[Unverified]` markers from `wire_formats.py` and `models.py`.
- Core lower-bound bumped to `>=1.9.0,<2.0.0`.
- Audit `_INTENTIONAL_OVERRIDES` expanded for core v1.8.0/v1.9.0 symbols.
- Audit `_PKG_MODULES` and CHECK_5 imports fixed to use fully qualified paths.

### [0.4.0] - 2026-05-31
#### Added
- `FRInvoice(EN16931Invoice)` and `FRParty(EN16931Party)` in `models.py`.
  Corrects the long-standing incorrect non-EN 16931 classification; set
  `_IS_EN16931_FAMILY = True` in `audit/audit_vs_core.py`.
  **[FR-SC-1] BLOCKING resolved.**
- `FRUBLSerializer` and `FRUBLParser` extending `EN16931UBLSerializer` /
  `EN16931UBLParser` from core v1.3.0. Needed for Chorus Pro UBL 2.1
  submission and NF XP Z12-012 compliance. **[FR-CORE-1] resolved.**
- `FRCIISerializer` and `FRCIIParser` extending `EN16931CIISerializer` /
  `EN16931CIIParser`. `FRCIISerializer` injects `schemeID="urn:cen.eu:en16931:2017"`
  per Factur-X 1.0.07 §3.4. **[FR-CORE-2] resolved.**
- Core lower-bound bumped to `>=1.3.0,<2.0.0`.
#### Fixed
- YAML syntax error in `.github/workflows/publish.yml` (multi-line `python -c`
  replaced with `run: |` block scalar).

### [0.3.0] - 2026-05-21
#### Changed / Added
- **[FR-1] HIGH:** XML escaping via `xml.sax.saxutils.escape()` in
  `_build_lifecycle_status_xml`; well-formedness test added.
- **[FR-2] HIGH:** `_parse_error_body` overridden in `FlowClient` and `DirectoryClient`
  to parse `errorCode`/`errorMessage` from XP Z12-013 error bodies.
- **[FR-3] MEDIUM:** `audit/audit_vs_core.py` scaffolded; wired into `publish.yml`
  as blocking CI gate.
- **[FR-4] MEDIUM:** Interim SIREN/SIRET Luhn validators in `tools/directory_tools.py`;
  marked `[GAP id=FR-SIRET-VALIDATOR]` pending core addition.
- **[FR-5] MEDIUM:** XP Z12-013, XP Z12-012, v1.2.0 Swagger, and CDAR XML examples
  added to `specs/`; `specs/README.md` updated.
- **[FR-6]** `LifecycleStatusCode` Literal added.
- **[FR-7]** `_check_flow_not_terminal()` pre-flight helper added.
- **[FR-8]** `pa_oauth_scope` split into `pa_oauth_scope_flow` and
  `pa_oauth_scope_directory` in `PAConfig`.
- **[FR-11]** `specs/README.md` with source URL, version, and retrieval date.
- **[FR-12]** XP Z12-013 v1.1.0 → v1.2.0 delta: 5 Directory write endpoints
  tombstoned, 3 B2G processing rules added, 204 handling fixed.
- **[FR-15]** DGFiP Flux 10 e-reporting: `specs/dgfip/` populated; new tools
  `submit_transaction_report`, `submit_payment_report`, `validate_ereporting_xml`;
  36 new tests; 118 total passing; ruff clean.

### [0.2.2] - 2026-04-29
#### Changed
- Improved tool descriptions for `search_company` and `update_routing_code`:
  added Behavior, Response, and Usage Guidelines sections.

### [0.2.1] - 2026-04-29
#### Changed
- Improved tool descriptions for `search_establishment`, `search_routing_code`,
  `create_routing_code`, `search_directory_line`, and `submit_flow`: added
  explicit Behavior, Response, and Usage Guidelines sections to each docstring.

### [0.2.0] - 2026-04-19
#### Changed
- Refactored to use `mcp-einvoicing-core>=0.1.0` as base package.
  Shared utilities (`TokenCache`, `OAuthConfig`, `BaseEInvoicingClient`, logging,
  `format_error`) are now imported from the base package instead of being duplicated
  locally. `FlowClient` and `DirectoryClient` extend `BaseEInvoicingClient`.

### [0.1.3] - 2025-xx-xx
- Previous release.

---

## Notes

- The MCP registry does **not** sync automatically with PyPI or GitHub — step 3 is required for every release.
- The `server.json` description field must be **≤ 100 characters**.
- PyPI rejects re-uploads of the same version — always bump before tagging.
- GitHub Actions creates the GitHub Release automatically (with release notes) alongside the PyPI publish.
