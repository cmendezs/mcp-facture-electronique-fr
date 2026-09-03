# mcp-facture-electronique-fr 🇫🇷

[English](README.md) | [Francais](README.fr.md)

<!-- mcp-name: io.github.cmendezs/mcp-facture-electronique-fr -->

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![PyPI version](https://img.shields.io/pypi/v/mcp-facture-electronique-fr.svg)](https://pypi.org/project/mcp-facture-electronique-fr/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-facture-electronique-fr.svg)](https://pypi.org/project/mcp-facture-electronique-fr/) [![mcp-facture-electronique-fr MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-facture-electronique-fr/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-facture-electronique-fr)

A Python MCP server exposing the standardized **AFNOR XP Z12-013** APIs for the French e-invoicing reform (effective September 1, 2026). This project enables AI agents (Claude, IDEs) to interact natively with the Approved Platform (PA/PDP) ecosystem as a Compatible Solution (SC).

---

## Introduction

This package is built on top of [**mcp-einvoicing-core**](https://github.com/cmendezs/mcp-einvoicing-core), a shared base library for European e-invoicing MCP servers. It provides the OAuth2 HTTP client, token cache, shared models, logging utilities, and exception hierarchy used by this package.

`mcp-einvoicing-core` is installed automatically as a transitive dependency, no extra step is needed.

> **For contributors:** `pip install -e ".[dev]"` installs the base package from PyPI automatically.

This server operates in **Compatible Solution (CS)** mode as defined by the French e-invoicing reform. The CS acts as an intermediary between the company's information system and an Approved Platform (AP/PDP). This means:

- **No profile validation of caller-supplied payloads.** The server transmits the invoice file (Factur-X PDF/A-3, UBL 2.1, or CII XML) as provided. Structural and business-rule validation (NF XP Z12-012 profiles, Schematron rules) is performed by the receiving Approved Platform, not by this server.
- **No e-reporting payload validation beyond schema-level XSD.** Transaction reports (Flux 10.1/10.3) and payment reports (Flux 10.2/10.4) are validated against the DGFiP v3.2 XSD schema when `validate_ereporting_xml` is called, but deeper business-rule checks (e.g. coherence between declared amounts and invoice totals) are the responsibility of the AP.
- **No PDF/A-3 envelope generation.** The caller must produce the conformant Factur-X PDF/A-3 file with embedded CII XML. This server transmits the finished binary.

The Approved Platform performs final validation and may reject non-conformant submissions with an error code and message.

## Installation

### Via PyPI (recommended)

```bash
pip install mcp-facture-electronique-fr
```

Or without prior installation using `uvx`:

```bash
uvx mcp-facture-electronique-fr
```

For Factur-X Schematron validation (`validate_facturx`, requires the XSLT 2.0 /
Saxon-HE backend — see FR-XSLT2-1 in Available tools below):

```bash
pip install mcp-facture-electronique-fr[xslt2]
```

### From source

```bash
# Clone the repository
git clone https://github.com/cmendezs/mcp-facture-electronique-fr.git
cd mcp-facture-electronique-fr

# Create the virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e ".[dev]"
```

```bash
# Initial configuration
cp .env.example .env
# Edit .env with the credentials provided by your PA/PDP
```

## Configuration (.env)

The server requires the following variables to authenticate with an Approved Platform (PA):

| Variable | Description |
|----------|-------------|
| `PA_BASE_URL_FLOW` | Base URL of the PA Flow Service |
| `PA_BASE_URL_DIRECTORY` | Deprecated — no longer read; see `PPF_ANNUAIRE_BASE_URL` |
| `PPF_ANNUAIRE_BASE_URL` | Base URL of the PPF Annuaire service (defaults to the production swagger `servers` URL; override for sandbox testing) |
| `PA_CLIENT_ID` | OAuth2 Client ID |
| `PA_CLIENT_SECRET` | OAuth2 Client Secret |
| `PA_TOKEN_URL` | Authentication server URL |
| `PA_ORGANIZATION_ID` | Organization identifier for multi-tenant AP (optional) |
| `HTTP_TIMEOUT` | Request timeout (default: 30s) |
| `PPF_GLOBAL_ID` | PPF party GlobalID for the CDAR second `RecipientTradeParty` (optional; unset by default, see `submit_lifecycle_status`) |
| `PPF_SCHEME_ID` | schemeID for `PPF_GLOBAL_ID` (default `0238`) |
| `PPF_NAME` | Name for the PPF `RecipientTradeParty` (default `PPF`) |
| `PPF_ROLE_CODE` | RoleCode for the PPF `RecipientTradeParty` (default `DFH`) |

## Claude Desktop integration

To use this server with Claude, add this configuration to your `claude_desktop_config.json` file:

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "uvx",
      "args": ["mcp-facture-electronique-fr"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.votre-pdp.fr/flow",
        "PPF_ANNUAIRE_BASE_URL": "https://aife.economie.gouv.fr/ppf/annuaire-public/v1",
        "PA_CLIENT_ID": "votre-id",
        "PA_CLIENT_SECRET": "votre-secret",
        "PA_TOKEN_URL": "https://auth.votre-pdp.fr/oauth/token"
      }
    }
  }
}
```

## Cursor integration

Cursor supports MCP servers via stdio. Add the configuration in:
- **Global** (all projects): `~/.cursor/mcp.json`
- **Project** (this repository only): `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "uvx",
      "args": ["mcp-facture-electronique-fr"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.votre-pdp.fr/flow",
        "PPF_ANNUAIRE_BASE_URL": "https://aife.economie.gouv.fr/ppf/annuaire-public/v1",
        "PA_CLIENT_ID": "votre-id",
        "PA_CLIENT_SECRET": "votre-secret",
        "PA_TOKEN_URL": "https://auth.votre-pdp.fr/oauth/token"
      }
    }
  }
}
```

Reload the Cursor window (`Ctrl+Shift+P` then *Reload Window*) to apply the changes.

## Kiro integration

Kiro supports MCP servers via its dedicated configuration file. Two levels are available:
- **Global** (all projects): `~/.kiro/settings/mcp.json`
- **Workspace** (this repository only): `.kiro/settings/mcp.json`

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "uvx",
      "args": ["mcp-facture-electronique-fr"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.votre-pdp.fr/flow",
        "PPF_ANNUAIRE_BASE_URL": "https://aife.economie.gouv.fr/ppf/annuaire-public/v1",
        "PA_CLIENT_ID": "votre-id",
        "PA_CLIENT_SECRET": "votre-secret",
        "PA_TOKEN_URL": "https://auth.votre-pdp.fr/oauth/token"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

The file is automatically reloaded on save. You can also open the config via the command palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) then *MCP*.

> **Kiro security tip**: rather than writing secrets in plain text, use the syntax `"PA_CLIENT_SECRET": "${PA_CLIENT_SECRET}"`, Kiro resolves shell environment variables at startup.

## Available tools

| Service | Domain | Standard | MCP Tools |
|---------|--------|----------|-----------|
| **Flow Service** | Invoice flows and e-reporting | Annex A, v1.2.0 | 5 tools |
| **PPF Annuaire (directory)** | Central directory (SIREN/SIRET/routing/addressing) | PPF swagger v1.11.0 | 20 tools |
| **Webhook Service** | Event notification subscriptions | Annex A, v1.2.0 | 5 tools |
| **Factur-X Service** | CII XML validation (Schematron) | Factur-X 1.09.2 | 1 tool |

> Text bumped to June 2026 (v1.2.0 swagger current) — AFNOR resupplied the XP Z12-013
> narrative text in June 2026 without an updated swagger; the server continues to
> implement the v1.2.0 wire contract.

> **Note (FR-XSLT2-1, resolved):** the bundled Factur-X 1.09.2 Schematron
> stylesheets require XSLT 2.0, which `lxml`/`libxslt` (XSLT 1.0 only) cannot
> compile — the same root cause as the `DE-XSLT2-1` gap tracked for ZUGFeRD.
> `validate_facturx` now runs real Schematron validation via Saxon-HE. Install
> the optional `xslt2` extra for this to work:
> `pip install mcp-facture-electronique-fr[xslt2]`. Without it, the tool
> degrades gracefully to `level="unavailable"`.

> **Note (FR-FLUX11-2026-06, PPF Annuaire):** the directory tools are wired
> directly against the bundled PPF-platform swagger
> `ppf-openapi-annuaire-api-public-1.11.0-openapi.json` — this is a
> **PPF-platform-specific** interface, not a PDP-agnostic Annex B abstraction.
> Per the swagger's own description, these endpoints are subject to change and
> require prior PISTE application publication before use.

### Flow Service (Flow management)
* `submit_flow`: Submit invoices (**Factur-X**, **UBL**, **CII**) or e-reporting data.
* `search_flows`: Multi-criteria search of sent or received flows using the standard filters.
* `submit_lifecycle_status`: Update the lifecycle status (e.g., Made available, Collected, Dispute).
* `get_flow`: Retrieve the full details and attachments of a specific flow.
* `healthcheck_flow`: Test the connectivity and availability of the PA Flow API.

### PPF Annuaire (directory)
Wired directly against the bundled PPF-platform swagger
`ppf-openapi-annuaire-api-public-1.11.0-openapi.json` — see the note above.
* `search_company` / `get_company_by_siren` / `get_company_by_id_instance`: Look up legal units (SIREN).
* `search_establishment` / `get_establishment_by_siret` / `get_establishment_by_id_instance`: Look up establishments (SIRET).
* `search_routing_code` / `get_routing_code_by_siret_and_code` / `get_routing_code_by_id_instance` / `create_routing_code` / `update_routing_code` / `replace_routing_code`: Manage routing codes (code-routage).
* `search_directory_line` / `get_directory_line_by_code` / `get_directory_line` / `create_directory_line` / `update_directory_line` / `replace_directory_line` / `delete_directory_line`: Manage directory lines (ligne-annuaire), the electronic-invoice receiving addresses.
* `check_ppf_annuaire_health`: Check availability of the PPF Annuaire service.

### Webhook Service (Webhook management)
* `list_webhooks`: List all webhook subscription IDs for the current token holder.
* `get_webhook`: Retrieve the full details of a webhook subscription.
* `create_webhook`: Subscribe to flow event notifications (filter by flow type, direction, processing rule).
* `update_webhook`: Update a webhook's technical parameters (authentication, signature).
* `delete_webhook`: Unsubscribe from a webhook.

## Architecture

The server acts as an intelligent communication interface between your AI agent and the technical infrastructure of the reform:

```text
[ ERP / Business IS ] <--> [ MCP Server ] <--> [ Approved Platform (PA/PDP) ]
          ^                        |
          |                        v
   [ AI Agent (Claude) ] <--- (XP Z12-013 Standard)
```

## Supported standards

- **AFNOR XP Z12-012**: Invoice message formats, profiles, and lifecycle statuses (v1.4, June 2026 edition).
- **AFNOR XP Z12-013**: Service interface specifications (June 2026 edition; v1.2.0 wire contract).
- **AFNOR XP Z12-014**: Technical implementation guide for business use cases (v1.4, June 2026 edition).
- **France B2B reform**: Mandatory rollout schedule (2024-2026).

## Tests

```bash
# Run the unit and integration test suite
pytest tests/ -v
```

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Other e-invoicing MCP servers

| Country | Server |
|---------|--------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgium | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brazil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Germany | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italy | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇲🇽 Mexico | [mcp-cfdi-mx](https://github.com/cmendezs/mcp-cfdi-mx) |
| 🇵🇱 Poland | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇸🇬 Singapore | [mcp-invoicenow-sg](https://github.com/cmendezs/mcp-invoicenow-sg) |
| 🇪🇸 Spain | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |
| 🇦🇪 United Arab Emirates | [mcp-einvoicing-ae](https://github.com/cmendezs/mcp-einvoicing-ae) |

## License

This project is distributed under the **Apache 2.0** license. See the [LICENSE](LICENSE) file for details. For the full version history, see [CHANGELOG.md](CHANGELOG.md).
