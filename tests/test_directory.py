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
from tools.directory_tools import _luhn_ok, _validate_siren, _validate_siret

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

    @pytest.mark.asyncio
    async def test_create_directory_line_raises(self, directory_client: DirectoryClient):
        """create_directory_line raises NotImplementedError (removed in v1.2.0)."""
        with pytest.raises(NotImplementedError, match="v1.2.0"):
            await directory_client.create_directory_line(
                siren="123456789",
                platform_id="PA-001",
            )

    @pytest.mark.asyncio
    async def test_delete_directory_line_raises(self, directory_client: DirectoryClient):
        """delete_directory_line raises NotImplementedError (removed in v1.2.0)."""
        with pytest.raises(NotImplementedError, match="v1.2.0"):
            await directory_client.delete_directory_line("DL-001")

    @pytest.mark.asyncio
    async def test_update_directory_line_raises(self, directory_client: DirectoryClient):
        """update_directory_line raises NotImplementedError (removed in v1.2.0)."""
        with pytest.raises(NotImplementedError, match="v1.2.0"):
            await directory_client.update_directory_line(
                instance_id="DL-001",
                platform_id="PA-002",
            )


# ---------------------------------------------------------------------------
# Tests: FR-2 — _parse_error_body override in DirectoryClient
# ---------------------------------------------------------------------------


class TestDirectoryClientParseErrorBody:
    @respx.mock
    @pytest.mark.asyncio
    async def test_422_errorCode_errorMessage_parsed(self, directory_client: DirectoryClient):
        """A 422 with errorCode/errorMessage is surfaced correctly by DirectoryClient."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{DIR_BASE_URL}/v1/siren/search").mock(
            return_value=httpx.Response(
                422,
                json={"errorCode": "ERR_SIREN_NOT_FOUND", "errorMessage": "SIREN does not exist"},
            )
        )

        with pytest.raises(PlatformError) as exc_info:
            await directory_client.search_company(name="Acme")

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_code == "ERR_SIREN_NOT_FOUND"
        assert "SIREN does not exist" in str(exc_info.value)

    @respx.mock
    @pytest.mark.asyncio
    async def test_non_json_error_falls_back(self, directory_client: DirectoryClient):
        """A non-JSON error body falls back to the base implementation."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{DIR_BASE_URL}/v1/siren/search").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        with pytest.raises(PlatformError) as exc_info:
            await directory_client.search_company(name="Acme")

        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Tests: FR-4 — Luhn validators (_validate_siren, _validate_siret)
# ---------------------------------------------------------------------------


class TestLuhnOk:
    def test_valid_siren_luhn(self):
        assert _luhn_ok("732829320") is True

    def test_invalid_luhn_all_zeros_except_last(self):
        assert _luhn_ok("000000001") is False

    def test_all_zeros_valid_luhn(self):
        assert _luhn_ok("000000000") is True


class TestValidateSiren:
    def test_valid_siren_passes(self):
        assert _validate_siren("732829320") == "732829320"

    def test_strips_whitespace(self):
        assert _validate_siren("  732829320  ") == "732829320"

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="9 digits"):
            _validate_siren("12345678")

    def test_non_digits_raises(self):
        with pytest.raises(ValueError, match="9 digits"):
            _validate_siren("12345678A")

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

    def test_non_digits_raises(self):
        with pytest.raises(ValueError, match="14 digits"):
            _validate_siret("1234567890123A")

    def test_bad_check_digit_raises(self):
        with pytest.raises(ValueError, match="Luhn"):
            _validate_siret("73282932073000")
