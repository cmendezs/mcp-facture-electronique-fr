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
