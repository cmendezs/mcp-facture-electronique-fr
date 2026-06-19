# mcp-facture-electronique-fr 🇫🇷

[English](README.md) | [Francais](README.fr.md)

<!-- mcp-name: io.github.cmendezs/mcp-facture-electronique-fr -->

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![PyPI version](https://img.shields.io/pypi/v/mcp-facture-electronique-fr.svg)](https://pypi.org/project/mcp-facture-electronique-fr/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-facture-electronique-fr.svg)](https://pypi.org/project/mcp-facture-electronique-fr/) [![mcp-facture-electronique-fr MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-facture-electronique-fr/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-facture-electronique-fr)

Serveur MCP Python exposant les APIs standardisees **AFNOR XP Z12-013** pour la reforme de la facturation electronique francaise (entree en vigueur le 1er septembre 2026). Ce projet permet aux agents IA (Claude, IDEs) d'interagir nativement avec l'ecosysteme des Plateformes Agreees (PA/PDP) en tant que Solution Compatible (SC).

## Built on

Ce package repose sur [**mcp-einvoicing-core**](https://github.com/cmendezs/mcp-einvoicing-core), une bibliotheque de base partagee pour les serveurs MCP de facturation electronique europeens. Elle fournit le client HTTP OAuth2, le cache de jetons, les modeles partages, les utilitaires de journalisation et la hierarchie d'exceptions utilises par ce package.

`mcp-einvoicing-core` est installe automatiquement en tant que dependance transitive, aucune etape supplementaire n'est necessaire.

> **Pour les contributeurs :** `pip install -e ".[dev]"` installe automatiquement le package de base depuis PyPI.

---

## 🏗️ Architecture

Le serveur se positionne comme une interface de communication intelligente entre votre agent IA et l'infrastructure technique de la reforme :

```text
[ ERP / SI Entreprise ] <--> [ Serveur MCP ] <--> [ Plateforme Agreee (PA/PDP) ]
          ^                        |
          |                        v
   [ Agent IA (Claude) ] <--- (Standard XP Z12-013)
```

## 🛠️ Services exposes

| Service | Domaine | Norme | Outils MCP |
|---------|---------|-------|------------|
| **Flow Service** | Flux de factures et e-reporting | Annexe A, v1.1.0 | 5 outils |
| **Directory Service** | Annuaire centralise (SIREN/SIRET) | Annexe B, v1.1.0 | 12 outils |

## 🚀 Installation

### Via PyPI (recommande)

```bash
pip install mcp-facture-electronique-fr
```

Ou sans installation prealable avec `uvx` :

```bash
uvx mcp-facture-electronique-fr
```

### Depuis les sources

```bash
# Cloner le depot
git clone https://github.com/cmendezs/mcp-facture-electronique-fr.git
cd mcp-facture-electronique-fr

# Creer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows : .venv\Scripts\activate

# Installation en mode editable
pip install -e ".[dev]"
```

```bash
# Configuration initiale
cp .env.example .env
# Editer .env avec vos credentials fournis par votre PA/PDP
```

## ⚙️ Configuration (.env)

Le serveur necessite les variables suivantes pour s'authentifier aupres d'une Plateforme Agreee (PA) :

| Variable | Description |
|----------|-------------|
| `PA_BASE_URL_FLOW` | URL de base du Flow Service de la PA |
| `PA_BASE_URL_DIRECTORY` | URL de base du Directory Service de la PA |
| `PA_CLIENT_ID` | Client ID OAuth2 |
| `PA_CLIENT_SECRET` | Client Secret OAuth2 |
| `PA_TOKEN_URL` | URL du serveur d'authentification |
| `HTTP_TIMEOUT` | Timeout des requetes (defaut : 30s) |

## 🤖 Integration Claude Desktop

Pour utiliser ce serveur avec Claude, ajoutez cette configuration dans votre fichier `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "uvx",
      "args": ["mcp-facture-electronique-fr"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.votre-pdp.fr/flow",
        "PA_BASE_URL_DIRECTORY": "https://api.votre-pdp.fr/directory",
        "PA_CLIENT_ID": "votre-id",
        "PA_CLIENT_SECRET": "votre-secret",
        "PA_TOKEN_URL": "https://auth.votre-pdp.fr/oauth/token"
      }
    }
  }
}
```

## ⌨️ Integration Cursor

Cursor supporte les serveurs MCP en stdio. Ajoutez la configuration dans :
- **Global** (tous les projets) : `~/.cursor/mcp.json`
- **Projet** (ce depot uniquement) : `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "uvx",
      "args": ["mcp-facture-electronique-fr"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.votre-pdp.fr/flow",
        "PA_BASE_URL_DIRECTORY": "https://api.votre-pdp.fr/directory",
        "PA_CLIENT_ID": "votre-id",
        "PA_CLIENT_SECRET": "votre-secret",
        "PA_TOKEN_URL": "https://auth.votre-pdp.fr/oauth/token"
      }
    }
  }
}
```

Rechargez la fenetre Cursor (`Ctrl+Shift+P` puis *Reload Window*) pour prendre en compte les changements.

## 🪐 Integration Kiro

Kiro supporte les serveurs MCP via son fichier de configuration dedie. Deux niveaux disponibles :
- **Global** (tous les projets) : `~/.kiro/settings/mcp.json`
- **Workspace** (ce depot uniquement) : `.kiro/settings/mcp.json`

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "uvx",
      "args": ["mcp-facture-electronique-fr"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.votre-pdp.fr/flow",
        "PA_BASE_URL_DIRECTORY": "https://api.votre-pdp.fr/directory",
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

Le fichier est recharge automatiquement a la sauvegarde. Vous pouvez egalement ouvrir la config via la palette de commandes (`Cmd+Shift+P` / `Ctrl+Shift+P`) puis *MCP*.

> **Conseil securite Kiro** : plutot que d'ecrire les secrets en clair, utilisez la syntaxe `"PA_CLIENT_SECRET": "${PA_CLIENT_SECRET}"`, Kiro resout les variables d'environnement shell au demarrage.

## 🧰 Outils MCP disponibles

### Flow Service (Gestion des flux)
* `submit_flow` : Envoi de factures (**Factur-X**, **UBL**, **CII**) ou donnees d'e-reporting.
* `search_flows` : Recherche multicriteres de flux emis ou recus selon les filtres de la norme.
* `submit_lifecycle_status` : Mise a jour du statut du cycle de vie (ex: Mise a disposition, Encaissee, Litige).
* `get_flow` : Recuperation du detail complet et des pieces jointes d'un flux specifique.
* `healthcheck_flow` : Test de connectivite et de disponibilite de l'API Flow de la PA.

### Directory Service (Annuaire)
* `get_company_by_siren` / `get_establishment_by_siret` : Consultation des fiches entreprises et etablissements dans l'annuaire central.
* `search_routing_code` : Identification du code plateforme (adresse de routage) d'un destinataire pour l'emission des factures.
* `manage_directory_line` : Creation, modification et suppression des lignes d'annuaire pour la gestion des services de l'assujetti.

## 📚 References reglementaires
- **AFNOR XP Z12-013** : Specifications des interfaces de services (version fevrier 2026).
- **AFNOR XP Z12-014** : Guide d'implementation technique des cas d'usage metier.
- **Reforme B2B France** : Calendrier de deploiement obligatoire (2024-2026).

## 🧪 Tests

```bash
# Lancer la suite de tests unitaires et d'integration
pytest tests/ -v
```

## Other e-invoicing MCP servers

| Country | Server |
|---------|--------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgium | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brazil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Germany | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italy | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Poland | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Spain | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

## 📄 Licence

Ce projet est distribue sous licence **Apache 2.0**. Voir le fichier [LICENSE](LICENSE) pour plus de details.

---
*Projet maintenu par cmendezs. Pour toute question relative a l'implementation de la norme XP Z12-013, n'hesitez pas a ouvrir une Issue.*
