# mcp-facture-electronique-fr 🇫🇷
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

Serveur MCP Python exposant les APIs standardisées **AFNOR XP Z12-013** pour la réforme de la facturation électronique française (entrée en vigueur le 1er septembre 2026). Ce projet permet aux agents IA (Claude, IDEs) d'interagir nativement avec l'écosystème des Plateformes Agréées (PA/PDP) en tant que Solution Compatible (SC).

**English:** This is a **Model Context Protocol (MCP)** server specifically designed for **digital invoicing** in France. It implements the **XP Z12-013** API specifications to enable AI agents to manage, validate, and explore **e-invoicing** workflows within the French regulatory ecosystem (2024-2026 reform).

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
| **Flow Service** | Flux de factures & E-reporting | Annexe A – v1.1.0 | 5 outils |
| **Directory Service** | Annuaire centralisé (SIREN/SIRET) | Annexe B – v1.1.0 | 12 outils |

## 🚀 Installation

```bash
# Cloner le dépôt
git clone [https://github.com/VOTRE_NOM_UTILISATEUR/mcp-facture-electronique-fr.git](https://github.com/VOTRE_NOM_UTILISATEUR/mcp-facture-electronique-fr.git)
cd mcp-facture-electronique-fr
```

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows : .venv\Scripts\activate

# Installation en mode éditable
pip install -e ".[dev]"

# Configuration initiale
cp .env.example .env
# Éditer .env avec vos credentials fournis par votre PA/PDP

## ⚙️ Configuration (.env)

Le serveur nécessite les variables suivantes pour s'authentifier auprès d'une Plateforme Agréée (PA) :

| Variable | Description |
|----------|-------------|
| `PA_BASE_URL_FLOW` | URL de base du Flow Service de la PA |
| `PA_BASE_URL_DIRECTORY` | URL de base du Directory Service de la PA |
| `PA_CLIENT_ID` | Client ID OAuth2 |
| `PA_CLIENT_SECRET` | Client Secret OAuth2 |
| `PA_TOKEN_URL` | URL du serveur d'authentification |
| `HTTP_TIMEOUT` | Timeout des requêtes (défaut : 30s) |

## 🤖 Intégration Claude Desktop

Pour utiliser ce serveur avec Claude, ajoutez cette configuration dans votre fichier `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "python",
      "args": ["/CHEMIN_ABSOLU_VERS_VOTRE_PROJET/server.py"],
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
      "command": "python",
      "args": ["/CHEMIN_ABSOLU_VERS_VOTRE_PROJET/server.py"],
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

Rechargez la fenêtre Cursor (`Ctrl+Shift+P` → *Reload Window*) pour prendre en compte les changements.

## 🪐 Intégration Kiro

Kiro supporte les serveurs MCP via son fichier de configuration dédié. Deux niveaux disponibles :
- **Global** (tous les projets) : `~/.kiro/settings/mcp.json`
- **Workspace** (ce dépôt uniquement) : `.kiro/settings/mcp.json`

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "python",
      "args": ["/CHEMIN_ABSOLU_VERS_VOTRE_PROJET/server.py"],
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

Le fichier est rechargé automatiquement à la sauvegarde. Vous pouvez également ouvrir la config via la palette de commandes (`Cmd+Shift+P` / `Ctrl+Shift+P`) → *MCP*.

> **Conseil sécurité Kiro** : plutôt que d'écrire les secrets en clair, utilisez la syntaxe `"PA_CLIENT_SECRET": "${PA_CLIENT_SECRET}"` — Kiro résout les variables d'environnement shell au démarrage.

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

## 📚 Références réglementaires
- **AFNOR XP Z12-013** : Spécifications des interfaces de services (version février 2026).
- **AFNOR XP Z12-014** : Guide d'implémentation technique des cas d'usage métier.
- **Réforme B2B France** : Calendrier de déploiement obligatoire (2024-2026).

## 🧪 Tests

```bash
# Lancer la suite de tests unitaires et d'intégration
pytest tests/ -v
```

## 📄 Licence

Ce projet est distribué sous licence **Apache 2.0**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---
*Projet maintenu par cmendezs. Pour toute question relative à l'implémentation de la norme XP Z12-013, n'hésitez pas à ouvrir une Issue.*


