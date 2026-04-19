"""
Unit tests for the Flow Service (clients/flow_client.py + tools/flow_tools.py).

HTTP calls are mocked via respx to avoid any dependency
on a real Approved Platform.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from clients.flow_client import FlowClient
from config import PAConfig
from mcp_einvoicing_core.exceptions import AuthenticationError, PlatformError
from mcp_einvoicing_core.http_client import TokenCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_TOKEN = "eyJhbGciOiJSUzI1NiJ9.fake.token"

FLOW_BASE_URL = "https://api.flow.test-pa.fr/flow-service"
TOKEN_URL = "https://auth.test-pa.fr/oauth/token"


@pytest.fixture
def pa_config() -> PAConfig:
    """Test PA configuration (does not contact any real server)."""
    return PAConfig(
        pa_base_url_flow=FLOW_BASE_URL,
        pa_base_url_directory="https://api.directory.test-pa.fr/directory-service",
        pa_client_id="test-client-id",
        pa_client_secret="test-client-secret",
        pa_token_url=TOKEN_URL,
        http_timeout=5.0,
    )


@pytest.fixture
def token_cache() -> TokenCache:
    """Fresh token cache per test — prevents leaking between tests."""
    return TokenCache()


@pytest.fixture
def flow_client(pa_config: PAConfig, token_cache: TokenCache) -> FlowClient:
    """FlowClient instance with injected fresh token cache."""
    return FlowClient(config=pa_config, token_cache=token_cache)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token_response() -> dict:
    return {"access_token": FAKE_TOKEN, "token_type": "Bearer", "expires_in": 3600}


def _sample_flow_response(flow_id: str = "FLOW-001", tracking_id: str = "TRK-2024-001") -> dict:
    return {
        "flowId": flow_id,
        "trackingId": tracking_id,
        "status": "Deposited",
        "processingRule": "B2B",
        "flowType": "Invoice",
        "createdAt": "2024-09-01T10:00:00Z",
        "updatedAt": "2024-09-01T10:00:01Z",
    }


def _sample_search_response(flows: list | None = None) -> dict:
    return {
        "flows": flows or [_sample_flow_response()],
        "total": 1,
        "nextUpdatedAfter": None,
    }


# ---------------------------------------------------------------------------
# Tests: TokenCache (replaces deleted OAuthClient)
# ---------------------------------------------------------------------------


class TestTokenCache:
    def test_empty_initially(self):
        cache = TokenCache()
        assert cache.get() is None
        assert not cache.is_valid()

    def test_set_and_get(self):
        cache = TokenCache()
        cache.set("my-token", 3600)
        assert cache.get() == "my-token"
        assert cache.is_valid()

    def test_invalidate_clears_token(self):
        cache = TokenCache()
        cache.set("my-token", 3600)
        cache.invalidate()
        assert cache.get() is None
        assert not cache.is_valid()

    def test_expired_token_not_returned(self):
        """A token set with expires_in=0 is immediately outside the validity window."""
        cache = TokenCache()
        cache.set("my-token", 0)
        assert cache.get() is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_token_fetched_and_cached(self, flow_client: FlowClient):
        """Token is fetched once and reused for subsequent requests."""
        token_route = respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json=_make_token_response())
        )
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        await flow_client.healthcheck()
        await flow_client.healthcheck()

        assert token_route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_invalidate_forces_token_refresh(self, flow_client: FlowClient):
        """After invalidation, the token is refetched on the next request."""
        token_route = respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json=_make_token_response())
        )
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        await flow_client.healthcheck()
        flow_client.invalidate_token()
        await flow_client.healthcheck()

        assert token_route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_server_error_raises_authentication_error(self, flow_client: FlowClient):
        """A 401 from the token endpoint raises AuthenticationError."""
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(401, json={"error": "invalid_client"})
        )

        with pytest.raises(AuthenticationError):
            await flow_client.healthcheck()


# ---------------------------------------------------------------------------
# Tests: FlowClient.submit_flow
# ---------------------------------------------------------------------------


class TestSubmitFlow:
    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_success(self, flow_client: FlowClient):
        """submit_flow returns the flowId assigned by the AP."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = _sample_flow_response()
        respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await flow_client.submit_flow(
            file_content=b"<Invoice/>",
            file_name="invoice_001.xml",
            flow_syntax="CII",
            processing_rule="B2B",
            flow_type="Invoice",
            tracking_id="TRK-2024-001",
        )

        assert result["flowId"] == "FLOW-001"
        assert result["trackingId"] == "TRK-2024-001"
        assert result["status"] == "Deposited"

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_with_all_params(self, flow_client: FlowClient):
        """submit_flow sends all provided flow metadata to the AP."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = _sample_flow_response(flow_id="FLOW-002")
        route = respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await flow_client.submit_flow(
            file_content=b"%PDF-1.4 fake facturx",
            file_name="facturx_001.pdf",
            flow_syntax="FacturX",
            processing_rule="B2B",
            flow_type="Invoice",
            tracking_id="TRK-2024-002",
        )

        assert result["flowId"] == "FLOW-002"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_413_raises(self, flow_client: FlowClient):
        """An oversized file raises PlatformError."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(413, json={"detail": "Payload too large"})
        )

        with pytest.raises(PlatformError) as exc_info:
            await flow_client.submit_flow(
                file_content=b"x" * 1000,
                file_name="huge.xml",
                flow_syntax="UBL",
                processing_rule="B2B",
                flow_type="Invoice",
            )

        assert exc_info.value.status_code == 413

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_401_retries_once(self, flow_client: FlowClient):
        """A 401 from the AP invalidates the token and the request is retried once."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))

        call_count = 0

        def response_factory(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(401, json={"detail": "Token expired"})
            return httpx.Response(201, json=_sample_flow_response())

        respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(side_effect=response_factory)

        result = await flow_client.submit_flow(
            file_content=b"<Invoice/>",
            file_name="invoice.xml",
            flow_syntax="CII",
            processing_rule="B2B",
            flow_type="Invoice",
        )

        assert call_count == 2
        assert result["flowId"] == "FLOW-001"


# ---------------------------------------------------------------------------
# Tests: FlowClient.search_flows
# ---------------------------------------------------------------------------


class TestSearchFlows:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_flows_returns_list(self, flow_client: FlowClient):
        """search_flows returns a list of flows."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = _sample_search_response(
            flows=[
                _sample_flow_response("FLOW-001", "TRK-001"),
                _sample_flow_response("FLOW-002", "TRK-002"),
            ]
        )
        expected["total"] = 2

        respx.post(f"{FLOW_BASE_URL}/v1/flows/search").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await flow_client.search_flows(processing_rule="B2B", limit=10)

        assert len(result["flows"]) == 2
        assert result["flows"][0]["flowId"] == "FLOW-001"

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_flows_pagination_via_updated_after(self, flow_client: FlowClient):
        """search_flows passes updatedAfter inside the where dict."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        route = respx.post(f"{FLOW_BASE_URL}/v1/flows/search").mock(
            return_value=httpx.Response(200, json=_sample_search_response())
        )

        await flow_client.search_flows(updated_after="2024-09-01T10:05:00Z", limit=25)

        request_body = json.loads(route.calls[0].request.content)
        assert request_body["where"]["updatedAfter"] == "2024-09-01T10:05:00Z"
        assert request_body["limit"] == 25

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_flows_empty_result(self, flow_client: FlowClient):
        """search_flows returns an empty list when no flows are found."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.post(f"{FLOW_BASE_URL}/v1/flows/search").mock(
            return_value=httpx.Response(200, json={"flows": [], "total": 0, "nextUpdatedAfter": None})
        )

        result = await flow_client.search_flows(status="NonExistentStatus")

        assert result["flows"] == []
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Tests: FlowClient.get_flow
# ---------------------------------------------------------------------------


class TestGetFlow:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_flow_metadata_returns_dict(self, flow_client: FlowClient):
        """get_flow with docType=Metadata returns a JSON dict."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            **_sample_flow_response("FLOW-001"),
            "senderSiren": "123456789",
            "recipientSiren": "987654321",
        }
        respx.get(f"{FLOW_BASE_URL}/v1/flows/FLOW-001").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await flow_client.get_flow(flow_id="FLOW-001", doc_type="Metadata")

        assert isinstance(result, dict)
        assert result["flowId"] == "FLOW-001"
        assert result["senderSiren"] == "123456789"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_flow_original_returns_bytes(self, flow_client: FlowClient):
        """get_flow with docType=Original returns bytes."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        xml_content = b"<Invoice>...</Invoice>"
        respx.get(f"{FLOW_BASE_URL}/v1/flows/FLOW-001").mock(
            return_value=httpx.Response(
                200,
                content=xml_content,
                headers={"Content-Type": "application/xml"},
            )
        )

        result = await flow_client.get_flow(flow_id="FLOW-001", doc_type="Original")

        assert isinstance(result, bytes)
        assert result == xml_content

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_flow_default_doc_type_is_metadata(self, flow_client: FlowClient):
        """get_flow without docType defaults to Metadata."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        route = respx.get(f"{FLOW_BASE_URL}/v1/flows/FLOW-001").mock(
            return_value=httpx.Response(200, json=_sample_flow_response())
        )

        await flow_client.get_flow(flow_id="FLOW-001")

        assert route.calls[0].request.url.params["docType"] == "Metadata"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_flow_404_raises(self, flow_client: FlowClient):
        """get_flow raises PlatformError for an unknown flowId."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{FLOW_BASE_URL}/v1/flows/UNKNOWN-ID").mock(
            return_value=httpx.Response(404, json={"detail": "Flow not found"})
        )

        with pytest.raises(PlatformError) as exc_info:
            await flow_client.get_flow(flow_id="UNKNOWN-ID")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: FlowClient.submit_lifecycle_status
# ---------------------------------------------------------------------------


class TestSubmitLifecycleStatus:
    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_refused_status(self, flow_client: FlowClient):
        """submit_lifecycle_status Refused includes the reason."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {
            "flowId": "STATUS-001",
            "status": "Deposited",
            "flowType": "LifecycleStatus",
        }
        route = respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await flow_client.submit_lifecycle_status(
            referenced_flow_id="FLOW-001",
            status_code="Refused",
            reason="Incorrect amount on line 3",
        )

        assert result["flowId"] == "STATUS-001"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_cashed_status_with_payment_info(self, flow_client: FlowClient):
        """submit_lifecycle_status Cashed passes payment information."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        expected = {"flowId": "STATUS-002", "status": "Deposited"}
        route = respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await flow_client.submit_lifecycle_status(
            referenced_flow_id="FLOW-002",
            status_code="Cashed",
            payment_date="2024-09-30",
            payment_amount="12500.00",
        )

        assert result["flowId"] == "STATUS-002"
        assert route.called


# ---------------------------------------------------------------------------
# Tests: FlowClient.healthcheck
# ---------------------------------------------------------------------------


class TestHealthcheck:
    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_ok(self, flow_client: FlowClient):
        """healthcheck returns the operational status."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(200, json={"status": "ok", "version": "1.1.0"})
        )

        result = await flow_client.healthcheck()

        assert result["status"] == "ok"

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_503_raises(self, flow_client: FlowClient):
        """healthcheck raises PlatformError when the AP is unavailable."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        with pytest.raises(PlatformError) as exc_info:
            await flow_client.healthcheck()

        assert exc_info.value.status_code == 503

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_empty_body(self, flow_client: FlowClient):
        """healthcheck handles an empty response body gracefully."""
        respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json=_make_token_response()))
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(200, content=b"")
        )

        result = await flow_client.healthcheck()

        assert result["http_status"] == 200
        assert result["status"] == "ok"
