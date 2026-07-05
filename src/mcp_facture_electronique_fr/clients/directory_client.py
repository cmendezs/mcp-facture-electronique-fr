"""
HTTP client for the PPF Annuaire (directory) service.

Wired directly against the bundled PPF-platform swagger
`specs/dgfip/swagger/ppf-openapi-annuaire-api-public-1.11.0-openapi.json`
(v1.11.0). This is a PPF-specific tool set, not a PDP-agnostic XP Z12-013
Annex B Directory Service interface — see FR-FLUX11-2026-06 in
context-library/countries/fr.md for the framing-shift rationale.

Per the swagger's own `info.description`: endpoints are subject to change
and require prior PISTE application publication.

Inherits BaseEInvoicingClient from mcp-einvoicing-core, which provides:
  - OAuth2 client_credentials token management (shared TokenCache with FlowClient)
  - Automatic 401 retry
  - Structured PlatformError on HTTP failures
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient, TokenCache

from mcp_facture_electronique_fr.config import PAConfig, get_config, get_shared_token_cache
from mcp_facture_electronique_fr.models.annuaire import (
    CreateCodeRoutageBody,
    CreateLigneAnnuaireBody,
    UpdatePatchCodeRoutageBody,
    UpdatePatchLigneAnnuaireBody,
    UpdatePutCodeRoutageBody,
    UpdatePutLigneAnnuaireBody,
)

logger = logging.getLogger(__name__)


class DirectoryClient(BaseEInvoicingClient):
    """Async client for the PPF Annuaire swagger v1.11.0.

    Shares its OAuth2 token cache with FlowClient to avoid redundant fetches.
    """

    def __init__(
        self,
        config: Optional[PAConfig] = None,
        token_cache: Optional[TokenCache] = None,
    ) -> None:
        cfg = config or get_config()
        self._organization_id: Optional[str] = cfg.pa_organization_id
        super().__init__(
            base_url=cfg.ppf_annuaire_base_url,
            auth_mode=AuthMode.OAUTH2_CLIENT_CREDENTIALS,
            oauth_config=cfg.to_oauth_config_directory(),
            token_cache=token_cache if token_cache is not None else get_shared_token_cache(),
            http_timeout=cfg.http_timeout,
        )

    async def _get_headers(self) -> dict[str, str]:
        headers = await super()._get_headers()
        if self._organization_id:
            headers["Organization-Id"] = self._organization_id
        return headers

    def _parse_error_body(self, response: httpx.Response) -> tuple[str, Optional[str]]:
        try:
            body = response.json()
            return body.get("errorMessage") or body.get("message") or "", body.get("errorCode")
        except Exception:
            return super()._parse_error_body(response)

    # ------------------------------------------------------------------
    # SIREN — Legal units
    # ------------------------------------------------------------------

    async def search_company(
        self,
        siren: Optional[str] = None,
        raison_sociale: Optional[str] = None,
        type_entite: Optional[str] = None,
        etat_administratif: Optional[str] = None,
        limite: int = 50,
        ignorer: int = 0,
    ) -> dict[str, Any]:
        """POST /siren/recherche — Search legal units (searchSiren)."""
        filtres: dict[str, Any] = {}
        if siren:
            filtres["siren"] = siren
        if raison_sociale:
            filtres["raisonSociale"] = raison_sociale
        if type_entite:
            filtres["typeEntite"] = type_entite
        if etat_administratif:
            filtres["etatAdministratif"] = etat_administratif
        body: dict[str, Any] = {"limite": limite, "ignorer": ignorer}
        if filtres:
            body["filtres"] = filtres
        response = await self._request("POST", "/siren/recherche", json=body)
        if response.status_code == 204:
            return {"total": 0}
        return response.json()

    async def get_company_by_siren(self, siren: str) -> dict[str, Any]:
        """GET /siren/code-insee:{siren} — Look up a legal unit by SIREN."""
        response = await self._request("GET", f"/siren/code-insee:{siren}")
        return response.json()

    async def get_company_by_id_instance(self, id_instance: str) -> dict[str, Any]:
        """GET /siren/id-instance:{id-instance} — Look up a legal unit by directory instance ID."""
        response = await self._request("GET", f"/siren/id-instance:{id_instance}")
        return response.json()

    # ------------------------------------------------------------------
    # SIRET — Establishments
    # ------------------------------------------------------------------

    async def search_establishment(
        self,
        siret: Optional[str] = None,
        siren: Optional[str] = None,
        denomination: Optional[str] = None,
        etat_administratif: Optional[str] = None,
        limite: int = 50,
        ignorer: int = 0,
    ) -> dict[str, Any]:
        """POST /siret/recherche — Search establishments (searchSiret)."""
        filtres: dict[str, Any] = {}
        if siret:
            filtres["siret"] = siret
        if siren:
            filtres["siren"] = siren
        if denomination:
            filtres["denomination"] = denomination
        if etat_administratif:
            filtres["etatAdministratif"] = etat_administratif
        body: dict[str, Any] = {"limite": limite, "ignorer": ignorer}
        if filtres:
            body["filtres"] = filtres
        response = await self._request("POST", "/siret/recherche", json=body)
        if response.status_code == 204:
            return {"total": 0}
        return response.json()

    async def get_establishment_by_siret(self, siret: str) -> dict[str, Any]:
        """GET /siret/code-insee:{siret} — Look up an establishment by SIRET."""
        response = await self._request("GET", f"/siret/code-insee:{siret}")
        return response.json()

    async def get_establishment_by_id_instance(self, id_instance: str) -> dict[str, Any]:
        """GET /siret/id-instance:{id-instance} — Look up an establishment by directory instance ID."""
        response = await self._request("GET", f"/siret/id-instance:{id_instance}")
        return response.json()

    # ------------------------------------------------------------------
    # Routing Code (code-routage)
    # ------------------------------------------------------------------

    async def search_routing_code(
        self,
        identifiant_routage: Optional[str] = None,
        siret: Optional[str] = None,
        libelle_code_routage: Optional[str] = None,
        etat_administratif: Optional[str] = None,
        limite: int = 50,
        ignorer: int = 0,
    ) -> dict[str, Any]:
        """POST /code-routage/recherche — Search routing codes (searchCodeRoutage)."""
        filtres: dict[str, Any] = {}
        if identifiant_routage:
            filtres["identifiantRoutage"] = identifiant_routage
        if siret:
            filtres["siret"] = siret
        if libelle_code_routage:
            filtres["libelleCodeRoutage"] = libelle_code_routage
        if etat_administratif:
            filtres["etatAdministratif"] = etat_administratif
        body: dict[str, Any] = {"limite": limite, "ignorer": ignorer}
        if filtres:
            body["filtres"] = filtres
        response = await self._request("POST", "/code-routage/recherche", json=body)
        if response.status_code == 204:
            return {"total": 0}
        return response.json()

    async def get_routing_code_by_siret_and_code(
        self, siret: str, identifiant_routage: str
    ) -> dict[str, Any]:
        """GET /code-routage/siret:{siret}/code:{identifiant-routage}."""
        response = await self._request(
            "GET", f"/code-routage/siret:{siret}/code:{identifiant_routage}"
        )
        return response.json()

    async def get_routing_code_by_id_instance(self, id_instance: str) -> dict[str, Any]:
        """GET /code-routage/id-instance:{id-instance}."""
        response = await self._request("GET", f"/code-routage/id-instance:{id_instance}")
        return response.json()

    async def create_routing_code(self, body: CreateCodeRoutageBody) -> dict[str, Any]:
        """POST /code-routage — Create a routing code (createCodeRoutageBody)."""
        response = await self._request(
            "POST", "/code-routage", json=body.model_dump(by_alias=True, exclude_none=True)
        )
        return response.json()

    async def update_routing_code(
        self, id_instance: str, body: UpdatePatchCodeRoutageBody
    ) -> dict[str, Any]:
        """PATCH /code-routage/id-instance:{id-instance} — Partial update (updatePatchCodeRoutageBody)."""
        response = await self._request(
            "PATCH",
            f"/code-routage/id-instance:{id_instance}",
            json=body.model_dump(by_alias=True, exclude_none=True),
        )
        if response.status_code == 204:
            return {"status": "updated", "idInstance": id_instance}
        return response.json()

    async def replace_routing_code(
        self, id_instance: str, body: UpdatePutCodeRoutageBody
    ) -> dict[str, Any]:
        """PUT /code-routage/id-instance:{id-instance} — Full replace (updatePutCodeRoutageBody)."""
        response = await self._request(
            "PUT",
            f"/code-routage/id-instance:{id_instance}",
            json=body.model_dump(by_alias=True, exclude_none=True),
        )
        if response.status_code == 204:
            return {"status": "replaced", "idInstance": id_instance}
        return response.json()

    # ------------------------------------------------------------------
    # Directory Line (ligne-annuaire)
    # ------------------------------------------------------------------

    async def search_directory_line(
        self,
        identifiant_adressage: Optional[str] = None,
        matricule_plateforme: Optional[str] = None,
        siren: Optional[str] = None,
        siret: Optional[str] = None,
        identifiant_routage: Optional[str] = None,
        limite: int = 50,
        ignorer: int = 0,
    ) -> dict[str, Any]:
        """POST /ligne-annuaire/recherche — Search directory lines (searchLigneAnnuaire)."""
        filtres: dict[str, Any] = {}
        if identifiant_adressage:
            filtres["identifiantAdressage"] = identifiant_adressage
        if matricule_plateforme:
            filtres["matriculePlateforme"] = matricule_plateforme
        if siren:
            filtres["siren"] = siren
        if siret:
            filtres["siret"] = siret
        if identifiant_routage:
            filtres["identifiantRoutage"] = identifiant_routage
        body: dict[str, Any] = {"limite": limite, "ignorer": ignorer}
        if filtres:
            body["filtres"] = filtres
        response = await self._request("POST", "/ligne-annuaire/recherche", json=body)
        if response.status_code == 204:
            return {"total": 0}
        return response.json()

    async def get_directory_line_by_code(self, identifiant_adressage: str) -> dict[str, Any]:
        """GET /ligne-annuaire/code:{identifiant-adressage}."""
        response = await self._request(
            "GET", f"/ligne-annuaire/code:{identifiant_adressage}"
        )
        return response.json()

    async def get_directory_line(self, id_instance: str) -> dict[str, Any]:
        """GET /ligne-annuaire/id-instance:{id-instance}."""
        response = await self._request("GET", f"/ligne-annuaire/id-instance:{id_instance}")
        return response.json()

    async def create_directory_line(self, body: CreateLigneAnnuaireBody) -> dict[str, Any]:
        """POST /ligne-annuaire — Create a directory line (createLigneAnnuaireBody)."""
        response = await self._request(
            "POST", "/ligne-annuaire", json=body.model_dump(by_alias=True, exclude_none=True)
        )
        return response.json()

    async def update_directory_line(
        self, id_instance: str, body: UpdatePatchLigneAnnuaireBody
    ) -> dict[str, Any]:
        """PATCH /ligne-annuaire/id-instance:{id-instance} — Partial update (updatePatchLigneAnnuaireBody)."""
        response = await self._request(
            "PATCH",
            f"/ligne-annuaire/id-instance:{id_instance}",
            json=body.model_dump(by_alias=True, exclude_none=True),
        )
        if response.status_code == 204:
            return {"status": "updated", "idInstance": id_instance}
        return response.json()

    async def replace_directory_line(
        self, id_instance: str, body: UpdatePutLigneAnnuaireBody
    ) -> dict[str, Any]:
        """PUT /ligne-annuaire/id-instance:{id-instance} — Full replace (updatePutLigneAnnuaireBody)."""
        response = await self._request(
            "PUT",
            f"/ligne-annuaire/id-instance:{id_instance}",
            json=body.model_dump(by_alias=True, exclude_none=True),
        )
        if response.status_code == 204:
            return {"status": "replaced", "idInstance": id_instance}
        return response.json()

    async def delete_directory_line(self, id_instance: str) -> dict[str, Any]:
        """DELETE /ligne-annuaire/id-instance:{id-instance}."""
        response = await self._request("DELETE", f"/ligne-annuaire/id-instance:{id_instance}")
        if response.status_code == 204:
            return {"status": "deleted", "idInstance": id_instance}
        return response.json()

    # ------------------------------------------------------------------
    # Healthcheck
    # ------------------------------------------------------------------

    async def check_health(self) -> dict[str, Any]:
        """GET /healthcheck — Check availability of the PPF Annuaire service."""
        response = await self._request("GET", "/healthcheck")
        try:
            return response.json()
        except Exception:
            return {"status": "ok", "http_status": response.status_code}
