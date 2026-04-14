"""
Client HTTP pour le Flow Service XP Z12-013 (Annexe A v1.1.0).

Gère l'authentification OAuth2 automatique et la gestion des erreurs HTTP
conformément aux codes de retour définis dans la norme.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

import httpx

# Valeurs normalisées XP Z12-013 Annexe A §FlowInfo.processingRule
ProcessingRule = Literal[
    "B2B",
    "B2BInt",
    "B2C",
    "OutOfScope",
    "ArchiveOnly",
    "NotApplicable",
]

from config import OAuthClient, PAConfig, get_config, get_oauth_client

logger = logging.getLogger(__name__)

# Codes d'erreur HTTP gérés explicitement (XP Z12-013 §5.x)
_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Requête invalide — vérifier le format du flux ou des paramètres",
    401: "Non authentifié — token OAuth2 invalide ou expiré",
    403: "Accès refusé — droits insuffisants sur ce flux ou cette opération",
    404: "Flux introuvable — l'identifiant fourni n'existe pas",
    413: "Flux trop volumineux — dépasse la taille maximale acceptée par la PA",
    422: "Entité non traitable — le flux est syntaxiquement invalide",
    429: "Trop de requêtes — limite de débit dépassée, réessayer ultérieurement",
    500: "Erreur interne du Flow Service — contacter la Plateforme Agréée",
    503: "Flow Service indisponible — la Plateforme Agréée est en maintenance",
}


def _raise_for_status(response: httpx.Response) -> None:
    """
    Lève une exception avec un message métier clair selon le code HTTP.

    Tente d'inclure le détail renvoyé par la PA (champ 'errorCode'/'errorMessage'
    définis dans le schéma Error XP Z12-013, ou fallback sur le corps texte).
    """
    if response.is_success:
        return

    code = response.status_code
    base_msg = _HTTP_ERROR_MESSAGES.get(code, f"Erreur HTTP {code}")

    detail = ""
    try:
        body = response.json()
        # Schéma Error XP Z12-013 : { errorCode, errorMessage }
        detail = body.get("errorMessage") or body.get("errorCode") or ""
    except Exception:
        detail = response.text[:200] if response.text else ""

    full_msg = f"{base_msg}" + (f" — {detail}" if detail else "")
    logger.error("Flow Service %d : %s", code, full_msg)
    response.raise_for_status()  # conserve la sémantique httpx standard


class FlowClient:
    """
    Wrapper asynchrone du Flow Service XP Z12-013.

    Toutes les méthodes renouvellent le token OAuth2 automatiquement.
    En cas de 401, le token est invalidé et la requête est réessayée une fois.
    """

    def __init__(
        self,
        config: Optional[PAConfig] = None,
        oauth: Optional[OAuthClient] = None,
    ) -> None:
        self._config = config or get_config()
        self._oauth = oauth or get_oauth_client()
        self._base_url = self._config.pa_base_url_flow

    async def _get_headers(self) -> dict[str, str]:
        token = await self._oauth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """
        Exécute une requête HTTP avec retry automatique sur 401.

        Un 401 invalide le token et relance la requête une seule fois
        (le serveur d'autorisation peut avoir révoqué le token).
        """
        url = f"{self._base_url}{path}"
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=self._config.http_timeout) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                files=files,
            )

        if response.status_code == 401 and retry_on_401:
            logger.info("Token OAuth2 rejeté (401), renouvellement et retry")
            self._oauth.invalidate_token()
            return await self._request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                retry_on_401=False,
            )

        _raise_for_status(response)
        return response

    # ------------------------------------------------------------------
    # Flow Service — endpoints
    # ------------------------------------------------------------------

    async def submit_flow(
        self,
        file_content: bytes,
        file_name: str,
        flow_syntax: str,
        processing_rule: Optional[ProcessingRule] = None,
        flow_type: Optional[str] = None,
        tracking_id: Optional[str] = None,
        sha256: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        POST /v1/flows — Soumettre un flux (facture, e-reporting, statut CDAR).

        Le flux est envoyé en multipart/form-data avec :
        - `file`     : le document binaire
        - `flowInfo` : les métadonnées JSON (flowSyntax requis, XP Z12-013 Annexe A)
        """
        import json as _json

        # flowSyntax est le seul champ requis dans FlowInfo (spec Annexe A 1.1.0)
        flow_info: dict[str, Any] = {"flowSyntax": flow_syntax}
        if processing_rule:
            flow_info["processingRule"] = processing_rule
        if flow_type:
            flow_info["flowType"] = flow_type
        if tracking_id:
            flow_info["trackingId"] = tracking_id
        if sha256:
            flow_info["sha256"] = sha256
        # 'name' dans flowInfo correspond au nom du fichier (spec §FlowInfo)
        flow_info["name"] = file_name

        files = {
            "file": (file_name, file_content, "application/octet-stream"),
            "flowInfo": (None, _json.dumps(flow_info), "application/json"),
        }

        response = await self._request("POST", "/v1/flows", files=files)
        return response.json()

    async def submit_lifecycle_status(
        self,
        referenced_flow_id: str,
        status_code: str,
        reason: Optional[str] = None,
        payment_date: Optional[str] = None,
        payment_amount: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        POST /v1/flows — Soumettre un statut de cycle de vie (CDAR).

        Construit un flux CDAR (flowSyntax='CDAR', flowType='CustomerInvoiceLC'
        ou 'SupplierInvoiceLC' selon le contexte) et le soumet via POST /v1/flows.
        """
        import json as _json

        status_xml = _build_lifecycle_status_xml(
            referenced_flow_id=referenced_flow_id,
            status_code=status_code,
            reason=reason,
            payment_date=payment_date,
            payment_amount=payment_amount,
        )

        flow_info: dict[str, Any] = {
            "flowSyntax": "CDAR",
            "processingRule": "NotApplicable",
            # SupplierInvoiceLC = statut sur facture reçue (fournisseur → client)
            "flowType": "SupplierInvoiceLC",
            "name": "lifecycle_status.xml",
        }

        files = {
            "file": ("lifecycle_status.xml", status_xml.encode("utf-8"), "application/xml"),
            "flowInfo": (None, _json.dumps(flow_info), "application/json"),
        }

        response = await self._request("POST", "/v1/flows", files=files)
        return response.json()

    async def search_flows(
        self,
        processing_rule: Optional[ProcessingRule | list[ProcessingRule]] = None,
        flow_type: Optional[str | list[str]] = None,
        status: Optional[str | list[str]] = None,
        flow_direction: Optional[str | list[str]] = None,
        ack_status: Optional[str] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        tracking_id: Optional[str] = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        POST /v1/flows/search — Rechercher des flux selon des critères.

        Structure du corps : { "limit": N, "where": { <critères> } }
        (spec SearchFlowParams Annexe A 1.1.0 — wrapper 'where' requis).

        La pagination s'effectue via `updatedAfter` (ISO 8601).
        processingRule et flowType acceptent une valeur unique ou une liste.
        """
        where: dict[str, Any] = {}

        if processing_rule:
            where["processingRule"] = (
                processing_rule if isinstance(processing_rule, list) else [processing_rule]
            )
        if flow_type:
            where["flowType"] = (
                flow_type if isinstance(flow_type, list) else [flow_type]
            )
        if status:
            where["status"] = (
                status if isinstance(status, list) else [status]
            )
        if flow_direction:
            where["flowDirection"] = (
                flow_direction if isinstance(flow_direction, list) else [flow_direction]
            )
        if ack_status:
            where["ackStatus"] = ack_status
        if updated_after:
            where["updatedAfter"] = updated_after
        if updated_before:
            where["updatedBefore"] = updated_before
        if tracking_id:
            where["trackingId"] = tracking_id

        body: dict[str, Any] = {"limit": limit, "where": where}
        response = await self._request("POST", "/v1/flows/search", json=body)
        return response.json()

    async def get_flow(
        self,
        flow_id: str,
        doc_type: str = "Metadata",
    ) -> dict[str, Any] | bytes:
        """
        GET /v1/flows/{flowId} — Récupérer un flux par son identifiant.

        - `Metadata` (défaut) : retourne les métadonnées JSON du flux
        - `Original` : retourne le document original (binaire)
        - `Converted` : retourne le document converti (binaire)
        - `ReadableView` : retourne la représentation lisible (PDF binaire)
        """
        params = {"docType": doc_type}
        response = await self._request("GET", f"/v1/flows/{flow_id}", params=params)

        if doc_type == "Metadata":
            return response.json()
        return response.content

    async def healthcheck(self) -> dict[str, Any]:
        """GET /v1/healthcheck — Vérifier la disponibilité du Flow Service."""
        response = await self._request("GET", "/v1/healthcheck")
        try:
            return response.json()
        except Exception:
            return {"status": "ok", "http_status": response.status_code}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_lifecycle_status_xml(
    referenced_flow_id: str,
    status_code: str,
    reason: Optional[str] = None,
    payment_date: Optional[str] = None,
    payment_amount: Optional[str] = None,
) -> str:
    """
    Construit un document XML CDAR de statut de cycle de vie.

    Le format exact dépend de la PA — cet helper produit un XML générique
    conforme aux statuts définis dans XP Z12-014 (42 cas B2B).
    """
    reason_el = f"<Reason>{reason}</Reason>" if reason else ""
    payment_el = ""
    if payment_date or payment_amount:
        payment_el = (
            "<Payment>"
            + (f"<Date>{payment_date}</Date>" if payment_date else "")
            + (f"<Amount>{payment_amount}</Amount>" if payment_amount else "")
            + "</Payment>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<LifecycleStatus xmlns="urn:xp-z12-013:lifecycle-status:1.0">'
        f"<ReferencedFlowId>{referenced_flow_id}</ReferencedFlowId>"
        f"<StatusCode>{status_code}</StatusCode>"
        f"{reason_el}"
        f"{payment_el}"
        "</LifecycleStatus>"
    )
