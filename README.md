# mcp-facture-electronique-fr

Serveur MCP Python exposant les APIs standardisées **AFNOR XP Z12-013** pour la réforme de facturation électronique française (entrée en vigueur le 1er septembre 2026).

Conçu pour fonctionner en mode **Solution Compatible (SC)** : intermédiaire entre un SI d'entreprise et une Plateforme Agréée (PA).

## Services exposés

| Service | Norme | Outils MCP |
|---------|-------|------------|
| Flow Service | Annexe A – v1.1.0 | 5 outils |
| Directory Service | Annexe B – v1.1.0 | 12 outils |

## Prérequis

- Python 3.10+
- Un accès à une Plateforme Agréée (PA) avec credentials OAuth2

## Installation

```bash
# Cloner et installer
git clone <repo>
cd mcp-facture-electronique-fr
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos credentials PA
```

## Configuration

Variables d'environnement (fichier `.env`) :

| Variable | Description |
|----------|-------------|
| `PA_BASE_URL_FLOW` | URL de base du Flow Service PA |
| `PA_BASE_URL_DIRECTORY` | URL de base du Directory Service PA |
| `PA_CLIENT_ID` | Client ID OAuth2 |
| `PA_CLIENT_SECRET` | Client Secret OAuth2 |
| `PA_TOKEN_URL` | URL du token OAuth2 |
| `PA_OAUTH_SCOPE` | Scope OAuth2 (optionnel) |
| `HTTP_TIMEOUT` | Timeout HTTP en secondes (défaut : 30) |
| `DEBUG` | Logs de débogage (défaut : false) |

## Lancement

```bash
# Mode stdio (pour Claude Desktop / claude.ai/code)
python server.py

# Ou via le script installé
mcp-facture-electronique-fr
```

### Intégration Claude Desktop

Ajouter dans `~/Library/Application Support/Claude/claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "facture-electronique-fr": {
      "command": "python",
      "args": ["/chemin/vers/mcp-facture-electronique-fr/server.py"],
      "env": {
        "PA_BASE_URL_FLOW": "https://api.flow.votre-pa.fr/flow-service",
        "PA_BASE_URL_DIRECTORY": "https://api.directory.votre-pa.fr/directory-service",
        "PA_CLIENT_ID": "votre-client-id",
        "PA_CLIENT_SECRET": "votre-client-secret",
        "PA_TOKEN_URL": "https://auth.votre-pa.fr/oauth/token"
      }
    }
  }
}
```

## Outils MCP disponibles

### Flow Service

| Outil | Description |
|-------|-------------|
| `submit_flow` | Soumettre une facture, e-reporting ou statut CDAR |
| `search_flows` | Rechercher des flux par critères |
| `get_flow` | Récupérer un flux par son ID |
| `submit_lifecycle_status` | Émettre un statut de cycle de vie |
| `healthcheck_flow` | Vérifier la disponibilité du Flow Service |

### Directory Service

| Outil | Description |
|-------|-------------|
| `search_company` | Rechercher une entreprise par SIREN/nom |
| `get_company_by_siren` | Consulter une entreprise par SIREN |
| `search_establishment` | Rechercher un établissement par SIRET |
| `get_establishment_by_siret` | Consulter un établissement par SIRET |
| `search_routing_code` | Rechercher les codes routage d'un destinataire |
| `create_routing_code` | Créer un code routage |
| `update_routing_code` | Mettre à jour un code routage |
| `search_directory_line` | Rechercher les lignes d'annuaire d'un assujetti |
| `get_directory_line` | Consulter une ligne d'annuaire |
| `create_directory_line` | Créer une ligne d'annuaire |
| `update_directory_line` | Mettre à jour une ligne d'annuaire |
| `delete_directory_line` | Supprimer une ligne d'annuaire |

## Tests

```bash
pytest tests/ -v
```

## Références réglementaires

- **XP Z12-013** (février 2026) — Norme AFNOR des interfaces standardisées
- **XP Z12-014 v1.2** — 42 cas d'usage B2B
- Formats supportés : Factur-X, UBL 2.1, UN/CEFACT CII D22B
- Deadline réforme : **1er septembre 2026**
