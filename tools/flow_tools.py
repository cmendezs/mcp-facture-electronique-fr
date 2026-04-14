"""
Outils MCP pour le Flow Service XP Z12-013 (Annexe A v1.1.0).

Ces outils sont exposés via FastMCP et permettent à Claude de soumettre,
rechercher et consulter des flux (factures, e-reportings, statuts) auprès
de la Plateforme Agréée.
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated, Literal, Optional

# Valeurs normalisées XP Z12-013 Annexe A §FlowInfo.processingRule
ProcessingRule = Literal[
    "B2B",          # facture domestique entre assujettis français
    "B2BInt",       # facture internationale / e-reporting
    "B2C",          # facture vers non-assujetti / e-reporting B2C
    "OutOfScope",   # hors périmètre réforme
    "ArchiveOnly",  # archivage sans routage
    "NotApplicable",# statut de cycle de vie (CDAR)
]

from fastmcp import FastMCP
from pydantic import Field

from clients.flow_client import FlowClient

logger = logging.getLogger(__name__)

# Le client est instancié une fois et partagé entre les tools
_flow_client: Optional[FlowClient] = None


def get_flow_client() -> FlowClient:
    global _flow_client
    if _flow_client is None:
        _flow_client = FlowClient()
    return _flow_client


def register_flow_tools(mcp: FastMCP) -> None:
    """Enregistre les 5 outils Flow Service sur l'instance FastMCP."""

    @mcp.tool()
    async def submit_flow(
        file_base64: Annotated[
            str,
            Field(
                description=(
                    "Contenu du fichier encodé en base64. "
                    "Formats acceptés : Factur-X (PDF/A-3), UBL 2.1 (XML), UN/CEFACT CII D22B (XML). "
                    "Taille maximale définie par la Plateforme Agréée."
                )
            ),
        ],
        file_name: Annotated[
            str,
            Field(
                description=(
                    "Nom du fichier avec extension (ex: facture_2024_001.xml, facture_2024_001.pdf). "
                    "Utilisé par la PA pour détecter le format si non spécifié dans flowInfo."
                )
            ),
        ],
        flow_syntax: Annotated[
            str,
            Field(
                description=(
                    "Syntaxe du flux soumis (champ requis par la PA). Valeurs courantes : "
                    "FacturX (facture PDF/A-3 avec XML embarqué), "
                    "UBL (facture XML UBL 2.1), "
                    "CII (facture XML UN/CEFACT CII D22B), "
                    "CDAR (statut de cycle de vie XML), "
                    "EReporting (flux e-reporting B2B/B2C)."
                )
            ),
        ],
        processing_rule: Annotated[
            ProcessingRule,
            Field(
                description=(
                    "Règle de traitement du flux. Valeurs acceptées : "
                    "B2B (facture domestique entre assujettis français), "
                    "B2BInt (facture internationale / e-reporting), "
                    "B2C (facture vers non-assujetti / e-reporting B2C), "
                    "OutOfScope (hors périmètre réforme), "
                    "ArchiveOnly (archivage sans routage), "
                    "NotApplicable (statut de cycle de vie)."
                )
            ),
        ],
        flow_type: Annotated[
            str,
            Field(
                description=(
                    "Type du flux soumis. Exemples : Invoice (facture), "
                    "CreditNote (avoir), EReportingB2B, EReportingB2C, LifecycleStatus. "
                    "Se référer à la documentation de la Plateforme Agréée pour la liste complète."
                )
            ),
        ],
        tracking_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Identifiant de suivi côté émetteur, libre (maxLength 36). "
                    "Permet de retrouver le flux via search_flows. "
                    "Peut être un numéro de facture, un UUID interne, etc."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Soumettre une facture électronique, un statut de cycle de vie ou un e-reporting
        à la Plateforme Agréée. Le flux peut être une facture B2B (Factur-X, UBL, CII),
        un e-reporting B2BInt ou B2C, ou un message de statut CDAR.

        Retourne le flowId attribué par la PA, le trackingId et le statut initial du flux.
        """
        try:
            file_content = base64.b64decode(file_base64)
        except Exception as e:
            return {"error": f"Décodage base64 impossible : {e}"}

        client = get_flow_client()
        result = await client.submit_flow(
            file_content=file_content,
            file_name=file_name,
            flow_syntax=flow_syntax,
            processing_rule=processing_rule,
            flow_type=flow_type,
            tracking_id=tracking_id,
        )
        return result

    @mcp.tool()
    async def search_flows(
        processing_rule: Annotated[
            Optional[ProcessingRule],
            Field(
                default=None,
                description=(
                    "Filtrer par règle de traitement : B2B, B2BInt, B2C, "
                    "OutOfScope, ArchiveOnly, NotApplicable."
                ),
            ),
        ] = None,
        flow_type: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Filtrer par type de flux : Invoice, CreditNote, "
                    "EReportingB2B, EReportingB2C, LifecycleStatus, etc."
                ),
            ),
        ] = None,
        status: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Filtrer par statut du flux. Exemples : Deposited, Processing, "
                    "Delivered, Rejected, Approved, Refused. "
                    "Se référer à la documentation PA pour la liste complète."
                ),
            ),
        ] = None,
        updated_after: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Pagination : ne retourner que les flux mis à jour après cette date/heure "
                    "(format ISO 8601, ex: 2024-09-01T00:00:00Z). "
                    "Utiliser la valeur 'nextUpdatedAfter' de la réponse précédente pour paginer."
                ),
            ),
        ] = None,
        tracking_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Filtrer par trackingId (identifiant libre émetteur, maxLength 36).",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                default=50,
                ge=1,
                le=500,
                description="Nombre maximum de flux à retourner (1-500, défaut 50).",
            ),
        ] = 50,
    ) -> dict:
        """
        Rechercher des flux (factures, statuts, e-reportings) dans la Plateforme Agréée
        selon des critères : type de flux, statut, processingRule, période, trackingId.
        Pagination via updatedAfter : utiliser le champ 'nextUpdatedAfter' de la réponse
        comme valeur du paramètre updated_after pour obtenir la page suivante.
        """
        client = get_flow_client()
        return await client.search_flows(
            processing_rule=processing_rule,
            flow_type=flow_type,
            status=status,
            updated_after=updated_after,
            tracking_id=tracking_id,
            limit=limit,
        )

    @mcp.tool()
    async def get_flow(
        flow_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant du flux attribué par la Plateforme Agréée "
                    "(retourné par submit_flow ou search_flows, maxLength 36)."
                )
            ),
        ],
        doc_type: Annotated[
            str,
            Field(
                default="Metadata",
                description=(
                    "Type de document à récupérer : "
                    "Metadata (défaut, retourne les métadonnées JSON du flux — recommandé), "
                    "Original (document original soumis, retourné en base64), "
                    "Converted (document converti par la PA, retourné en base64), "
                    "ReadableView (représentation PDF lisible, retournée en base64)."
                ),
            ),
        ] = "Metadata",
    ) -> dict:
        """
        Récupérer un flux par son identifiant. docType permet de choisir entre
        les métadonnées JSON (Metadata), le document original (Original), le document
        converti (Converted) ou la représentation lisible (ReadableView).
        Par défaut, retourne les métadonnées JSON (statut, dates, identifiants).
        """
        client = get_flow_client()
        result = await client.get_flow(flow_id=flow_id, doc_type=doc_type)

        if isinstance(result, bytes):
            # Encoder en base64 pour la sérialisation JSON
            return {
                "flowId": flow_id,
                "docType": doc_type,
                "contentBase64": base64.b64encode(result).decode(),
            }
        return result

    @mcp.tool()
    async def submit_lifecycle_status(
        referenced_flow_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant du flux de facture auquel s'applique ce statut "
                    "(flowId retourné lors de la réception, maxLength 36)."
                )
            ),
        ],
        status_code: Annotated[
            str,
            Field(
                description=(
                    "Code du statut de cycle de vie à émettre. Valeurs définies XP Z12-014 : "
                    "Refused (Refusée — transmis au PPF), "
                    "Approved (Approuvée), "
                    "PartiallyApproved (Approuvée partiellement), "
                    "Disputed (En litige), "
                    "Suspended (Suspendue), "
                    "Cashed (Encaissée — transmis au PPF), "
                    "PaymentTransmitted (Paiement transmis), "
                    "Cancelled (Annulée). "
                    "Refused et Cashed sont obligatoirement transmis au PPF."
                )
            ),
        ],
        reason: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Motif du statut, obligatoire pour Refused et Disputed. "
                    "Texte libre décrivant la raison du refus ou du litige."
                ),
            ),
        ] = None,
        payment_date: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Date de paiement (format ISO 8601 : YYYY-MM-DD). "
                    "Renseigné pour les statuts Cashed et PaymentTransmitted."
                ),
            ),
        ] = None,
        payment_amount: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Montant du paiement (chaîne décimale, ex: '1250.00'). "
                    "Renseigné pour les statuts Cashed et PaymentTransmitted."
                ),
            ),
        ] = None,
    ) -> dict:
        """
        Émettre un statut de traitement sur une facture reçue : Refusée, Approuvée,
        Approuvée partiellement, En litige, Suspendue, Encaissée, Paiement transmis,
        Annulée. Les statuts Refused et Cashed sont transmis obligatoirement au PPF.
        Le motif est obligatoire pour Refused et Disputed.
        """
        client = get_flow_client()
        return await client.submit_lifecycle_status(
            referenced_flow_id=referenced_flow_id,
            status_code=status_code,
            reason=reason,
            payment_date=payment_date,
            payment_amount=payment_amount,
        )

    @mcp.tool()
    async def healthcheck_flow() -> dict:
        """
        Vérifier la disponibilité du Flow Service de la Plateforme Agréée.
        Retourne le statut opérationnel du service (ok/dégradé/indisponible).
        À utiliser avant une session d'émission de factures pour s'assurer
        que la PA est joignable.
        """
        client = get_flow_client()
        return await client.healthcheck()
