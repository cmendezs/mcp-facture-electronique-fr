"""
MCP tools for the PPF Annuaire (directory) service.

Wired directly against the bundled PPF-platform swagger
`specs/dgfip/swagger/ppf-openapi-annuaire-api-public-1.11.0-openapi.json`
(v1.11.0) — a PPF-platform-specific tool set, not a PDP-agnostic XP Z12-013
Annex B Directory Service interface. Per the swagger's own `info.description`:
endpoints are subject to change and require prior PISTE application publication.

These tools allow Claude to query and maintain the PPF directory:
searching companies (SIREN), establishments (SIRET), routing codes
(code-routage), and directory lines (ligne-annuaire, electronic invoicing
receiving addresses).
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastmcp import FastMCP
from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from mcp_einvoicing_core.models import TaxIdentifier
from pydantic import Field

from mcp_facture_electronique_fr.clients.directory_client import DirectoryClient
from mcp_facture_electronique_fr.models.annuaire import (
    CreateCodeRoutageBody,
    CreateLigneAnnuaireBody,
    InformationAdressage,
    PeriodeEffet,
    UpdatePatchCodeRoutageBody,
    UpdatePatchLigneAnnuaireBody,
    UpdatePutCodeRoutageBody,
    UpdatePutLigneAnnuaireBody,
)

logger = logging.getLogger(__name__)


def _validate_siren(value: str) -> str:
    """Return the stripped SIREN or raise ValueError if invalid."""
    v = value.strip()
    ok, error = TaxIdentifier.validate_fr_siren(v)
    if not ok:
        raise ValueError(error)
    return v


def _validate_siret(value: str) -> str:
    """Return the stripped SIRET or raise ValueError if invalid."""
    v = value.strip()
    ok, error = TaxIdentifier.validate_fr_siret(v)
    if not ok:
        raise ValueError(error)
    return v


_directory_client: DirectoryClient | None = None


def get_directory_client() -> DirectoryClient:
    global _directory_client
    if _directory_client is None:
        _directory_client = DirectoryClient()
    return _directory_client


def register_directory_tools(mcp: FastMCP) -> None:
    """Registers the PPF Annuaire tools on the FastMCP instance."""

    # ------------------------------------------------------------------
    # SIREN — Legal units
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_company(
        raison_sociale: Annotated[
            str | None,
            Field(default=None, description="Legal/trade name (partial match). Use when the SIREN is unknown."),
        ] = None,
        siren: Annotated[
            str | None,
            Field(default=None, description="Exact SIREN (9 digits, no spaces)."),
        ] = None,
        type_entite: Annotated[
            str | None,
            Field(default=None, description="Entity type filter (typeEntite)."),
        ] = None,
        etat_administratif: Annotated[
            str | None,
            Field(default=None, description="Administrative status filter (etatAdministratif)."),
        ] = None,
        limite: Annotated[
            int, Field(default=50, ge=1, le=500, description="Maximum number of results (limite)."),
        ] = 50,
        ignorer: Annotated[
            int, Field(default=0, ge=0, description="Number of results to skip for pagination (ignorer)."),
        ] = 0,
    ) -> dict:
        """
        Search legal units (SIRENs) in the PPF Annuaire (POST /siren/recherche).

        A company must appear here before its establishments (SIRETs) or
        directory lines (ligne-annuaire) can be resolved. Prefer
        get_company_by_siren when the exact SIREN is already known.
        """
        if siren is not None:
            try:
                siren = _validate_siren(siren)
            except ValueError as exc:
                return {"error": str(exc)}
        client = get_directory_client()
        return await client.search_company(
            siren=siren,
            raison_sociale=raison_sociale,
            type_entite=type_entite,
            etat_administratif=etat_administratif,
            limite=limite,
            ignorer=ignorer,
        )

    @mcp.tool()
    async def get_company_by_siren(
        siren: Annotated[str, Field(description="Exact SIREN (9 digits, no spaces).")],
    ) -> dict:
        """Look up a legal unit by SIREN (GET /siren/code-insee:{siren})."""
        try:
            siren = _validate_siren(siren)
        except ValueError as exc:
            return {"error": str(exc)}
        client = get_directory_client()
        return await client.get_company_by_siren(siren=siren)

    @mcp.tool()
    async def get_company_by_id_instance(
        id_instance: Annotated[
            str,
            Field(description="Directory instance ID (idInstance) of the legal unit, from a previous search."),
        ],
    ) -> dict:
        """Look up a legal unit by directory instance ID (GET /siren/id-instance:{id-instance})."""
        client = get_directory_client()
        return await client.get_company_by_id_instance(id_instance=id_instance)

    # ------------------------------------------------------------------
    # SIRET — Establishments
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_establishment(
        siret: Annotated[
            str | None, Field(default=None, description="Exact SIRET (14 digits, no spaces).")
        ] = None,
        siren: Annotated[
            str | None, Field(default=None, description="Parent SIREN (9 digits). Lists all establishments.")
        ] = None,
        denomination: Annotated[
            str | None, Field(default=None, description="Establishment name (partial match).")
        ] = None,
        etat_administratif: Annotated[
            str | None, Field(default=None, description="Administrative status filter (etatAdministratif).")
        ] = None,
        limite: Annotated[
            int, Field(default=50, ge=1, le=500, description="Maximum number of results (limite).")
        ] = 50,
        ignorer: Annotated[
            int, Field(default=0, ge=0, description="Number of results to skip for pagination (ignorer).")
        ] = 0,
    ) -> dict:
        """Search establishments (SIRETs) in the PPF Annuaire (POST /siret/recherche)."""
        if siren is not None:
            try:
                siren = _validate_siren(siren)
            except ValueError as exc:
                return {"error": str(exc)}
        if siret is not None:
            try:
                siret = _validate_siret(siret)
            except ValueError as exc:
                return {"error": str(exc)}
        client = get_directory_client()
        return await client.search_establishment(
            siret=siret,
            siren=siren,
            denomination=denomination,
            etat_administratif=etat_administratif,
            limite=limite,
            ignorer=ignorer,
        )

    @mcp.tool()
    async def get_establishment_by_siret(
        siret: Annotated[str, Field(description="Exact SIRET (14 digits, no spaces).")],
    ) -> dict:
        """Look up an establishment by SIRET (GET /siret/code-insee:{siret})."""
        try:
            siret = _validate_siret(siret)
        except ValueError as exc:
            return {"error": str(exc)}
        client = get_directory_client()
        return await client.get_establishment_by_siret(siret=siret)

    @mcp.tool()
    async def get_establishment_by_id_instance(
        id_instance: Annotated[
            str,
            Field(description="Directory instance ID (idInstance) of the establishment, from a previous search."),
        ],
    ) -> dict:
        """Look up an establishment by directory instance ID (GET /siret/id-instance:{id-instance})."""
        client = get_directory_client()
        return await client.get_establishment_by_id_instance(id_instance=id_instance)

    # ------------------------------------------------------------------
    # Routing Code (code-routage)
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_routing_code(
        identifiant_routage: Annotated[
            str | None, Field(default=None, description="Exact routing-code identifier (identifiantRoutage).")
        ] = None,
        siret: Annotated[
            str | None, Field(default=None, description="Establishment SIRET (14 digits).")
        ] = None,
        libelle_code_routage: Annotated[
            str | None, Field(default=None, description="Routing code label (partial match).")
        ] = None,
        etat_administratif: Annotated[
            str | None, Field(default=None, description="'A' (active) or 'F' (closed).")
        ] = None,
        limite: Annotated[
            int, Field(default=50, ge=1, le=500, description="Maximum number of results (limite).")
        ] = 50,
        ignorer: Annotated[
            int, Field(default=0, ge=0, description="Number of results to skip for pagination (ignorer).")
        ] = 0,
    ) -> dict:
        """Search routing codes (POST /code-routage/recherche)."""
        if siret is not None:
            try:
                siret = _validate_siret(siret)
            except ValueError as exc:
                return {"error": str(exc)}
        client = get_directory_client()
        return await client.search_routing_code(
            identifiant_routage=identifiant_routage,
            siret=siret,
            libelle_code_routage=libelle_code_routage,
            etat_administratif=etat_administratif,
            limite=limite,
            ignorer=ignorer,
        )

    @mcp.tool()
    async def get_routing_code_by_siret_and_code(
        siret: Annotated[str, Field(description="Establishment SIRET (14 digits).")],
        identifiant_routage: Annotated[str, Field(description="Routing-code identifier (identifiantRoutage).")],
    ) -> dict:
        """Look up a routing code by SIRET and code (GET /code-routage/siret:{siret}/code:{identifiant-routage})."""
        try:
            siret = _validate_siret(siret)
        except ValueError as exc:
            return {"error": str(exc)}
        client = get_directory_client()
        return await client.get_routing_code_by_siret_and_code(
            siret=siret, identifiant_routage=identifiant_routage
        )

    @mcp.tool()
    async def get_routing_code_by_id_instance(
        id_instance: Annotated[
            str, Field(description="Directory instance ID (idInstance) of the routing code.")
        ],
    ) -> dict:
        """Look up a routing code by directory instance ID (GET /code-routage/id-instance:{id-instance})."""
        client = get_directory_client()
        return await client.get_routing_code_by_id_instance(id_instance=id_instance)

    @mcp.tool()
    async def create_routing_code(
        siret: Annotated[str, Field(description="Establishment SIRET (14 digits) this routing code belongs to.")],
        identifiant_routage: Annotated[
            str, Field(description="Routing-code identifier to create (max 100 chars, pattern [-_/@a-zA-Z0-9]).")
        ],
        type_identifiant_routage: Annotated[
            str, Field(description="4-digit type code for the routing-code identifier (typeIdentifiantRoutage).")
        ],
        libelle_code_routage: Annotated[str, Field(description="Human-readable label for the routing code.")],
        nature_etablissement: Annotated[
            Literal["Privé", "Public"], Field(description="Whether the establishment is private or public.")
        ],
        etat_administratif: Annotated[
            Literal["A", "F"], Field(description="'A' (active) or 'F' (closed).")
        ] = "A",
        gestion_engagement_juridique: Annotated[
            bool | None,
            Field(default=None, description="Whether a legal-commitment number (engagement juridique) is mandatory."),
        ] = None,
        confirmation_token: Annotated[
            str | None,
            Field(default=None, description="Confirmation token from a previous call. Omit on the first call."),
        ] = None,
    ) -> dict:
        """
        Create a routing code (POST /code-routage).

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")
        try:
            siret = _validate_siret(siret)
        except ValueError as exc:
            return {"error": str(exc)}

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="create_routing_code",
                summary=f"Create routing code {identifiant_routage!r} on SIRET {siret!r}.",
                token=confirmation_token,
            )

        body = CreateCodeRoutageBody(
            nature_etablissement=nature_etablissement,
            identifiant_routage=identifiant_routage,
            siret=siret,
            type_identifiant_routage=type_identifiant_routage,
            libelle_code_routage=libelle_code_routage,
            gestion_engagement_juridique=gestion_engagement_juridique,
            etat_administratif=etat_administratif,
        )
        client = get_directory_client()
        result = await client.create_routing_code(body)
        gate.consume(confirmation_token)
        return result

    @mcp.tool()
    async def update_routing_code(
        id_instance: Annotated[str, Field(description="Directory instance ID (idInstance) of the routing code.")],
        type_identifiant_routage: Annotated[
            str | None, Field(default=None, description="New 4-digit type code. Omit to leave unchanged.")
        ] = None,
        libelle_code_routage: Annotated[
            str | None, Field(default=None, description="New label. Omit to leave unchanged.")
        ] = None,
        etat_administratif: Annotated[
            Literal["A", "F"] | None, Field(default=None, description="New status. Omit to leave unchanged.")
        ] = None,
    ) -> dict:
        """
        Partially update a routing code (PATCH /code-routage/id-instance:{id-instance}).
        Only provided fields are modified.
        """
        assert_not_read_only("FR_READ_ONLY")
        body = UpdatePatchCodeRoutageBody(
            type_identifiant_routage=type_identifiant_routage,
            libelle_code_routage=libelle_code_routage,
            etat_administratif=etat_administratif,
        )
        client = get_directory_client()
        return await client.update_routing_code(id_instance=id_instance, body=body)

    @mcp.tool()
    async def replace_routing_code(
        id_instance: Annotated[str, Field(description="Directory instance ID (idInstance) of the routing code.")],
        type_identifiant_routage: Annotated[str, Field(description="4-digit type code (typeIdentifiantRoutage).")],
        libelle_code_routage: Annotated[str, Field(description="Label for the routing code.")],
        etat_administratif: Annotated[Literal["A", "F"], Field(description="'A' (active) or 'F' (closed).")],
        confirmation_token: Annotated[
            str | None,
            Field(default=None, description="Confirmation token from a previous call. Omit on the first call."),
        ] = None,
    ) -> dict:
        """
        Fully replace a routing code (PUT /code-routage/id-instance:{id-instance}).
        Unlike update_routing_code, all fields are required and replace the
        existing object entirely.

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="replace_routing_code",
                summary=f"Replace routing code {id_instance!r} entirely.",
                token=confirmation_token,
            )

        body = UpdatePutCodeRoutageBody(
            type_identifiant_routage=type_identifiant_routage,
            libelle_code_routage=libelle_code_routage,
            etat_administratif=etat_administratif,
        )
        client = get_directory_client()
        result = await client.replace_routing_code(id_instance=id_instance, body=body)
        gate.consume(confirmation_token)
        return result

    # ------------------------------------------------------------------
    # Directory Line (ligne-annuaire)
    # ------------------------------------------------------------------

    @mcp.tool()
    async def search_directory_line(
        identifiant_adressage: Annotated[
            str | None, Field(default=None, description="Exact addressing identifier (identifiantAdressage).")
        ] = None,
        matricule_plateforme: Annotated[
            str | None, Field(default=None, description="4-digit Approved Platform registration number.")
        ] = None,
        siren: Annotated[str | None, Field(default=None, description="SIREN (9 digits).")] = None,
        siret: Annotated[str | None, Field(default=None, description="SIRET (14 digits).")] = None,
        identifiant_routage: Annotated[
            str | None, Field(default=None, description="Routing-code identifier.")
        ] = None,
        limite: Annotated[
            int, Field(default=50, ge=1, le=500, description="Maximum number of results (limite).")
        ] = 50,
        ignorer: Annotated[
            int, Field(default=0, ge=0, description="Number of results to skip for pagination (ignorer).")
        ] = 0,
    ) -> dict:
        """
        Search directory lines (electronic invoice receiving addresses)
        (POST /ligne-annuaire/recherche).

        Call before sending an invoice to verify the recipient has a
        registered line and to identify their Approved Platform.
        """
        if siren is not None:
            try:
                siren = _validate_siren(siren)
            except ValueError as exc:
                return {"error": str(exc)}
        if siret is not None:
            try:
                siret = _validate_siret(siret)
            except ValueError as exc:
                return {"error": str(exc)}
        client = get_directory_client()
        return await client.search_directory_line(
            identifiant_adressage=identifiant_adressage,
            matricule_plateforme=matricule_plateforme,
            siren=siren,
            siret=siret,
            identifiant_routage=identifiant_routage,
            limite=limite,
            ignorer=ignorer,
        )

    @mcp.tool()
    async def get_directory_line_by_code(
        identifiant_adressage: Annotated[str, Field(description="Addressing identifier (identifiantAdressage).")],
    ) -> dict:
        """Look up a directory line by addressing code (GET /ligne-annuaire/code:{identifiant-adressage})."""
        client = get_directory_client()
        return await client.get_directory_line_by_code(identifiant_adressage=identifiant_adressage)

    @mcp.tool()
    async def get_directory_line(
        id_instance: Annotated[str, Field(description="Directory instance ID (idInstance) of the directory line.")],
    ) -> dict:
        """Look up a directory line by directory instance ID (GET /ligne-annuaire/id-instance:{id-instance})."""
        client = get_directory_client()
        return await client.get_directory_line(id_instance=id_instance)

    @mcp.tool()
    async def create_directory_line(
        siren: Annotated[str, Field(description="SIREN of the taxable entity creating this receiving address.")],
        matricule_plateforme: Annotated[
            str, Field(description="4-digit Approved Platform registration number receiving the invoices.")
        ],
        date_debut_effet: Annotated[str, Field(description="Effective start date, ISO YYYY-MM-DD (dateDebutEffet).")],
        siret: Annotated[
            str | None,
            Field(default=None, description="Specific establishment SIRET. If absent, applies to the whole SIREN."),
        ] = None,
        identifiant_routage: Annotated[
            str | None, Field(default=None, description="Routing-code identifier to refine the address.")
        ] = None,
        suffixe_adressage: Annotated[
            str | None, Field(default=None, description="Addressing suffix (suffixeAdressage).")
        ] = None,
        date_fin_effet: Annotated[
            str | None, Field(default=None, description="Effective end date, ISO YYYY-MM-DD, if known.")
        ] = None,
        confirmation_token: Annotated[
            str | None,
            Field(default=None, description="Confirmation token from a previous call. Omit on the first call."),
        ] = None,
    ) -> dict:
        """
        Create a directory line (electronic invoice receiving address)
        (POST /ligne-annuaire).

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")
        try:
            siren = _validate_siren(siren)
        except ValueError as exc:
            return {"error": str(exc)}
        if siret is not None:
            try:
                siret = _validate_siret(siret)
            except ValueError as exc:
                return {"error": str(exc)}

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="create_directory_line",
                summary=f"Create directory line for SIREN {siren!r} -> platform {matricule_plateforme!r}.",
                token=confirmation_token,
            )

        body = CreateLigneAnnuaireBody(
            periode_effet=PeriodeEffet(date_debut_effet=date_debut_effet, date_fin_effet=date_fin_effet),
            information_adressage=InformationAdressage(
                siren=siren,
                siret=siret,
                identifiant_routage=identifiant_routage,
                suffixe_adressage=suffixe_adressage,
                matricule_plateforme=matricule_plateforme,
            ),
        )
        client = get_directory_client()
        result = await client.create_directory_line(body)
        gate.consume(confirmation_token)
        return result

    @mcp.tool()
    async def update_directory_line(
        id_instance: Annotated[str, Field(description="Directory instance ID (idInstance) of the directory line.")],
        matricule_plateforme: Annotated[
            str | None, Field(default=None, description="New Approved Platform registration number.")
        ] = None,
        date_fin_effet: Annotated[
            str | None, Field(default=None, description="New effective end date, ISO YYYY-MM-DD.")
        ] = None,
    ) -> dict:
        """
        Partially update a directory line (PATCH /ligne-annuaire/id-instance:{id-instance}).
        Only provided fields are modified.
        """
        assert_not_read_only("FR_READ_ONLY")
        body = UpdatePatchLigneAnnuaireBody(
            matricule_plateforme=matricule_plateforme, date_fin_effet=date_fin_effet
        )
        client = get_directory_client()
        return await client.update_directory_line(id_instance=id_instance, body=body)

    @mcp.tool()
    async def replace_directory_line(
        id_instance: Annotated[str, Field(description="Directory instance ID (idInstance) of the directory line.")],
        matricule_plateforme: Annotated[str, Field(description="Approved Platform registration number.")],
        date_fin_effet: Annotated[
            str | None, Field(default=None, description="Effective end date, ISO YYYY-MM-DD, if any.")
        ] = None,
        confirmation_token: Annotated[
            str | None,
            Field(default=None, description="Confirmation token from a previous call. Omit on the first call."),
        ] = None,
    ) -> dict:
        """
        Fully replace a directory line (PUT /ligne-annuaire/id-instance:{id-instance}).

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="replace_directory_line",
                summary=f"Replace directory line {id_instance!r} entirely.",
                token=confirmation_token,
            )

        body = UpdatePutLigneAnnuaireBody(
            matricule_plateforme=matricule_plateforme, date_fin_effet=date_fin_effet
        )
        client = get_directory_client()
        result = await client.replace_directory_line(id_instance=id_instance, body=body)
        gate.consume(confirmation_token)
        return result

    @mcp.tool()
    async def delete_directory_line(
        id_instance: Annotated[
            str,
            Field(
                description=(
                    "Directory instance ID (idInstance) of the directory line to delete. "
                    "WARNING: this action is permanent. After deletion, senders will no "
                    "longer be able to send invoices via this address."
                )
            ),
        ],
        confirmation_token: Annotated[
            str | None,
            Field(default=None, description="Confirmation token from a previous call. Omit on the first call."),
        ] = None,
    ) -> dict:
        """
        Delete a directory line (DELETE /ligne-annuaire/id-instance:{id-instance}).

        HUMAN-IN-THE-LOOP: Requires user confirmation. Call without confirmation_token
        first, show the summary to the user, then call again with the token.
        """
        assert_not_read_only("FR_READ_ONLY")

        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="delete_directory_line",
                summary=f"Delete directory line {id_instance!r}. This is irreversible.",
                token=confirmation_token,
            )

        client = get_directory_client()
        result = await client.delete_directory_line(id_instance=id_instance)
        gate.consume(confirmation_token)
        return result

    # ------------------------------------------------------------------
    # Healthcheck
    # ------------------------------------------------------------------

    @mcp.tool()
    async def check_ppf_annuaire_health() -> dict:
        """
        Check the availability of the PPF Annuaire service (GET /healthcheck).
        Use before a directory-management session to ensure the service is reachable.
        """
        client = get_directory_client()
        return await client.check_health()
