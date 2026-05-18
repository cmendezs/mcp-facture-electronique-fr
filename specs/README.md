# mcp-facture-electronique-fr — Specification assets

Reference files for the AFNOR XP Z12-013 Compatible Solution (CS) integration.

**Copyright notice:** The AFNOR PDF files below (FA300082, FA300084) are protected by
AFNOR copyright. AFNOR expressly prohibits their integration, transmission, or absorption
by AI engines or algorithms, and any text and data mining or AI-derived creation based on
these documents. They are stored here as reference assets for human review only.

---

## XP Z12-013 — Compatible Solution interface (CS layer)

XP Z12-013 (February 2026) defines the API for interfacing company information systems
with Approved Platforms (PDPs). This is the normative specification that the CS server
implements.

| File | Standard | Version | Source | Retrieved |
|---|---|---|---|---|
| `XP_Z12-013_2026-02_FR.pdf` | XP Z12-013 normative text (French) | 2026-02 | AFNOR boutique (FA300084) | 2026-05-18 |
| `ANNEXE A - XP Z12-013 - Flow_Service-1.2.0-swagger-resolved.json` | XP Z12-013 Annex A — Flow Service OpenAPI | **1.2.0** | AFNOR boutique (FA300084) | 2026-05-18 |
| `ANNEXE B - XP Z12-013 - Directory_Service-1.2.0-swagger-resolved.json` | XP Z12-013 Annex B — Directory Service OpenAPI | **1.2.0** | AFNOR boutique (FA300084) | 2026-05-18 |

### Version history — kept for reference

The server (`v0.2.2`) was built against the earlier **v1.1.0 PR** (draft) Swagger files.
Those files are retained here until the server is updated for v1.2.0 compatibility.

| File | Standard | Version | Notes |
|---|---|---|---|
| `ANNEXE A - PR XP Z12-013 - AFNOR-Flow_Service-1.1.0-swagger.json` | XP Z12-013 Annex A — Flow Service OpenAPI | 1.1.0 PR (draft) | Superseded by v1.2.0; server currently implements this version |
| `ANNEXE B - PR XP Z12-013 - AFNOR-Directory_Service-1.1.0-swagger.json` | XP Z12-013 Annex B — Directory Service OpenAPI | 1.1.0 PR (draft) | Superseded by v1.2.0; server currently implements this version |

> **Resolved (v0.2.2):** The v1.1.0 PR → v1.2.0 delta has been audited and applied.
> Breaking changes implemented: 5 Directory write endpoints tombstoned (NotImplementedError),
> 4 id-instance GET endpoints removed, 3 B2G processing rules added, 204 handling added to
> all search routes. See audit/2026-05-audit-fr.md finding FR-12 for details.

---

## XP Z12-012 — Invoice message formats, profiles, and lifecycle statuses

XP Z12-012 (February 2026) defines the minimum invoice format requirements for the French
electronic invoicing reform. XP Z12-013 references XP Z12-012 for the message formats that
callers must submit to the CS server.

| File | Standard | Version | Source | Retrieved |
|---|---|---|---|---|
| `XP_Z12-012_2026-02_FR.pdf` | XP Z12-012 normative text (French) | 2026-02 | AFNOR boutique (FA300082) | 2026-05-18 |
| `XP_Z12-012_V1.3_ENG_formats_profiles.pdf` | XP Z12-012 English summary — formats and profiles | V1.3 | AFNOR boutique (FA300082) | 2026-05-18 |
| `XP_Z12-012_Annexe_A_V1.3_profiles.xlsx` | XP Z12-012 Annex A — profile mapping spreadsheet | V1.3 | AFNOR boutique (FA300082) | 2026-05-18 |
| `XP_Z12-012_Annexe_B_V1.3_exemples_FR.pdf` | XP Z12-012 Annex B — use-case examples (French) | V1.3 | AFNOR boutique (FA300082) | 2026-05-18 |
| `XP_Z12-012_Annex_B_V1.3_examples_ENG.pdf` | XP Z12-012 Annex B — use-case examples (English) | V1.3 | AFNOR boutique (FA300082) | 2026-05-18 |

---

## XP Z12-014 — Lifecycle use-case annex

XP Z12-014 defines the lifecycle status (CDAR) XML format built by `_build_lifecycle_status_xml`
in `clients/flow_client.py`.

| File | Standard | Version | Source | Retrieved |
|---|---|---|---|---|
| `XP_Z12-014_CAS_USAGE_Annexe_A_V1.2.pdf` | XP Z12-014 Annex A — Lifecycle use-case annex | V1.2 | AFNOR / DGFiP developer portal | 2026-05-18 |

---

## CDAR lifecycle status examples (`examples/cdar/`)

Official XP Z12-012 Annex B example CDAR XML documents. These are reference files for
human review; they must not be used as test fixtures directly (untrusted-content rule in
`sub-agents/mcp-audit-fr.md`).

| File | CDV code | Status description |
|---|---|---|
| `UC1_F202500003_01-CDV-200_Deposee.xml` | CDV-200 | Déposée — flow deposited |
| `UC1_F202500003_01-CDV-200_Deposee_POUR_PPF.xml` | CDV-200 | Déposée — PPF transmission variant |
| `UC1_F202500003_02-CDV-202_Recue.xml` | CDV-202 | Reçue — received by recipient's AP |
| `UC1_F202500003_03-CDV-203_Mise_a_disposition.xml` | CDV-203 | Mise à disposition — made available |
| `UC1_F202500003_04-CDV-204_Prise_en_charge.xml` | CDV-204 | Prise en charge — taken into processing |
| `UC1_F202500003_05-CDV-205_Approuvee.xml` | CDV-205 | Approuvée — Approved |
| `UC1_F202500003_06-CDV-211_Paiement_transmis.xml` | CDV-211 | Paiement transmis — PaymentTransmitted |
| `UC1_F202500003_07-CDV-212_Encaissee.xml` | CDV-212 | Encaissée — Cashed |
| `UC1_F202500003_07-CDV-212_Encaissee_POUR_PPF.xml` | CDV-212 | Encaissée — PPF transmission variant |
| `UC4_F202500006_04-CDV-207_En_litige.xml` | CDV-207 | En litige — Disputed (with reason) |
| `UC5_F202500007_04-CDV-207_En_litige.xml` | CDV-207 | En litige — Disputed (alternate use case) |

---

## Factur-X 1.08 — XSD, Schematron, and XSLT (`facturx/`)

Factur-X 1.08 / ZUGFeRD 2.4 final release (December 4, 2025). Source: FNFE-MPE.
No AFNOR copyright restriction — freely distributable.

| File / Directory | Contents | Version |
|---|---|---|
| `facturx/Factur-X_1.08_EN.pdf` | Full Factur-X 1.08 specification (English) | 1.08 |
| `facturx/Factur-X_1.08_field_mapping_ENFR.xlsx` | Semantic field mapping EN/FR | 1.08 |
| `facturx/MINIMUM/` | MINIMUM profile — XSD (3 files), Schematron (.sch), codedb.xml, XSLT/ | 1.08 |
| `facturx/BASICWL/` | BASIC WL profile — XSD (3 files), Schematron (.sch), codedb.xml, XSLT/ | 1.08 |
| `facturx/BASIC/` | BASIC profile — XSD (3 files), Schematron (.sch), codedb.xml, XSLT/ | 1.08 |
| `facturx/EN16931/` | EN 16931 (COMFORT) profile — XSD (3 files), Schematron (.sch), codedb.xml, XSLT/ | 1.08 |
| `facturx/EXTENDED/` | EXTENDED profile — XSD (3 files), Schematron (.sch), codedb.xml, XSLT/ | 1.08 |
| `facturx/XSD_CII_D22B/` | Base UN/CEFACT CII D22B XSDs (65 files) — imported by all profile XSDs | D22B |
| `facturx/appendices/` | Per-profile technical appendices (5 PDFs: MINIMUM, BASIC WL, BASIC, EN 16931, EXTENDED) | 1.08 |

**Per-profile entry XSD names** (used by a future `validate_facturx` tool):

| Profile | Entry XSD | Schematron |
|---|---|---|
| MINIMUM | `facturx/MINIMUM/Factur-X_1.08_MINIMUM.xsd` | `Factur-X_1.08_MINIMUM.sch` |
| BASIC WL | `facturx/BASICWL/Factur-X_1.08_BASICWL.xsd` | `Factur-X_1.08_BASICWL.sch` |
| BASIC | `facturx/BASIC/Factur-X_1.08_BASIC.xsd` | `Factur-X_1.08_BASIC.sch` |
| EN 16931 | `facturx/EN16931/Factur-X_1.08_EN16931.xsd` | `Factur-X_1.08_EN16931.sch` |
| EXTENDED | `facturx/EXTENDED/Factur-X_1.08_EXTENDED.xsd` | `Factur-X_1.08_EXTENDED.sch` |

Retrieved: 2026-05-18

---

## DGFiP Spécifications Externes v3.2 — E-reporting Flux 10 (`dgfip/`)

Official DGFiP specification bundle for the French electronic invoicing reform.
Version 3.2, published 30/04/2026. Source: impots.gouv.fr (B2B e-invoicing page).
No AFNOR copyright restriction on DGFiP material.

**E-reporting covers:**
- Flux 10.1 — `IndividualCustomerTransactionReport`: individual B2C / international B2B transactions
- Flux 10.2 — `UnitaryCustomerPaymentReport`: individual payment data for B2C / intl B2B invoices
- Flux 10.3 — `AggregatedCustomerTransactionReport`: aggregated B2C transactions
- Flux 10.4 — `AggregatedCustomerPaymentReport`: aggregated B2C payment data

### XSD schemas (`dgfip/xsd/`)

These schemas are loaded at runtime by `validate_ereporting_xml` and used by the XML builders
in `tools/ereporting_tools.py`.

| File | Contents | Namespace |
|---|---|---|
| `ereporting.xsd` | Root schema — `<Report>` root element | (none) |
| `report.xsd` | `ReportDocumentType` — transmission header (TT-1 to TT-16) | `report` |
| `transaction.xsd` | `TransactionsReportType` — Flux 10.1/10.3 invoice data (TT-17 to TT-88+) | `transaction` |
| `payment.xsd` | `PaymentsReportType` — Flux 10.2/10.4 payment data (TT-89 to TT-99) | `payment` |
| `parametre.xsd` | Simple type definitions (string ID types) | `parametre` |
| `Changelog_XSD.md` | XSD change log (v3.0 to v3.2 delta) | — |

Retrieved: 2026-05-18

### Annexes (`dgfip/annexes/`)

| File | Contents |
|---|---|
| `20260430_Annexe 6 - Format sémantique FE e-reporting - V1.10.xlsx` | Data dictionary for all Flux 10 fields (TT-* codes, xpath mapping, cardinality, code lists) |
| `20260430_Annexe 7 - Règles de gestion - V1.9.xlsx` | Business rules and validation logic (conditional field rules, error codes REJ_SEMAN, REJ_COH, etc.) |

### Documentation (`dgfip/docs/`)

| File | Contents |
|---|---|
| `0- Dossier de specifications externes FE - Dossier général_v3.2.pdf` | Master technical specification — transmission periodicity, Flux 10 packaging (tar.gz/USTAR), API overview |
| `1- Dossier de spécifications externes FE - Chorus Pro_v1.1.pdf` | Chorus Pro (DFH / public-sector invoicing) integration specification |

### PPF Annuaire Swagger (`dgfip/swagger/`)

| File | Contents |
|---|---|
| `ppf-openapi-annuaire-api-public-1.11.0-openapi.json` | PPF Annuaire (directory) REST API — endpoints for SIREN/SIRET lookup and directory-line management via the PPF portal |

---

## Still missing

| Asset | Standard | Notes |
|---|---|---|
| DGFiP e-invoicing XSDs (F1_BASE / F1_FULL) | DGFiP Spécifications Externes v3.2 | CII D22B and UBL 2.1 schemas restricted to French BASE and FULL profiles. Available in the DGFiP v3.2 ZIP; not copied here (these XSDs are for invoice validation, not e-reporting). |

---

## Update process

When AFNOR or DGFiP publishes a new version of any spec file:
1. Download the new file from the official source.
2. Add it here and update the Version and Retrieved columns in the relevant table.
3. Move the superseded file to the "Version history" section (or delete once the server
   has been updated to the new version).
4. Update any version constants in `clients/flow_client.py` or `clients/directory_client.py`.
5. Run the test suite to verify no regressions.
