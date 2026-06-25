# mcp-facture-electronique-fr 🇫🇷

[English](README.md) | [Français](README.fr.md)

<!-- mcp-name: io.github.cmendezs/mcp-facture-electronique-fr -->

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
[![PyPI version](https://img.shields.io/pypi/v/mcp-facture-electronique-fr.svg)](https://pypi.org/project/mcp-facture-electronique-fr/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-facture-electronique-fr.svg)](https://pypi.org/project/mcp-facture-electronique-fr/) [![mcp-facture-electronique-fr MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-facture-electronique-fr/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-facture-electronique-fr)

Serveur MCP Python exposant les APIs standardisées **AFNOR XP Z12-013** pour la réforme de la facturation électronique française (entrée en vigueur le 1er septembre 2026). Ce projet permet aux agents IA (Claude, IDEs) d'interagir nativement avec l'écosystème des Plateformes Agréées (PA/PDP) en tant que Solution Compatible (SC).

## Construit sur

Ce package repose sur [**mcp-einvoicing-core**](https://github.com/cmendezs/mcp-einvoicing-core), une bibliothèque de base partagée pour les serveurs MCP de facturation électronique européens. Elle fournit le client HTTP OAuth2, le cache de jetons, les modèles partagés, les utilitaires de journalisation et la hiérarchie d'exceptions utilisés par ce package.

`mcp-einvoicing-core` est installé automatiquement en tant que dépendance transitive, aucune étape supplémentaire n'est nécessaire.

> **Pour les contributeurs :** `pip install -e ".[dev]"` installe automatiquement le package de base depuis PyPI.

---

## Périmètre (Solution Compatible)

Ce serveur fonctionne en mode **Solution Compatible (SC)** tel que défini par la réforme de la facturation électronique française. La SC agit comme intermédiaire entre le système d'information de l'entreprise et une Plateforme Agréée (PA/PDP). Cela signifie :

- **Pas de validation de profil des données transmises.** Le serveur transmet le fichier facture (Factur-X PDF/A-3, UBL 2.1 ou CII XML) tel quel. La validation structurelle et des règles métier (profils NF XP Z12-012, règles Schematron) est effectuée par la Plateforme Agréée réceptrice, pas par ce serveur.
- **Pas de validation des données de e-reporting au-delà du XSD.** Les déclarations de transactions (Flux 10.1/10.3) et de paiements (Flux 10.2/10.4) sont validées contre le schéma XSD DGFiP v3.2 lorsque `validate_ereporting_xml` est appelé, mais les contrôles métier approfondis (ex. cohérence entre montants déclarés et totaux de facture) relèvent de la PA.
- **Pas de génération d'enveloppe PDF/A-3.** L'appelant doit produire le fichier Factur-X PDF/A-3 conforme avec le XML CII embarqué. Ce serveur transmet le binaire finalisé.

La Plateforme Agréée effectue la validation finale et peut rejeter les soumissions non conformes avec un code et un message d'erreur.

---

## 🏗️ Architecture

Le serveur se positionne comme une interface de communication intelligente entre votre agent IA et l'infrastructure technique de la réforme :

```text
[ ERP / SI Entreprise ] <--> [ Serveur MCP ] <--> [ Plateforme Agréée (PA/PDP) ]
          ^                        |
          |                        v
   [ Agent IA (Claude) ] <--- (Standard XP Z12-013)
```

## 🛠️ Services exposés

| Service | Domaine | Norme | Outils MCP |
|---------|---------|-------|------------|
| **Flow Service** | Flux de factures et e-reporting | Annexe A, v1.2.0 | 5 outils |
| **Directory Service** | Annuaire centralisé (SIREN/SIRET) | Annexe B, v1.2.0 | 12 outils |
| **Webhook Service** | Abonnements aux notifications | Annexe A, v1.2.0 | 5 outils |

## 🚀 Installation

### Via PyPI (recommandé)

```bash
pip install mcp-facture-electronique-fr
```

Ou sans installation préalable avec `uvx` :

```bash
uvx mcp-facture-electronique-fr
```

### Depuis les sources

```bash
# Cloner le dépôt
git clone https://github.com/cmendezs/mcp-facture-electronique-fr.git
cd mcp-facture-electronique-fr

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows : .venv\Scripts\activate

# Installation en mode éditable
pip install -e ".[dev]"
```

```bash
# Configuration initiale
cp .env.example .env
# Éditer .env avec vos credentials fournis par votre PA/PDP
```

## ⚙️ Configuration (.env)

Le serveur nécessite les variables suivantes pour s'authentifier auprès d'une Plateforme Agréée (PA) :

| Variable | Description |
|----------|-------------|
| `PA_BASE_URL_FLOW` | URL de base du Flow Service de la PA |
| `PA_BASE_URL_DIRECTORY` | URL de base du Directory Service de la PA |
| `PA_CLIENT_ID` | Client ID OAuth2 |
| `PA_CLIENT_SECRET` | Client Secret OAuth2 |
| `PA_TOKEN_URL` | URL du serveur d'authentification |
| `PA_ORGANIZATION_ID` | Identifiant d'organisation pour PA multi-tenant (optionnel) |
| `HTTP_TIMEOUT` | Timeout des requêtes (défaut : 30s) |

## 🤖 Intégration Claude Desktop

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

## ⌨️ Intégration Cursor

Cursor supporte les serveurs MCP en stdio. Ajoutez la configuration dans :
- **Global** (tous les projets) : `~/.cursor/mcp.json`
- **Projet** (ce dépôt uniquement) : `.cursor/mcp.json`

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

Rechargez la fenêtre Cursor (`Ctrl+Shift+P` puis *Reload Window*) pour prendre en compte les changements.

## 🪐 Intégration Kiro

Kiro supporte les serveurs MCP via son fichier de configuration dédié. Deux niveaux disponibles :
- **Global** (tous les projets) : `~/.kiro/settings/mcp.json`
- **Workspace** (ce dépôt uniquement) : `.kiro/settings/mcp.json`

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

Le fichier est rechargé automatiquement à la sauvegarde. Vous pouvez également ouvrir la configuration via la palette de commandes (`Cmd+Shift+P` / `Ctrl+Shift+P`) puis *MCP*.

> **Conseil sécurité Kiro** : plutôt que d'écrire les secrets en clair, utilisez la syntaxe `"PA_CLIENT_SECRET": "${PA_CLIENT_SECRET}"`, Kiro résout les variables d'environnement shell au démarrage.

## 🧰 Outils MCP disponibles

### Flow Service (Gestion des flux)
* `submit_flow` : Envoi de factures (**Factur-X**, **UBL**, **CII**) ou données d'e-reporting.
* `search_flows` : Recherche multicritères de flux émis ou reçus selon les filtres de la norme.
* `submit_lifecycle_status` : Mise à jour du statut du cycle de vie (ex: Mise à disposition, Encaissée, Litige).
* `get_flow` : Récupération du détail complet et des pièces jointes d'un flux spécifique.
* `healthcheck_flow` : Test de connectivité et de disponibilité de l'API Flow de la PA.

### Directory Service (Annuaire)
* `get_company_by_siren` / `get_establishment_by_siret` : Consultation des fiches entreprises et établissements dans l'annuaire central.
* `search_routing_code` : Identification du code plateforme (adresse de routage) d'un destinataire pour l'émission des factures.
* `manage_directory_line` : Création, modification et suppression des lignes d'annuaire pour la gestion des services de l'assujetti.

### Webhook Service (Gestion des webhooks)
* `list_webhooks` : Liste de tous les identifiants d'abonnements webhook.
* `get_webhook` : Récupération des détails complets d'un abonnement webhook.
* `create_webhook` : Abonnement aux notifications de flux (filtre par type, direction, règle de traitement).
* `update_webhook` : Mise à jour des paramètres techniques d'un webhook (authentification, signature).
* `delete_webhook` : Désabonnement d'un webhook.

## 📚 Références réglementaires
- **AFNOR XP Z12-013** : Spécifications des interfaces de services (version février 2026).
- **AFNOR XP Z12-014** : Guide d'implémentation technique des cas d'usage métier.
- **Réforme B2B France** : Calendrier de déploiement obligatoire (2024-2026).

## 🧪 Tests

```bash
# Lancer la suite de tests unitaires et d'intégration
pytest tests/ -v
```

## Autres serveurs MCP de facturation électronique

| Pays | Serveur |
|------|---------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgique | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brésil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Allemagne | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italie | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Pologne | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Espagne | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

## 📄 Licence

Ce projet est distribué sous licence **Apache 2.0**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---
*Projet maintenu par cmendezs. Pour toute question relative à l'implémentation de la norme XP Z12-013, n'hésitez pas à ouvrir une Issue.*
