"""
MCP protocol tests for the mcp-facture-electronique-fr server.

Verifies that tools are correctly registered via the MCP protocol,
that their schemas are valid (parameter names, types, required/optional status),
and that they work end-to-end via the in-process MCP client — without network calls.

These tests cover the layer that unit tests do not touch:
@mcp.tool() registration, response serialisation, and the wiring
between the JSON schema exposed to the LLM and the underlying Python functions.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from server import mcp

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_FLOW_TOOLS = {
    "submit_flow",
    "search_flows",
    "get_flow",
    "submit_lifecycle_status",
    "healthcheck_flow",
}

EXPECTED_DIRECTORY_TOOLS = {
    "search_company",
    "get_company_by_siren",
    "search_establishment",
    "get_establishment_by_siret",
    "search_routing_code",
    "create_routing_code",
    "update_routing_code",
    "search_directory_line",
    "get_directory_line",
    "create_directory_line",
    "update_directory_line",
    "delete_directory_line",
}


def _parse(result) -> dict | list:
    """Extracts and deserialises the JSON response from an MCP tool call."""
    return json.loads(result.content[0].text)


# ---------------------------------------------------------------------------
# Tests: tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_all_flow_tools_registered(self):
        """All 5 Flow Service tools are exposed via the MCP protocol."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        names = {t.name for t in tools}
        assert EXPECTED_FLOW_TOOLS.issubset(names)

    @pytest.mark.asyncio
    async def test_all_directory_tools_registered(self):
        """All 12 Directory Service tools are exposed via the MCP protocol."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        names = {t.name for t in tools}
        assert EXPECTED_DIRECTORY_TOOLS.issubset(names)

    @pytest.mark.asyncio
    async def test_total_tool_count(self):
        """The server exposes exactly 17 tools (5 Flow + 12 Directory)."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        assert len(tools) == 17

    @pytest.mark.asyncio
    async def test_all_tools_have_non_empty_description(self):
        """Every exposed tool has a non-empty description (visible to the LLM)."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        for tool in tools:
            assert tool.description, f"Tool '{tool.name}' has no description"


# ---------------------------------------------------------------------------
# Tests: tool JSON schemas (what the LLM sees)
# ---------------------------------------------------------------------------


class TestToolSchemas:
    @pytest.mark.asyncio
    async def test_submit_flow_required_params(self):
        """submit_flow declares the 5 expected required parameters."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "submit_flow")
        required = set(tool.inputSchema.get("required", []))
        assert {"file_base64", "file_name", "flow_syntax", "processing_rule", "flow_type"}.issubset(
            required
        )

    @pytest.mark.asyncio
    async def test_submit_flow_tracking_id_is_optional(self):
        """tracking_id is not in submit_flow's required parameters."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "submit_flow")
        required = set(tool.inputSchema.get("required", []))
        assert "tracking_id" not in required

    @pytest.mark.asyncio
    async def test_get_flow_flow_id_required_doc_type_optional(self):
        """get_flow requires flow_id; doc_type is optional (defaults to Metadata)."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_flow")
        required = set(tool.inputSchema.get("required", []))
        assert "flow_id" in required
        assert "doc_type" not in required

    @pytest.mark.asyncio
    async def test_healthcheck_flow_has_no_required_params(self):
        """healthcheck_flow has no required parameters."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "healthcheck_flow")
        assert tool.inputSchema.get("required", []) == []

    @pytest.mark.asyncio
    async def test_submit_lifecycle_status_required_params(self):
        """submit_lifecycle_status requires referenced_flow_id and status_code."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "submit_lifecycle_status")
        required = set(tool.inputSchema.get("required", []))
        assert "referenced_flow_id" in required
        assert "status_code" in required
        # Payment and reason fields are optional
        assert "reason" not in required
        assert "payment_date" not in required
        assert "payment_amount" not in required

    @pytest.mark.asyncio
    async def test_get_directory_line_requires_addressing_identifier(self):
        """get_directory_line requires addressing_identifier."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_directory_line")
        required = set(tool.inputSchema.get("required", []))
        assert "addressing_identifier" in required

    @pytest.mark.asyncio
    async def test_create_directory_line_required_params(self):
        """create_directory_line requires siren and platform_id."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "create_directory_line")
        required = set(tool.inputSchema.get("required", []))
        assert "siren" in required
        assert "platform_id" in required
        # siret, routing_code, technical_address are optional
        assert "siret" not in required
        assert "routing_code" not in required

    @pytest.mark.asyncio
    async def test_search_tools_have_no_required_params(self):
        """Search tools (search_*) have no required parameters."""
        search_tools = {
            "search_flows",
            "search_company",
            "search_establishment",
            "search_routing_code",
            "search_directory_line",
        }
        async with Client(mcp) as client:
            tools = await client.list_tools()
        for tool in tools:
            if tool.name in search_tools:
                required = tool.inputSchema.get("required", [])
                assert required == [], (
                    f"'{tool.name}' should have no required parameters, "
                    f"found: {required}"
                )


# ---------------------------------------------------------------------------
# Tests: Flow Service tool calls via MCP protocol
# ---------------------------------------------------------------------------


class TestFlowToolCalls:
    @pytest.mark.asyncio
    async def test_submit_flow_decodes_base64_and_returns_flow_id(self):
        """submit_flow decodes base64, calls the client, and returns the flowId."""
        fake_response = {"flowId": "FLOW-001", "trackingId": "TRK-001", "status": "Deposited"}
        mock_client = AsyncMock()
        mock_client.submit_flow = AsyncMock(return_value=fake_response)

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "submit_flow",
                    {
                        "file_base64": base64.b64encode(b"<Invoice/>").decode(),
                        "file_name": "invoice.xml",
                        "flow_syntax": "CII",
                        "processing_rule": "B2B",
                        "flow_type": "Invoice",
                    },
                )

        data = _parse(result)
        assert data["flowId"] == "FLOW-001"
        assert data["status"] == "Deposited"

    @pytest.mark.asyncio
    async def test_submit_flow_invalid_base64_returns_error_dict(self):
        """submit_flow returns {"error": ...} for invalid base64 without raising an MCP exception."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "submit_flow",
                {
                    "file_base64": "!!!not-valid-base64!!!",
                    "file_name": "invoice.xml",
                    "flow_syntax": "CII",
                    "processing_rule": "B2B",
                    "flow_type": "Invoice",
                },
            )

        data = _parse(result)
        assert "error" in data
        assert "base64" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_submit_flow_passes_decoded_bytes_to_client(self):
        """submit_flow passes decoded bytes (not the base64 string) to the HTTP client."""
        xml_bytes = b"<Invoice><ID>001</ID></Invoice>"
        mock_client = AsyncMock()
        mock_client.submit_flow = AsyncMock(return_value={"flowId": "F-001", "status": "Deposited"})

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                await client.call_tool(
                    "submit_flow",
                    {
                        "file_base64": base64.b64encode(xml_bytes).decode(),
                        "file_name": "invoice.xml",
                        "flow_syntax": "CII",
                        "processing_rule": "B2B",
                        "flow_type": "Invoice",
                        "tracking_id": "TRK-042",
                    },
                )

        call_kwargs = mock_client.submit_flow.call_args.kwargs
        assert call_kwargs["file_content"] == xml_bytes
        assert call_kwargs["tracking_id"] == "TRK-042"

    @pytest.mark.asyncio
    async def test_healthcheck_flow_returns_status(self):
        """healthcheck_flow returns the AP's operational status."""
        mock_client = AsyncMock()
        mock_client.healthcheck = AsyncMock(return_value={"status": "ok", "version": "1.1.0"})

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool("healthcheck_flow", {})

        data = _parse(result)
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_search_flows_passes_all_filters(self):
        """search_flows passes all filter criteria to the HTTP client."""
        mock_client = AsyncMock()
        mock_client.search_flows = AsyncMock(
            return_value={"flows": [], "total": 0, "nextUpdatedAfter": None}
        )

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                await client.call_tool(
                    "search_flows",
                    {
                        "processing_rule": "B2B",
                        "status": "Deposited",
                        "tracking_id": "TRK-001",
                        "limit": 10,
                    },
                )

        mock_client.search_flows.assert_called_once_with(
            processing_rule="B2B",
            flow_type=None,
            status="Deposited",
            updated_after=None,
            tracking_id="TRK-001",
            limit=10,
        )

    @pytest.mark.asyncio
    async def test_get_flow_metadata_returns_dict(self):
        """get_flow with docType Metadata returns a JSON dict directly."""
        fake_response = {"flowId": "FLOW-001", "status": "Delivered", "senderSiren": "123456789"}
        mock_client = AsyncMock()
        mock_client.get_flow = AsyncMock(return_value=fake_response)

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_flow", {"flow_id": "FLOW-001", "doc_type": "Metadata"}
                )

        data = _parse(result)
        assert data["flowId"] == "FLOW-001"
        assert "contentBase64" not in data

    @pytest.mark.asyncio
    async def test_get_flow_binary_response_encoded_as_base64(self):
        """get_flow encodes binary responses as base64 (Original, Converted, ReadableView)."""
        xml_bytes = b"<Invoice>...</Invoice>"
        mock_client = AsyncMock()
        mock_client.get_flow = AsyncMock(return_value=xml_bytes)

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_flow", {"flow_id": "FLOW-001", "doc_type": "Original"}
                )

        data = _parse(result)
        assert "contentBase64" in data
        assert data["docType"] == "Original"
        assert base64.b64decode(data["contentBase64"]) == xml_bytes

    @pytest.mark.asyncio
    async def test_submit_lifecycle_status_passes_all_params(self):
        """submit_lifecycle_status passes all parameters to the client."""
        fake_response = {"flowId": "STATUS-001", "status": "Deposited"}
        mock_client = AsyncMock()
        mock_client.submit_lifecycle_status = AsyncMock(return_value=fake_response)

        with patch("tools.flow_tools.get_flow_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "submit_lifecycle_status",
                    {
                        "referenced_flow_id": "FLOW-001",
                        "status_code": "Cashed",
                        "payment_date": "2024-09-30",
                        "payment_amount": "12500.00",
                    },
                )

        data = _parse(result)
        assert data["flowId"] == "STATUS-001"
        mock_client.submit_lifecycle_status.assert_called_once_with(
            referenced_flow_id="FLOW-001",
            status_code="Cashed",
            reason=None,
            payment_date="2024-09-30",
            payment_amount="12500.00",
        )


# ---------------------------------------------------------------------------
# Tests: Directory Service tool calls via MCP protocol
# ---------------------------------------------------------------------------


class TestDirectoryToolCalls:
    @pytest.mark.asyncio
    async def test_get_directory_line_returns_platform_id(self):
        """get_directory_line returns the recipient's Approved Platform."""
        fake_response = {
            "addressingIdentifier": "123456789",
            "platformId": "PA-001",
            "status": "Active",
        }
        mock_client = AsyncMock()
        mock_client.get_directory_line = AsyncMock(return_value=fake_response)

        with patch("tools.directory_tools.get_directory_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_directory_line", {"addressing_identifier": "123456789"}
                )

        data = _parse(result)
        assert data["platformId"] == "PA-001"
        mock_client.get_directory_line.assert_called_once_with(addressing_identifier="123456789")

    @pytest.mark.asyncio
    async def test_get_company_by_siren_returns_company_info(self):
        """get_company_by_siren returns the legal unit information."""
        fake_response = {"siren": "123456789", "name": "ACME SAS", "status": "Active"}
        mock_client = AsyncMock()
        mock_client.get_company_by_siren = AsyncMock(return_value=fake_response)

        with patch("tools.directory_tools.get_directory_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_company_by_siren", {"siren": "123456789"}
                )

        data = _parse(result)
        assert data["siren"] == "123456789"

    @pytest.mark.asyncio
    async def test_create_directory_line_required_siren_and_platform(self):
        """create_directory_line creates a directory line with siren + platform_id."""
        fake_response = {"instanceId": "DL-001", "siren": "123456789", "platformId": "PA-001"}
        mock_client = AsyncMock()
        mock_client.create_directory_line = AsyncMock(return_value=fake_response)

        with patch("tools.directory_tools.get_directory_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "create_directory_line",
                    {"siren": "123456789", "platform_id": "PA-001"},
                )

        data = _parse(result)
        assert data["instanceId"] == "DL-001"
        mock_client.create_directory_line.assert_called_once_with(
            siren="123456789",
            platform_id="PA-001",
            siret=None,
            routing_code=None,
            technical_address=None,
        )

    @pytest.mark.asyncio
    async def test_delete_directory_line_returns_deleted_true(self):
        """delete_directory_line returns {"deleted": True, "instanceId": ...}."""
        mock_client = AsyncMock()
        mock_client.delete_directory_line = AsyncMock(
            return_value={"deleted": True, "instanceId": "DL-001"}
        )

        with patch("tools.directory_tools.get_directory_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "delete_directory_line", {"instance_id": "DL-001"}
                )

        data = _parse(result)
        assert data["deleted"] is True
        mock_client.delete_directory_line.assert_called_once_with(instance_id="DL-001")

    @pytest.mark.asyncio
    async def test_search_company_passes_filters(self):
        """search_company passes all criteria to the client."""
        mock_client = AsyncMock()
        mock_client.search_company = AsyncMock(return_value={"companies": [], "total": 0})

        with patch("tools.directory_tools.get_directory_client", return_value=mock_client):
            async with Client(mcp) as client:
                await client.call_tool(
                    "search_company",
                    {"siren": "123456789", "status": "Active", "limit": 25},
                )

        mock_client.search_company.assert_called_once_with(
            name=None,
            siren="123456789",
            status="Active",
            updated_after=None,
            limit=25,
        )

    @pytest.mark.asyncio
    async def test_update_directory_line_passes_patch_fields(self):
        """update_directory_line only passes the provided fields (PATCH semantics)."""
        fake_response = {"instanceId": "DL-001", "platformId": "PA-002"}
        mock_client = AsyncMock()
        mock_client.update_directory_line = AsyncMock(return_value=fake_response)

        with patch("tools.directory_tools.get_directory_client", return_value=mock_client):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "update_directory_line",
                    {"instance_id": "DL-001", "platform_id": "PA-002"},
                )

        data = _parse(result)
        assert data["platformId"] == "PA-002"
        mock_client.update_directory_line.assert_called_once_with(
            instance_id="DL-001",
            platform_id="PA-002",
            technical_address=None,
            routing_code=None,
        )
