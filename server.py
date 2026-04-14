"""
Point d'entrée du MCP server mcp-facture-electronique-fr.

Expose les APIs standardisées AFNOR XP Z12-013 (Flow Service + Directory Service)
via le protocole MCP (Model Context Protocol) en mode Solution Compatible (SC).

Usage :
    python server.py                    # mode stdio (Claude Desktop / claude.ai/code)
    fastmcp dev server.py               # mode développement avec inspector
    fastmcp install server.py           # installation dans Claude Desktop
"""

from __future__ import annotations

import logging
import sys

from fastmcp import FastMCP

from tools.directory_tools import register_directory_tools
from tools.flow_tools import register_flow_tools

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Création du serveur FastMCP
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="mcp-facture-electronique-fr",
    instructions=(
        "Serveur MCP pour la facturation électronique française (réforme 2026, AFNOR XP Z12-013). "
        "Mode Solution Compatible (SC) : intermédiaire entre le SI de l'entreprise et "
        "une Plateforme Agréée (PA).\n\n"
        "**Flow Service** — soumettre et suivre des flux (factures B2B Factur-X/UBL/CII, "
        "e-reportings B2BInt/B2C, statuts de cycle de vie CDAR) :\n"
        "  • submit_flow : déposer une facture ou un e-reporting\n"
        "  • submit_lifecycle_status : émettre un statut (Approuvée, Refusée, Encaissée…)\n"
        "  • search_flows : rechercher des flux par critères\n"
        "  • get_flow : récupérer métadonnées ou document d'un flux\n"
        "  • healthcheck_flow : vérifier la disponibilité de la PA\n\n"
        "**Directory Service** — consulter et maintenir l'annuaire PPF :\n"
        "  • get_company_by_siren / search_company : vérifier un assujetti\n"
        "  • get_establishment_by_siret / search_establishment : vérifier un établissement\n"
        "  • search/create/update_routing_code : gérer les codes routage\n"
        "  • get/search/create/update/delete_directory_line : gérer les adresses de réception\n\n"
        "**Workflow recommandé avant émission d'une facture :**\n"
        "1. get_directory_line(addressing_identifier=SIREN_DESTINATAIRE) → vérifier l'inscription\n"
        "2. submit_flow(file_base64=..., processing_rule='B2B', flow_type='Invoice')\n"
        "3. get_flow(flow_id=...) → suivre le statut\n\n"
        "Auth : OAuth2 Bearer JWT (renouvellement automatique). "
        "Config via variables d'environnement (.env)."
    ),
)

# ---------------------------------------------------------------------------
# Enregistrement des outils
# ---------------------------------------------------------------------------

register_flow_tools(mcp)
register_directory_tools(mcp)

logger.info(
    "MCP server 'mcp-facture-electronique-fr' initialisé — "
    "5 outils Flow Service + 12 outils Directory Service"
)

# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main() -> None:
    """Lance le serveur MCP en mode stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
