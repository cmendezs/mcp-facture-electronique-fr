"""
Unit tests for the PPF Annuaire directory client (clients/directory_client.py).

Wired against the bundled swagger
specs/dgfip/swagger/ppf-openapi-annuaire-api-public-1.11.0-openapi.json.
HTTP calls are mocked via respx.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import TokenCache

from mcp_facture_electronique_fr.clients.directory_client import DirectoryClient
from mcp_facture_electronique_fr.config import PAConfig
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
from mcp_facture_electronique_fr.tools.directory_tools import _validate_siren, _validate_siret

FAKE_TOKEN = "eyJhbGciOiJSUzI1NiJ9.fake.token"
ANNUAIRE_BASE_URL = "https://api.annuaire.test-pa.fr/v1"
TOKEN_URL = "https://auth.test-pa.fr/oauth/token"


def _make_token_response() -> dict:
    return {"access_token": FAKE_TOKEN, "token_type": "Bearer", "expires_in": 3600}


@pytest.fixture
def pa_config() -> PAConfig:
    return PAConfig(
        pa_base_url_flow="https://api.flow.test-pa.fr/flow-service",
        pa_base_url_directory=None,
        ppf_annuaire_base_url=ANNUAIRE_BASE_URL,
        pa_client_id="test-client-id",
        pa_client_secret="test-client-secret",
        pa_token_url=TOKEN_URL,
        http_timeout=5.0,
    )


@pytest.fixture
def token_cache() -> TokenCache:
    return TokenCache()


@pytest.fixture
def directory_client(pa_config: PAConfig, token_cache: TokenCache) -> DirectoryClient:
    return DirectoryClient(config=pa_config, token_cache=token_cache)


# ---------------------------------------------------------------------------
# Tests: config wiring
# ---------------------------------------------------------------------------


def test_directory_client_uses_ppf_annuaire_base_url(directory_client: DirectoryClient):
    assert directory_client._base_url == ANNUAIRE_BASE_URL


def test_ppf_annuaire_base_url_default_matches_swagger_servers_block():
    cfg = PAConfig(
        pa_base_url_flow="https://api.flow.test-pa.fr/flow-service",
        pa_client_id="x",
        pa_client_secret="x",
        pa_token_url=TOKEN_URL,
    )
    assert cfg.ppf_annuaire_base_url == "https://aife.economie.gouv.fr/ppf/annuaire-public/v1"


# ---------------------------------------------------------------------------
# Tests: search_company (POST /siren/recherche)
# ---------------------------------------------------------------------------


class TestSearchCompany:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_siren(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"resultats": [{"siren": "732829320", "raisonSociale": "ACME SAS"}], "total": 1}
        respx.post(f"{ANNUAIRE_BASE_URL}/siren/recherche").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.search_company(siren="732829320")

        assert result["total"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_name(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{ANNUAIRE_BASE_URL}/siren/recherche").mock(
            return_value=httpx.Response(200, json={"resultats": [], "total": 0})
        )

        result = await directory_client.search_company(raison_sociale="Unknown Company")

        assert result["total"] == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_204_returns_zero_total(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{ANNUAIRE_BASE_URL}/siren/recherche").mock(return_value=httpx.Response(204))

        result = await directory_client.search_company(siren="732829320")

        assert result == {"total": 0}


# ---------------------------------------------------------------------------
# Tests: get_company_by_siren / get_company_by_id_instance
# ---------------------------------------------------------------------------


class TestGetCompany:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_siren(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"siren": "732829320", "raisonSociale": "ACME SAS", "idInstance": 120}
        respx.get(f"{ANNUAIRE_BASE_URL}/siren/code-insee:732829320").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.get_company_by_siren("732829320")

        assert result["siren"] == "732829320"
        assert result["idInstance"] == 120

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_siren_404(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/siren/code-insee:000000000").mock(
            return_value=httpx.Response(404, json={"detail": "SIREN not found"})
        )

        with pytest.raises(PlatformError) as exc_info:
            await directory_client.get_company_by_siren("000000000")

        assert exc_info.value.status_code == 404

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_id_instance(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/siren/id-instance:120").mock(
            return_value=httpx.Response(200, json={"siren": "732829320", "idInstance": 120})
        )

        result = await directory_client.get_company_by_id_instance("120")

        assert result["idInstance"] == 120


# ---------------------------------------------------------------------------
# Tests: SIRET (search_establishment / get_establishment_by_siret / by id-instance)
# ---------------------------------------------------------------------------


class TestEstablishment:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_siret(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"siret": "73282932073006", "siren": "732829320", "denomination": "ACME SAS - HQ"}
        respx.get(f"{ANNUAIRE_BASE_URL}/siret/code-insee:73282932073006").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.get_establishment_by_siret("73282932073006")

        assert result["siret"] == "73282932073006"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_id_instance(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/siret/id-instance:200").mock(
            return_value=httpx.Response(200, json={"siret": "73282932073006", "idInstance": 200})
        )

        result = await directory_client.get_establishment_by_id_instance("200")

        assert result["idInstance"] == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_search(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{ANNUAIRE_BASE_URL}/siret/recherche").mock(
            return_value=httpx.Response(200, json={"resultats": [], "total": 0})
        )

        result = await directory_client.search_establishment(siren="732829320")

        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Tests: Routing code (code-routage) CRUD
# ---------------------------------------------------------------------------


class TestRoutingCode:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{ANNUAIRE_BASE_URL}/code-routage/recherche").mock(
            return_value=httpx.Response(200, json={"resultats": [], "total": 0})
        )

        result = await directory_client.search_routing_code(siret="73282932073006")

        assert result["total"] == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_siret_and_code(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/code-routage/siret:73282932073006/code:ROUTE1").mock(
            return_value=httpx.Response(200, json={"identifiantRoutage": "ROUTE1"})
        )

        result = await directory_client.get_routing_code_by_siret_and_code(
            "73282932073006", "ROUTE1"
        )

        assert result["identifiantRoutage"] == "ROUTE1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_id_instance(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/code-routage/id-instance:300").mock(
            return_value=httpx.Response(200, json={"idInstance": 300})
        )

        result = await directory_client.get_routing_code_by_id_instance("300")

        assert result["idInstance"] == 300

    @respx.mock
    @pytest.mark.asyncio
    async def test_create(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        route = respx.post(f"{ANNUAIRE_BASE_URL}/code-routage").mock(
            return_value=httpx.Response(201, json={"idInstance": 301})
        )

        body = CreateCodeRoutageBody(
            nature_etablissement="Privé",
            identifiant_routage="ROUTE1",
            siret="73282932073006",
            type_identifiant_routage="0224",
            libelle_code_routage="Comptabilité",
            etat_administratif="A",
        )
        result = await directory_client.create_routing_code(body)

        assert result["idInstance"] == 301
        sent = route.calls.last.request
        import json as _json

        payload = _json.loads(sent.content)
        assert payload["natureEtablissement"] == "Privé"
        assert payload["identifiantRoutage"] == "ROUTE1"
        assert "gestionEngagementJuridique" not in payload

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_patch(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.patch(f"{ANNUAIRE_BASE_URL}/code-routage/id-instance:301").mock(
            return_value=httpx.Response(204)
        )

        body = UpdatePatchCodeRoutageBody(libelle_code_routage="Nouveau libellé")
        result = await directory_client.update_routing_code("301", body)

        assert result == {"status": "updated", "idInstance": "301"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_replace_put(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.put(f"{ANNUAIRE_BASE_URL}/code-routage/id-instance:301").mock(
            return_value=httpx.Response(204)
        )

        body = UpdatePutCodeRoutageBody(
            type_identifiant_routage="0224", libelle_code_routage="Libellé", etat_administratif="A"
        )
        result = await directory_client.replace_routing_code("301", body)

        assert result == {"status": "replaced", "idInstance": "301"}


# ---------------------------------------------------------------------------
# Tests: Directory line (ligne-annuaire) CRUD
# ---------------------------------------------------------------------------


class TestDirectoryLine:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_code(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"identifiantAdressage": "732829320", "matriculePlateforme": "0145"}
        respx.get(f"{ANNUAIRE_BASE_URL}/ligne-annuaire/code:732829320").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.get_directory_line_by_code("732829320")

        assert result["identifiantAdressage"] == "732829320"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_by_id_instance(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/ligne-annuaire/id-instance:400").mock(
            return_value=httpx.Response(200, json={"idInstance": 400})
        )

        result = await directory_client.get_directory_line("400")

        assert result["idInstance"] == 400

    @respx.mock
    @pytest.mark.asyncio
    async def test_create(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        route = respx.post(f"{ANNUAIRE_BASE_URL}/ligne-annuaire").mock(
            return_value=httpx.Response(201, json={"idInstance": 401})
        )

        body = CreateLigneAnnuaireBody(
            periode_effet=PeriodeEffet(date_debut_effet="2026-08-01"),
            information_adressage=InformationAdressage(
                siren="732829320", matricule_plateforme="0145"
            ),
        )
        result = await directory_client.create_directory_line(body)

        assert result["idInstance"] == 401
        sent = route.calls.last.request
        import json as _json

        payload = _json.loads(sent.content)
        assert payload["periodeEffet"]["dateDebutEffet"] == "2026-08-01"
        assert payload["informationAdressage"]["matriculePlateforme"] == "0145"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_patch(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.patch(f"{ANNUAIRE_BASE_URL}/ligne-annuaire/id-instance:401").mock(
            return_value=httpx.Response(204)
        )

        body = UpdatePatchLigneAnnuaireBody(matricule_plateforme="0146")
        result = await directory_client.update_directory_line("401", body)

        assert result == {"status": "updated", "idInstance": "401"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_replace_put(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.put(f"{ANNUAIRE_BASE_URL}/ligne-annuaire/id-instance:401").mock(
            return_value=httpx.Response(204)
        )

        body = UpdatePutLigneAnnuaireBody(matricule_plateforme="0146")
        result = await directory_client.replace_directory_line("401", body)

        assert result == {"status": "replaced", "idInstance": "401"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.delete(f"{ANNUAIRE_BASE_URL}/ligne-annuaire/id-instance:401").mock(
            return_value=httpx.Response(204)
        )

        result = await directory_client.delete_directory_line("401")

        assert result == {"status": "deleted", "idInstance": "401"}


# ---------------------------------------------------------------------------
# Tests: healthcheck
# ---------------------------------------------------------------------------


class TestHealthcheck:
    @respx.mock
    @pytest.mark.asyncio
    async def test_check_health(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{ANNUAIRE_BASE_URL}/healthcheck").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        result = await directory_client.check_health()

        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests: FR-2 — _parse_error_body override in DirectoryClient
# ---------------------------------------------------------------------------


class TestDirectoryClientParseErrorBody:
    @respx.mock
    @pytest.mark.asyncio
    async def test_422_errorCode_errorMessage_parsed(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{ANNUAIRE_BASE_URL}/siren/recherche").mock(
            return_value=httpx.Response(
                422,
                json={"errorCode": "ERR_SIREN_NOT_FOUND", "errorMessage": "SIREN does not exist"},
            )
        )

        with pytest.raises(PlatformError) as exc_info:
            await directory_client.search_company(raison_sociale="Acme")

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_code == "ERR_SIREN_NOT_FOUND"
        assert "SIREN does not exist" in str(exc_info.value)

    @respx.mock
    @pytest.mark.asyncio
    async def test_non_json_error_falls_back(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{ANNUAIRE_BASE_URL}/siren/recherche").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        with pytest.raises(PlatformError) as exc_info:
            await directory_client.search_company(raison_sociale="Acme")

        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Tests: SIREN/SIRET validation wrappers (delegate to core TaxIdentifier)
# ---------------------------------------------------------------------------


class TestValidateSiren:
    def test_valid_siren_passes(self):
        assert _validate_siren("732829320") == "732829320"

    def test_strips_whitespace(self):
        assert _validate_siren("  732829320  ") == "732829320"

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="9 digits"):
            _validate_siren("12345678")

    def test_bad_check_digit_raises(self):
        with pytest.raises(ValueError, match="Luhn"):
            _validate_siren("123456780")


class TestValidateSiret:
    def test_valid_siret_passes(self):
        assert _validate_siret("73282932073006") == "73282932073006"

    def test_strips_whitespace(self):
        assert _validate_siret("  73282932073006  ") == "73282932073006"

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="14 digits"):
            _validate_siret("1234567890123")

    def test_bad_check_digit_raises(self):
        with pytest.raises(ValueError, match="Luhn"):
            _validate_siret("73282932073000")
