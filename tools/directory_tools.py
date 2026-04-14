"""
Outils MCP pour le Directory Service XP Z12-013 (Annexe B v1.1.0).

Ces outils permettent à Claude d'interroger et de maintenir l'annuaire PPF :
recherche d'entreprises (SIREN), d'établissements (SIRET), gestion des codes
routage et des lignes d'annuaire (adresses de facturation électronique).
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

from clients.directory_client import DirectoryClient

logger = logging.getLogger(__name__)

_directory_client: Optional[DirectoryClient] = None


def get_directory_client() -> DirectoryClient:
    global _directory_client
    if _directory_client is None:
        _directory_client = DirectoryClient()
    return _directory_client


def register_directory_tools(mcp: FastMCP) -> None:
    """Enregistre les 12 outils Directory Service sur l'instance FastMCP."""

    # ------------------------------------------------------------------
    # SIREN — Unités légales
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_company(
        name: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Nom ou raison sociale de l'entreprise (recherche partielle acceptée). "
                    "Exemple : 'Dupont' retournera toutes les entités dont le nom contient 'Dupont'."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Numéro SIREN de l'entreprise (9 chiffres, sans espaces). "
                    "Exemple : '123456789'."
                ),
            ),
        ] = None,
        status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Statut de l'unité légale dans l'annuaire PPF. "
                    "Valeurs possibles : Active, Inactive, Pending."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Pagination : retourner uniquement les entrées mises à jour après "
                    "cette date/heure (format ISO 8601, ex: 2024-09-01T00:00:00Z)."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Nombre maximum de résultats (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Rechercher une entreprise dans l'annuaire PPF par critères (nom, SIREN, statut).
        Retourne les unités légales assujetties à la TVA enregistrées dans l'annuaire.
        Au moins un critère de recherche doit être fourni.
        """
        client = get_directory_client()
        return await client.search_company(
            name=name,
            siren=siren,
            status=status,
            updated_after=updated_after,
            limit=limit,
        )

    @mcp.tool()
    async def get_company_by_siren(
        siren: Annotated[
            str,
            Field(
                description=(
                    "Numéro SIREN de l'entreprise (9 chiffres, sans espaces). "
                    "Exemple : '123456789'. "
                    "Retourne les informations complètes de l'unité légale dans l'annuaire PPF, "
                    "y compris son statut d'inscription et sa Plateforme Agréée."
                )
            ),
        ],
    ) -> dict:
        """
        Consulter une entreprise dans l'annuaire PPF par son numéro SIREN.
        Retourne les informations complètes de l'unité légale : raison sociale,
        statut administratif, Plateforme Agréée associée et dates d'inscription.
        """
        client = get_directory_client()
        return await client.get_company_by_siren(siren=siren)

    # ------------------------------------------------------------------
    # SIRET — Établissements
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_establishment(
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Numéro SIRET de l'établissement (14 chiffres, sans espaces). "
                    "Exemple : '12345678900012'."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "SIREN de l'entreprise parente (9 chiffres). "
                    "Retourne tous les établissements de cette entreprise."
                ),
            ),
        ] = None,
        administrative_status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Statut administratif de l'établissement. "
                    "Valeurs : Active (ouvert), Inactive (fermé)."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Pagination ISO 8601 (ex: 2024-09-01T00:00:00Z).",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Nombre maximum de résultats (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Rechercher un établissement dans l'annuaire PPF par critères
        (SIRET, SIREN parent, statut administratif).
        Un établissement correspond à un lieu d'exercice de l'activité (SIRET).
        """
        client = get_directory_client()
        return await client.search_establishment(
            siret=siret,
            siren=siren,
            administrative_status=administrative_status,
            updated_after=updated_after,
            limit=limit,
        )

    @mcp.tool()
    async def get_establishment_by_siret(
        siret: Annotated[
            str,
            Field(
                description=(
                    "Numéro SIRET de l'établissement (14 chiffres, sans espaces). "
                    "Exemple : '12345678900012'. "
                    "Indispensable pour vérifier l'adresse de réception avant envoi d'une facture : "
                    "confirme que l'établissement est inscrit et actif dans l'annuaire PPF."
                )
            ),
        ],
    ) -> dict:
        """
        Consulter un établissement dans l'annuaire PPF par son numéro SIRET.
        Indispensable pour vérifier l'adresse de réception avant envoi d'une facture.
        Retourne les coordonnées de l'établissement, son statut et sa Plateforme Agréée.
        """
        client = get_directory_client()
        return await client.get_establishment_by_siret(siret=siret)

    # ------------------------------------------------------------------
    # Routing Code — Codes routage
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_routing_code(
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "SIRET de l'établissement (14 chiffres). "
                    "Retourne tous les codes routage associés à cet établissement."
                ),
            ),
        ] = None,
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description="SIREN de l'entreprise (9 chiffres).",
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Valeur du code routage à rechercher (ex: 'SERVICE-COMPTABLE', 'DEPT-75')."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Nombre maximum de résultats (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Rechercher les codes routage d'un destinataire dans l'annuaire PPF.
        Le code routage affine l'adresse de réception au niveau service ou département
        pour les entreprises qui souhaitent ventiler leurs factures reçues.
        """
        client = get_directory_client()
        return await client.search_routing_code(
            siret=siret,
            siren=siren,
            routing_code=routing_code,
            limit=limit,
        )

    @mcp.tool()
    async def create_routing_code(
        siret: Annotated[
            str,
            Field(
                description=(
                    "SIRET de l'établissement auquel associer ce code routage (14 chiffres)."
                )
            ),
        ],
        routing_code: Annotated[
            str,
            Field(
                description=(
                    "Valeur du code routage à créer (chaîne libre, ex: 'SERVICE-ACHAT', 'AGENCE-PARIS'). "
                    "Ce code sera utilisé dans l'adresse de facturation du destinataire."
                )
            ),
        ],
        label: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Libellé descriptif du code routage (ex: 'Service des achats - siège').",
            ),
        ] = None,
    ) -> dict:
        """
        Créer un code routage pour un SIRET dans l'annuaire PPF.
        Le code routage permet d'affiner l'adresse de réception des factures
        au niveau d'un service ou d'un département de l'entreprise destinataire.
        """
        client = get_directory_client()
        return await client.create_routing_code(
            siret=siret,
            routing_code=routing_code,
            label=label,
        )

    @mcp.tool()
    async def update_routing_code(
        instance_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant d'instance du code routage à modifier "
                    "(retourné par create_routing_code ou search_routing_code)."
                )
            ),
        ],
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Nouvelle valeur du code routage.",
            ),
        ] = None,
        label: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Nouveau libellé descriptif.",
            ),
        ] = None,
    ) -> dict:
        """
        Mettre à jour partiellement un code routage existant dans l'annuaire PPF.
        Seuls les champs fournis sont modifiés (PATCH sémantique).
        """
        client = get_directory_client()
        return await client.update_routing_code(
            instance_id=instance_id,
            routing_code=routing_code,
            label=label,
        )

    # ------------------------------------------------------------------
    # Directory Line — Lignes d'annuaire
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_directory_line(
        siren: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "SIREN de l'assujetti (9 chiffres). "
                    "Retourne toutes les lignes d'annuaire enregistrées pour cette entreprise."
                ),
            ),
        ] = None,
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description="SIRET d'un établissement spécifique (14 chiffres).",
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filtrer par code routage associé à la ligne d'annuaire.",
            ),
        ] = None,
        platform_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filtrer par identifiant de Plateforme Agréée.",
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Pagination ISO 8601 (ex: 2024-09-01T00:00:00Z).",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(default=50, ge=1, le=500, description="Nombre maximum de résultats (1-500)."),
        ] = 50,
    ) -> dict:
        """
        Rechercher les lignes d'annuaire (adresses de facturation électronique) d'un assujetti.
        Une ligne d'annuaire est l'adresse à laquelle le destinataire souhaite recevoir ses
        factures (identifiée par SIREN, SIREN/SIRET, ou SIREN/SIRET/code-routage).
        """
        client = get_directory_client()
        return await client.search_directory_line(
            siren=siren,
            siret=siret,
            routing_code=routing_code,
            platform_id=platform_id,
            updated_after=updated_after,
            limit=limit,
        )

    @mcp.tool()
    async def get_directory_line(
        addressing_identifier: Annotated[
            str,
            Field(
                description=(
                    "Identifiant d'adressage de la ligne d'annuaire. "
                    "Format : SIREN seul (ex: '123456789'), "
                    "SIREN/SIRET (ex: '123456789/12345678900012'), "
                    "ou SIREN/SIRET/code-routage (ex: '123456789/12345678900012/SERVICE-ACHAT'). "
                    "À utiliser avant toute émission de facture pour vérifier "
                    "l'atteignabilité du destinataire et sa Plateforme Agréée."
                )
            ),
        ],
    ) -> dict:
        """
        Consulter une ligne d'annuaire par son identifiant d'adressage.
        À utiliser avant toute émission de facture pour vérifier l'atteignabilité
        du destinataire et obtenir sa Plateforme Agréée de réception.
        Retourne 404 si le destinataire n'est pas encore inscrit dans l'annuaire PPF.
        """
        client = get_directory_client()
        return await client.get_directory_line(addressing_identifier=addressing_identifier)

    @mcp.tool()
    async def create_directory_line(
        siren: Annotated[
            str,
            Field(
                description="SIREN de l'assujetti (9 chiffres) qui crée cette adresse de réception."
            ),
        ],
        platform_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant de la Plateforme Agréée qui recevra les factures "
                    "(fourni par votre PA lors de l'inscription)."
                )
            ),
        ],
        siret: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "SIRET d'un établissement spécifique (14 chiffres). "
                    "Si absent, la ligne s'applique à tous les établissements du SIREN."
                ),
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Code routage pour affiner l'adresse de réception "
                    "(doit exister via create_routing_code)."
                ),
            ),
        ] = None,
        technical_address: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Adresse technique de réception propre à la PA "
                    "(endpoint, boîte aux lettres, etc.). "
                    "Format défini par la Plateforme Agréée."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Créer une ligne d'annuaire (adresse de réception de factures électroniques)
        pour un assujetti. Nécessaire pour s'inscrire dans l'annuaire PPF et
        permettre à d'autres entreprises de vous adresser des factures électroniques.
        Une ligne peut être au niveau SIREN (toute l'entreprise), SIREN/SIRET
        (un établissement) ou SIREN/SIRET/code-routage (un service précis).
        """
        client = get_directory_client()
        return await client.create_directory_line(
            siren=siren,
            platform_id=platform_id,
            siret=siret,
            routing_code=routing_code,
            technical_address=technical_address,
        )

    @mcp.tool()
    async def update_directory_line(
        instance_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant d'instance de la ligne d'annuaire à modifier "
                    "(retourné par create_directory_line ou search_directory_line)."
                )
            ),
        ],
        platform_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Nouvel identifiant de Plateforme Agréée. "
                    "À utiliser en cas de changement de PA (avec delete_directory_line sur l'ancienne)."
                ),
            ),
        ] = None,
        technical_address: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Nouvelle adresse technique de réception.",
            ),
        ] = None,
        routing_code: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Nouveau code routage associé.",
            ),
        ] = None,
    ) -> dict:
        """
        Mettre à jour partiellement une ligne d'annuaire existante.
        Seuls les champs fournis sont modifiés (PATCH sémantique).
        Utilisé notamment pour mettre à jour l'adresse technique lors d'un
        changement de configuration côté Plateforme Agréée.
        """
        client = get_directory_client()
        return await client.update_directory_line(
            instance_id=instance_id,
            platform_id=platform_id,
            technical_address=technical_address,
            routing_code=routing_code,
        )

    @mcp.tool()
    async def delete_directory_line(
        instance_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant d'instance de la ligne d'annuaire à supprimer "
                    "(retourné par create_directory_line ou search_directory_line). "
                    "ATTENTION : cette action est définitive. Après suppression, "
                    "les émetteurs ne pourront plus vous adresser de factures via cette adresse."
                )
            ),
        ],
    ) -> dict:
        """
        Supprimer une ligne d'annuaire. À utiliser lors d'un changement de Plateforme Agréée
        ou d'une fermeture d'établissement. Après suppression, créer une nouvelle ligne
        via create_directory_line si nécessaire.
        ATTENTION : action irréversible — vérifier l'instance_id avant d'appeler cet outil.
        """
        client = get_directory_client()
        return await client.delete_directory_line(instance_id=instance_id)
