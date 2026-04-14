"""
Client HTTP pour le Directory Service XP Z12-013 (Annexe B v1.1.0).

Gère l'authentification OAuth2 automatique et la gestion des erreurs HTTP.
L'annuaire PPF est la source de vérité pour les adresses de réception
des assujettis à la facturation électronique.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from config import OAuthClient, PAConfig, get_config, get_oauth_client

logger = logging.getLogger(__name__)

_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Requête invalide — vérifier le format SIREN/SIRET ou les paramètres de recherche",
    401: "Non authentifié — token OAuth2 invalide ou expiré",
    403: "Accès refusé — droits insuffisants sur cette ressource annuaire",
    404: "Ressource introuvable — l'identifiant fourni n'existe pas dans l'annuaire",
    413: "Corps de requête trop volumineux",
    422: "Entité non traitable — données de l'annuaire invalides",
    429: "Trop de requêtes — limite de débit dépassée, réessayer ultérieurement",
    500: "Erreur interne du Directory Service — contacter la Plateforme Agréée",
    503: "Directory Service indisponible — la Plateforme Agréée est en maintenance",
}


def _raise_for_status(response: httpx.Response) -> None:
    """Lève une exception avec message métier selon le code HTTP."""
    if response.is_success:
        return

    code = response.status_code
    base_msg = _HTTP_ERROR_MESSAGES.get(code, f"Erreur HTTP {code}")

    detail = ""
    try:
        body = response.json()
        detail = body.get("detail") or body.get("message") or body.get("error_description") or ""
    except Exception:
        detail = response.text[:200] if response.text else ""

    full_msg = f"{base_msg}" + (f" — {detail}" if detail else "")
    logger.error("Directory Service %d : %s", code, full_msg)
    response.raise_for_status()


class DirectoryClient:
    """
    Wrapper asynchrone du Directory Service XP Z12-013.

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
        self._base_url = self._config.pa_base_url_directory

    async def _get_headers(self) -> dict[str, str]:
        token = await self._oauth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """Exécute une requête HTTP avec retry automatique sur 401."""
        url = f"{self._base_url}{path}"
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=self._config.http_timeout) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )

        if response.status_code == 401 and retry_on_401:
            logger.info("Token OAuth2 rejeté (401), renouvellement et retry")
            self._oauth.invalidate_token()
            return await self._request(
                method, path, params=params, json=json, retry_on_401=False
            )

        _raise_for_status(response)
        return response

    # ------------------------------------------------------------------
    # SIREN — Unités légales
    # ------------------------------------------------------------------

    async def search_company(
        self,
        name: Optional[str] = None,
        siren: Optional[str] = None,
        status: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/siren/search — Rechercher des unités légales dans l'annuaire."""
        body: dict[str, Any] = {"limit": limit}
        if name:
            body["name"] = name
        if siren:
            body["siren"] = siren
        if status:
            body["status"] = status
        if updated_after:
            body["updatedAfter"] = updated_after

        response = await self._request("POST", "/v1/siren/search", json=body)
        return response.json()

    async def get_company_by_siren(self, siren: str) -> dict[str, Any]:
        """GET /v1/siren/code-insee:{siren} — Consulter une unité légale par SIREN."""
        response = await self._request("GET", f"/v1/siren/code-insee:{siren}")
        return response.json()

    # ------------------------------------------------------------------
    # SIRET — Établissements
    # ------------------------------------------------------------------

    async def search_establishment(
        self,
        siret: Optional[str] = None,
        siren: Optional[str] = None,
        administrative_status: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/siret/search — Rechercher des établissements dans l'annuaire."""
        body: dict[str, Any] = {"limit": limit}
        if siret:
            body["siret"] = siret
        if siren:
            body["siren"] = siren
        if administrative_status:
            body["administrativeStatus"] = administrative_status
        if updated_after:
            body["updatedAfter"] = updated_after

        response = await self._request("POST", "/v1/siret/search", json=body)
        return response.json()

    async def get_establishment_by_siret(self, siret: str) -> dict[str, Any]:
        """GET /v1/siret/code-insee:{siret} — Consulter un établissement par SIRET."""
        response = await self._request("GET", f"/v1/siret/code-insee:{siret}")
        return response.json()

    # ------------------------------------------------------------------
    # Routing Code — Codes routage
    # ------------------------------------------------------------------

    async def search_routing_code(
        self,
        siret: Optional[str] = None,
        siren: Optional[str] = None,
        routing_code: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/routing-code/search — Rechercher des codes routage."""
        body: dict[str, Any] = {"limit": limit}
        if siret:
            body["siret"] = siret
        if siren:
            body["siren"] = siren
        if routing_code:
            body["routingCode"] = routing_code

        response = await self._request("POST", "/v1/routing-code/search", json=body)
        return response.json()

    async def create_routing_code(
        self,
        siret: str,
        routing_code: str,
        label: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST /v1/routing-code — Créer un code routage pour un SIRET."""
        body: dict[str, Any] = {
            "siret": siret,
            "routingCode": routing_code,
        }
        if label:
            body["label"] = label

        response = await self._request("POST", "/v1/routing-code", json=body)
        return response.json()

    async def update_routing_code(
        self,
        instance_id: str,
        routing_code: Optional[str] = None,
        label: Optional[str] = None,
    ) -> dict[str, Any]:
        """PATCH /v1/routing-code/id-instance:{id} — Mettre à jour un code routage."""
        body: dict[str, Any] = {}
        if routing_code:
            body["routingCode"] = routing_code
        if label:
            body["label"] = label

        response = await self._request(
            "PATCH", f"/v1/routing-code/id-instance:{instance_id}", json=body
        )
        return response.json()

    # ------------------------------------------------------------------
    # Directory Line — Lignes d'annuaire
    # ------------------------------------------------------------------

    async def search_directory_line(
        self,
        siren: Optional[str] = None,
        siret: Optional[str] = None,
        routing_code: Optional[str] = None,
        platform_id: Optional[str] = None,
        updated_after: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """POST /v1/directory-line/search — Rechercher des lignes d'annuaire."""
        body: dict[str, Any] = {"limit": limit}
        if siren:
            body["siren"] = siren
        if siret:
            body["siret"] = siret
        if routing_code:
            body["routingCode"] = routing_code
        if platform_id:
            body["platformId"] = platform_id
        if updated_after:
            body["updatedAfter"] = updated_after

        response = await self._request("POST", "/v1/directory-line/search", json=body)
        return response.json()

    async def get_directory_line(self, addressing_identifier: str) -> dict[str, Any]:
        """
        GET /v1/directory-line/code:{addressing-identifier} — Consulter une ligne d'annuaire.

        L'addressing-identifier est composé de SIREN, SIREN/SIRET, ou SIREN/SIRET/code-routage.
        """
        response = await self._request(
            "GET", f"/v1/directory-line/code:{addressing_identifier}"
        )
        return response.json()

    async def create_directory_line(
        self,
        siren: str,
        platform_id: str,
        siret: Optional[str] = None,
        routing_code: Optional[str] = None,
        technical_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST /v1/directory-line — Créer une ligne d'annuaire."""
        body: dict[str, Any] = {
            "siren": siren,
            "platformId": platform_id,
        }
        if siret:
            body["siret"] = siret
        if routing_code:
            body["routingCode"] = routing_code
        if technical_address:
            body["technicalAddress"] = technical_address

        response = await self._request("POST", "/v1/directory-line", json=body)
        return response.json()

    async def update_directory_line(
        self,
        instance_id: str,
        platform_id: Optional[str] = None,
        technical_address: Optional[str] = None,
        routing_code: Optional[str] = None,
    ) -> dict[str, Any]:
        """PATCH /v1/directory-line/id-instance:{id} — Mettre à jour une ligne d'annuaire."""
        body: dict[str, Any] = {}
        if platform_id:
            body["platformId"] = platform_id
        if technical_address:
            body["technicalAddress"] = technical_address
        if routing_code:
            body["routingCode"] = routing_code

        response = await self._request(
            "PATCH", f"/v1/directory-line/id-instance:{instance_id}", json=body
        )
        return response.json()

    async def delete_directory_line(self, instance_id: str) -> dict[str, Any]:
        """DELETE /v1/directory-line/id-instance:{id} — Supprimer une ligne d'annuaire."""
        response = await self._request(
            "DELETE", f"/v1/directory-line/id-instance:{instance_id}"
        )
        # DELETE peut retourner 204 No Content
        if response.status_code == 204 or not response.content:
            return {"deleted": True, "instanceId": instance_id}
        return response.json()
