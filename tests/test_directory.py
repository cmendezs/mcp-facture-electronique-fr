"""
Unit tests for the Directory Service (clients/directory_client.py).

HTTP calls are mocked via respx.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from clients.directory_client import DirectoryClient
from config import PAConfig
from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import TokenCache

FAKE_TOKEN = "eyJhbGciOiJSUzI1NiJ9.fake.token"
DIR_BASE_URL = "https://api.directory.test-pa.fr/directory-service"
TOKEN_URL = "https://auth.test-pa.fr/oauth/token"


def _make_token_response() -> dict:
    return {"access_token": FAKE_TOKEN, "token_type": "Bearer", "expires_in": 3600}


@pytest.fixture
def pa_config() -> PAConfig:
    return PAConfig(
        pa_base_url_flow="https://api.flow.test-pa.fr/flow-service",
        pa_base_url_directory=DIR_BASE_URL,
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
# Tests: search_company
# ---------------------------------------------------------------------------


class TestSearchCompany:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_siren(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            "companies": [{"siren": "123456789", "name": "ACME SAS", "status": "Active"}],
            "total": 1,
        }
        respx.post(f"{DIR_BASE_URL}/v1/siren/search").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.search_company(siren="123456789")

        assert result["total"] == 1
        assert result["companies"][0]["siren"] == "123456789"

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_name(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"companies": [], "total": 0}
        respx.post(f"{DIR_BASE_URL}/v1/siren/search").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.search_company(name="Unknown Company")

        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Tests: get_company_by_siren
# ---------------------------------------------------------------------------


class TestGetCompanyBySiren:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_existing_company(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            "siren": "123456789",
            "name": "ACME SAS",
            "status": "Active",
            "platformId": "PA-001",
        }
        respx.get(f"{DIR_BASE_URL}/v1/siren/code-insee:123456789").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.get_company_by_siren("123456789")

        assert result["siren"] == "123456789"
        assert result["platformId"] == "PA-001"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_company_404(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{DIR_BASE_URL}/v1/siren/code-insee:000000000").mock(
            return_value=httpx.Response(404, json={"detail": "SIREN not found"})
        )

        with pytest.raises(PlatformError) as exc_info:
            await directory_client.get_company_by_siren("000000000")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: get_establishment_by_siret
# ---------------------------------------------------------------------------


class TestGetEstablishmentBySiret:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_existing_establishment(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            "siret": "12345678900012",
            "siren": "123456789",
            "name": "ACME SAS - HQ",
            "status": "Active",
        }
        respx.get(f"{DIR_BASE_URL}/v1/siret/code-insee:12345678900012").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.get_establishment_by_siret("12345678900012")

        assert result["siret"] == "12345678900012"
        assert result["status"] == "Active"


# ---------------------------------------------------------------------------
# Tests: Directory Line CRUD
# ---------------------------------------------------------------------------


class TestDirectoryLine:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_directory_line_by_siren(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            "addressingIdentifier": "123456789",
            "siren": "123456789",
            "platformId": "PA-001",
            "status": "Active",
        }
        respx.get(f"{DIR_BASE_URL}/v1/directory-line/code:123456789").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.get_directory_line("123456789")

        assert result["addressingIdentifier"] == "123456789"
        assert result["platformId"] == "PA-001"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_directory_line(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            "instanceId": "DL-001",
            "siren": "123456789",
            "platformId": "PA-001",
            "status": "Active",
        }
        respx.post(f"{DIR_BASE_URL}/v1/directory-line").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await directory_client.create_directory_line(
            siren="123456789",
            platform_id="PA-001",
        )

        assert result["instanceId"] == "DL-001"

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_directory_line_204(self, directory_client: DirectoryClient):
        """DELETE returning 204 No Content is handled cleanly."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.delete(f"{DIR_BASE_URL}/v1/directory-line/id-instance:DL-001").mock(
            return_value=httpx.Response(204, content=b"")
        )

        result = await directory_client.delete_directory_line("DL-001")

        assert result["deleted"] is True
        assert result["instanceId"] == "DL-001"

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_directory_line_patch(self, directory_client: DirectoryClient):
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"instanceId": "DL-001", "platformId": "PA-002", "status": "Active"}
        respx.patch(f"{DIR_BASE_URL}/v1/directory-line/id-instance:DL-001").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await directory_client.update_directory_line(
            instance_id="DL-001",
            platform_id="PA-002",
        )

        assert result["platformId"] == "PA-002"
