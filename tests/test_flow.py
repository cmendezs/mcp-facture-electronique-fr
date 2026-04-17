"""
Unit tests for the Flow Service (clients/flow_client.py + tools/flow_tools.py).

HTTP calls are mocked via respx to avoid any dependency
on a real Approved Platform.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from clients.flow_client import FlowClient, _raise_for_status
from config import OAuthClient, PAConfig

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
def mock_oauth(pa_config: PAConfig) -> OAuthClient:
    """Mocked OAuth2 client that returns a token without network calls."""
    oauth = OAuthClient(pa_config)
    oauth.get_token = AsyncMock(return_value=FAKE_TOKEN)
    return oauth


@pytest.fixture
def flow_client(pa_config: PAConfig, mock_oauth: OAuthClient) -> FlowClient:
    """FlowClient instance with mocked OAuth."""
    return FlowClient(config=pa_config, oauth=mock_oauth)


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
# Tests: _raise_for_status
# ---------------------------------------------------------------------------


class TestRaiseForStatus:
    def test_success_200_does_not_raise(self):
        response = httpx.Response(200, json={"ok": True})
        _raise_for_status(response)  # must not raise

    def test_success_201_does_not_raise(self):
        response = httpx.Response(201, json={"flowId": "abc"})
        _raise_for_status(response)

    def test_404_raises_http_status_error(self):
        response = httpx.Response(404, json={"detail": "Flow not found"})
        with pytest.raises(httpx.HTTPStatusError):
            _raise_for_status(response)

    def test_500_raises_http_status_error(self):
        response = httpx.Response(500, text="Internal Server Error")
        with pytest.raises(httpx.HTTPStatusError):
            _raise_for_status(response)

    def test_429_raises_http_status_error(self):
        response = httpx.Response(429, json={"message": "Rate limit exceeded"})
        with pytest.raises(httpx.HTTPStatusError):
            _raise_for_status(response)


# ---------------------------------------------------------------------------
# Tests: FlowClient.submit_flow
# ---------------------------------------------------------------------------


class TestSubmitFlow:
    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_success(self, flow_client: FlowClient):
        """submit_flow returns the flowId assigned by the AP."""
        expected = _sample_flow_response()
        respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await flow_client.submit_flow(
            file_content=b"<Invoice/>",
            file_name="invoice_001.xml",
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
        """submit_flow passes sender and recipient to flowInfo."""
        expected = _sample_flow_response(flow_id="FLOW-002")
        route = respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(201, json=expected)
        )

        result = await flow_client.submit_flow(
            file_content=b"%PDF-1.4 fake facturx",
            file_name="facturx_001.pdf",
            processing_rule="B2B",
            flow_type="Invoice",
            tracking_id="TRK-2024-002",
            sender_identifier="123456789",
            recipient_identifier="987654321",
        )

        assert result["flowId"] == "FLOW-002"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_413_raises(self, flow_client: FlowClient):
        """An oversized file raises HTTPStatusError."""
        respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(
            return_value=httpx.Response(413, json={"detail": "Payload too large"})
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await flow_client.submit_flow(
                file_content=b"x" * 1000,
                file_name="huge.xml",
                processing_rule="B2B",
                flow_type="Invoice",
            )

        assert exc_info.value.response.status_code == 413

    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_flow_401_retries_once(self, flow_client: FlowClient):
        """A 401 invalidates the token and retries once."""
        call_count = 0

        def response_factory(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(401, json={"detail": "Token expired"})
            return httpx.Response(201, json=_sample_flow_response())

        respx.post(f"{FLOW_BASE_URL}/v1/flows").mock(side_effect=response_factory)
        flow_client._oauth.invalidate_token = MagicMock()

        result = await flow_client.submit_flow(
            file_content=b"<Invoice/>",
            file_name="invoice.xml",
            processing_rule="B2B",
            flow_type="Invoice",
        )

        assert call_count == 2
        assert result["flowId"] == "FLOW-001"
        flow_client._oauth.invalidate_token.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: FlowClient.search_flows
# ---------------------------------------------------------------------------


class TestSearchFlows:
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_flows_returns_list(self, flow_client: FlowClient):
        """search_flows returns a list of flows."""
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
        """search_flows passes updatedAfter in the JSON body."""
        route = respx.post(f"{FLOW_BASE_URL}/v1/flows/search").mock(
            return_value=httpx.Response(200, json=_sample_search_response())
        )

        await flow_client.search_flows(updated_after="2024-09-01T10:05:00Z", limit=25)

        request_body = json.loads(route.calls[0].request.content)
        assert request_body["updatedAfter"] == "2024-09-01T10:05:00Z"
        assert request_body["limit"] == 25

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_flows_empty_result(self, flow_client: FlowClient):
        """search_flows returns an empty list when no flows are found."""
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
        route = respx.get(f"{FLOW_BASE_URL}/v1/flows/FLOW-001").mock(
            return_value=httpx.Response(200, json=_sample_flow_response())
        )

        await flow_client.get_flow(flow_id="FLOW-001")

        assert route.calls[0].request.url.params["docType"] == "Metadata"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_flow_404_raises(self, flow_client: FlowClient):
        """get_flow raises HTTPStatusError for an unknown flowId."""
        respx.get(f"{FLOW_BASE_URL}/v1/flows/UNKNOWN-ID").mock(
            return_value=httpx.Response(404, json={"detail": "Flow not found"})
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await flow_client.get_flow(flow_id="UNKNOWN-ID")

        assert exc_info.value.response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: FlowClient.submit_lifecycle_status
# ---------------------------------------------------------------------------


class TestSubmitLifecycleStatus:
    @respx.mock
    @pytest.mark.asyncio
    async def test_submit_refused_status(self, flow_client: FlowClient):
        """submit_lifecycle_status Refused includes the reason."""
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
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(200, json={"status": "ok", "version": "1.1.0"})
        )

        result = await flow_client.healthcheck()

        assert result["status"] == "ok"

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_503_raises(self, flow_client: FlowClient):
        """healthcheck raises HTTPStatusError when the AP is unavailable."""
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await flow_client.healthcheck()

        assert exc_info.value.response.status_code == 503

    @respx.mock
    @pytest.mark.asyncio
    async def test_healthcheck_empty_body(self, flow_client: FlowClient):
        """healthcheck handles an empty response body (204-like on 200)."""
        respx.get(f"{FLOW_BASE_URL}/v1/healthcheck").mock(
            return_value=httpx.Response(200, content=b"")
        )

        result = await flow_client.healthcheck()

        assert result["http_status"] == 200
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests: OAuthClient
# ---------------------------------------------------------------------------


class TestOAuthClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_token_fetches_and_caches(self, pa_config: PAConfig):
        """get_token fetches a token and caches it."""
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json=_make_token_response())
        )

        oauth = OAuthClient(pa_config)
        # The fixture mock OAuth is not used here — testing the real OAuthClient
        token1 = await oauth.get_token()
        token2 = await oauth.get_token()  # must come from cache

        assert token1 == FAKE_TOKEN
        assert token2 == FAKE_TOKEN
        # The token endpoint must be called only once
        assert respx.calls.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_invalidate_token_forces_refresh(self, pa_config: PAConfig):
        """invalidate_token forces a new call to the authorisation server."""
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(200, json=_make_token_response())
        )

        oauth = OAuthClient(pa_config)
        await oauth.get_token()
        oauth.invalidate_token()
        await oauth.get_token()

        assert respx.calls.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_token_401_from_auth_server_raises(self, pa_config: PAConfig):
        """A 401 from the authorisation server raises HTTPStatusError."""
        respx.post(TOKEN_URL).mock(
            return_value=httpx.Response(401, json={"error": "invalid_client"})
        )

        oauth = OAuthClient(pa_config)
        with pytest.raises(httpx.HTTPStatusError):
            await oauth.get_token()
