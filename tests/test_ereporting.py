"""
Unit tests for e-reporting tools (tools/ereporting_tools.py).

Covers:
  - XML builder for transaction reports (Flux 10.1)
  - XML builder for payment reports (Flux 10.2)
  - XSD validation helper (well-formedness path)
  - MCP tool: validate_ereporting_xml
  - MCP tool: submit_transaction_report
  - MCP tool: submit_payment_report
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from server import mcp
from tools.ereporting_tools import (
    _build_payment_report_xml,
    _build_transaction_report_xml,
    _validate_against_xsd,
)


def _parse(result) -> dict | list:
    return json.loads(result.content[0].text)


# Minimal valid transaction invoice
_MINIMAL_INVOICE = {
    "id": "F-2025-001",
    "issue_date": "2025-01-15",
    "type_code": "380",
    "currency_code": "EUR",
    "business_process_id": "A1",
    "business_process_type_id": "EREP",
    "seller_company_id": "123456789",
    "seller_company_id_scheme": "SIREN",
    "monetary_total_tax_amount": "200.00",
    "monetary_total_currency": "EUR",
    "tax_subtotals": [
        {"taxable_amount": "1000.00", "tax_amount": "200.00", "tax_percent": "20.0"}
    ],
}

# Minimal valid payment invoice
_MINIMAL_PAYMENT = {
    "invoice_id": "F-2025-001",
    "issue_date": "2025-01-15",
    "payment_date": "2025-02-01",
    "subtotals": [
        {"tax_percent": "20.0", "amount": "1200.00", "currency_code": "EUR"}
    ],
}

# Shared header kwargs
_HEADER = dict(
    transmission_id="TX-001",
    issue_datetime="20250115T120000+0100",
    type_code="380",
    sender_id="123456789",
    sender_id_scheme="SIREN",
    sender_name="My CS Platform",
    sender_role_code="CS",
    issuer_id="123456789",
    issuer_id_scheme="SIREN",
    issuer_name="ACME SAS",
    issuer_role_code="MOA",
    period_start="2025-01-01",
    period_end="2025-01-31",
)


# ---------------------------------------------------------------------------
# Tests: _build_transaction_report_xml
# ---------------------------------------------------------------------------


class TestBuildTransactionReportXml:
    def test_produces_well_formed_xml(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        assert root.tag == "Report"

    def test_has_report_document(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        assert root.find("ReportDocument") is not None

    def test_transmission_id_in_xml(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        id_el = root.find("ReportDocument/Id")
        assert id_el is not None
        assert id_el.text == "TX-001"

    def test_period_in_transactions_report(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        start = root.find("TransactionsReport/ReportPeriod/StartDate")
        end = root.find("TransactionsReport/ReportPeriod/EndDate")
        assert start is not None and start.text == "2025-01-01"
        assert end is not None and end.text == "2025-01-31"

    def test_invoice_id_in_xml(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        inv_id = root.find("TransactionsReport/Invoice/ID")
        assert inv_id is not None and inv_id.text == "F-2025-001"

    def test_seller_company_id_with_scheme(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        company_id = root.find("TransactionsReport/Invoice/Seller/CompanyId")
        assert company_id is not None
        assert company_id.text == "123456789"
        assert company_id.attrib["schemeId"] == "SIREN"

    def test_monetary_total_tax_amount_with_currency(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        tax_amount = root.find("TransactionsReport/Invoice/MonetaryTotal/TaxAmount")
        assert tax_amount is not None
        assert tax_amount.text == "200.00"
        assert tax_amount.attrib["CurrencyCode"] == "EUR"

    def test_tax_subtotal_percent(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        percent = root.find("TransactionsReport/Invoice/TaxSubTotal/TaxCategory/Percent")
        assert percent is not None and percent.text == "20.0"

    def test_empty_invoices_produces_valid_xml(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[])
        root = ET.fromstring(xml.encode("utf-8"))
        assert root.find("TransactionsReport") is not None

    def test_xml_escaping_in_invoice_id(self):
        inv = {**_MINIMAL_INVOICE, "id": "<F&2025>"}
        xml = _build_transaction_report_xml(**_HEADER, invoices=[inv])
        root = ET.fromstring(xml.encode("utf-8"))
        inv_id = root.find("TransactionsReport/Invoice/ID")
        assert inv_id is not None and inv_id.text == "<F&2025>"

    def test_optional_buyer_block_included(self):
        inv = {
            **_MINIMAL_INVOICE,
            "buyer_company_id": "DE123456789",
            "buyer_company_id_scheme": "0088",
            "buyer_country": "DE",
        }
        xml = _build_transaction_report_xml(**_HEADER, invoices=[inv])
        root = ET.fromstring(xml.encode("utf-8"))
        buyer = root.find("TransactionsReport/Invoice/Buyer")
        assert buyer is not None
        country = buyer.find("PostalAddress/CountryId")
        assert country is not None and country.text == "DE"

    def test_optional_buyer_block_absent(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        root = ET.fromstring(xml.encode("utf-8"))
        assert root.find("TransactionsReport/Invoice/Buyer") is None

    def test_optional_transmission_name(self):
        xml = _build_transaction_report_xml(
            **_HEADER, invoices=[_MINIMAL_INVOICE], transmission_name="Rapport janvier"
        )
        root = ET.fromstring(xml.encode("utf-8"))
        name = root.find("ReportDocument/Name")
        assert name is not None and name.text == "Rapport janvier"

    def test_multiple_invoices(self):
        inv2 = {**_MINIMAL_INVOICE, "id": "F-2025-002"}
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE, inv2])
        root = ET.fromstring(xml.encode("utf-8"))
        invoices = root.findall("TransactionsReport/Invoice")
        assert len(invoices) == 2

    def test_tax_exclusive_amount_optional(self):
        inv = {**_MINIMAL_INVOICE, "tax_exclusive_amount": "1000.00"}
        xml = _build_transaction_report_xml(**_HEADER, invoices=[inv])
        root = ET.fromstring(xml.encode("utf-8"))
        el = root.find("TransactionsReport/Invoice/MonetaryTotal/TaxExclusiveAmount")
        assert el is not None and el.text == "1000.00"

    def test_multiple_tax_subtotals(self):
        inv = {
            **_MINIMAL_INVOICE,
            "tax_subtotals": [
                {"taxable_amount": "1000.00", "tax_amount": "200.00", "tax_percent": "20.0"},
                {"taxable_amount": "500.00", "tax_amount": "27.50", "tax_percent": "5.5"},
            ],
        }
        xml = _build_transaction_report_xml(**_HEADER, invoices=[inv])
        root = ET.fromstring(xml.encode("utf-8"))
        subtotals = root.findall("TransactionsReport/Invoice/TaxSubTotal")
        assert len(subtotals) == 2


# ---------------------------------------------------------------------------
# Tests: _build_payment_report_xml
# ---------------------------------------------------------------------------


class TestBuildPaymentReportXml:
    def test_produces_well_formed_xml(self):
        xml = _build_payment_report_xml(**_HEADER, invoices=[_MINIMAL_PAYMENT])
        root = ET.fromstring(xml.encode("utf-8"))
        assert root.tag == "Report"

    def test_payments_report_element_present(self):
        xml = _build_payment_report_xml(**_HEADER, invoices=[_MINIMAL_PAYMENT])
        root = ET.fromstring(xml.encode("utf-8"))
        assert root.find("PaymentsReport") is not None

    def test_invoice_id_in_payments(self):
        xml = _build_payment_report_xml(**_HEADER, invoices=[_MINIMAL_PAYMENT])
        root = ET.fromstring(xml.encode("utf-8"))
        inv_id = root.find("PaymentsReport/Invoice/InvoiceID")
        assert inv_id is not None and inv_id.text == "F-2025-001"

    def test_payment_date_in_xml(self):
        xml = _build_payment_report_xml(**_HEADER, invoices=[_MINIMAL_PAYMENT])
        root = ET.fromstring(xml.encode("utf-8"))
        date = root.find("PaymentsReport/Invoice/Payment/Date")
        assert date is not None and date.text == "2025-02-01"

    def test_subtotals_amount_in_xml(self):
        xml = _build_payment_report_xml(**_HEADER, invoices=[_MINIMAL_PAYMENT])
        root = ET.fromstring(xml.encode("utf-8"))
        amount = root.find("PaymentsReport/Invoice/Payment/SubTotals/Amount")
        assert amount is not None and amount.text == "1200.00"

    def test_subtotals_currency_code_optional(self):
        payment_no_currency = {
            "invoice_id": "F-2025-002",
            "issue_date": "2025-01-16",
            "payment_date": "2025-02-02",
            "subtotals": [{"tax_percent": "20.0", "amount": "600.00"}],
        }
        xml = _build_payment_report_xml(**_HEADER, invoices=[payment_no_currency])
        root = ET.fromstring(xml.encode("utf-8"))
        currency = root.find("PaymentsReport/Invoice/Payment/SubTotals/CurrencyCode")
        assert currency is None

    def test_period_in_payments_report(self):
        xml = _build_payment_report_xml(**_HEADER, invoices=[_MINIMAL_PAYMENT])
        root = ET.fromstring(xml.encode("utf-8"))
        start = root.find("PaymentsReport/ReportPeriod/StartDate")
        assert start is not None and start.text == "2025-01-01"

    def test_xml_escaping_in_payment_invoice_id(self):
        payment = {**_MINIMAL_PAYMENT, "invoice_id": "F&2025<001>"}
        xml = _build_payment_report_xml(**_HEADER, invoices=[payment])
        root = ET.fromstring(xml.encode("utf-8"))
        inv_id = root.find("PaymentsReport/Invoice/InvoiceID")
        assert inv_id is not None and inv_id.text == "F&2025<001>"


# ---------------------------------------------------------------------------
# Tests: _validate_against_xsd
# ---------------------------------------------------------------------------


class TestValidateAgainstXsd:
    def test_well_formed_xml_returns_valid(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        result = _validate_against_xsd(xml)
        # Either xsd-valid or well-formedness valid; never False for correct XML
        assert result.get("valid") is not False

    def test_malformed_xml_returns_invalid(self):
        result = _validate_against_xsd("<Report><Unclosed>")
        assert result.get("valid") is False

    def test_returns_level_key(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        result = _validate_against_xsd(xml)
        assert "level" in result

    def test_well_formedness_level_on_bad_xml(self):
        result = _validate_against_xsd("<broken>")
        assert result["level"] == "wellformedness"
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# Tests: MCP tool validate_ereporting_xml
# ---------------------------------------------------------------------------


class TestMcpValidateEreportingXml:
    @pytest.mark.asyncio
    async def test_valid_transaction_xml_passes(self):
        xml = _build_transaction_report_xml(**_HEADER, invoices=[_MINIMAL_INVOICE])
        async with Client(mcp) as client:
            result = await client.call_tool("validate_ereporting_xml", {"xml_content": xml})
        data = _parse(result)
        assert data.get("valid") is not False

    @pytest.mark.asyncio
    async def test_malformed_xml_fails(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "validate_ereporting_xml", {"xml_content": "<Report><Unclosed>"}
            )
        data = _parse(result)
        assert data.get("valid") is False


# ---------------------------------------------------------------------------
# Tests: MCP tool submit_transaction_report
# ---------------------------------------------------------------------------


class TestMcpSubmitTransactionReport:
    @pytest.mark.asyncio
    async def test_pending_confirmation_on_first_call(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "submit_transaction_report",
                {
                    **_HEADER,
                    "invoices_json": json.dumps([_MINIMAL_INVOICE]),
                    "flow_type": "IndividualCustomerTransactionReport",
                    "processing_rule": "B2BInt",
                },
            )
        data = _parse(result)
        assert data["status"] == "awaiting_confirmation"
        assert "token" in data

    @pytest.mark.asyncio
    async def test_submit_with_confirmation(self):
        fake_response = {"flowId": "FL-001", "status": "Deposited"}
        mock_client = AsyncMock()
        mock_client.submit_flow = AsyncMock(return_value=fake_response)

        with (
            patch("mcp_einvoicing_core.confirmation._HITL_DISABLED", True),
            patch("tools.ereporting_tools._get_flow_client", return_value=mock_client),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "submit_transaction_report",
                    {
                        **_HEADER,
                        "invoices_json": json.dumps([_MINIMAL_INVOICE]),
                        "flow_type": "IndividualCustomerTransactionReport",
                        "processing_rule": "B2BInt",
                    },
                )
        data = _parse(result)
        assert data.get("flowId") == "FL-001"

    @pytest.mark.asyncio
    async def test_invalid_invoices_json_returns_error(self):
        with patch("mcp_einvoicing_core.confirmation._HITL_DISABLED", True):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "submit_transaction_report",
                    {
                        **_HEADER,
                        "invoices_json": "not-valid-json",
                        "flow_type": "IndividualCustomerTransactionReport",
                        "processing_rule": "B2BInt",
                    },
                )
        data = _parse(result)
        assert "error" in data
        assert "JSON" in data["error"]

    @pytest.mark.asyncio
    async def test_invoices_json_must_be_array(self):
        with patch("mcp_einvoicing_core.confirmation._HITL_DISABLED", True):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "submit_transaction_report",
                    {
                        **_HEADER,
                        "invoices_json": '{"key": "value"}',
                        "flow_type": "IndividualCustomerTransactionReport",
                        "processing_rule": "B2BInt",
                    },
                )
        data = _parse(result)
        assert "error" in data
        assert "array" in data["error"].lower()


# ---------------------------------------------------------------------------
# Tests: MCP tool submit_payment_report
# ---------------------------------------------------------------------------


class TestMcpSubmitPaymentReport:
    @pytest.mark.asyncio
    async def test_pending_confirmation_on_first_call(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "submit_payment_report",
                {
                    **_HEADER,
                    "invoices_json": json.dumps([_MINIMAL_PAYMENT]),
                    "flow_type": "UnitaryCustomerPaymentReport",
                    "processing_rule": "B2BInt",
                },
            )
        data = _parse(result)
        assert data["status"] == "awaiting_confirmation"
        assert "token" in data

    @pytest.mark.asyncio
    async def test_submit_payment_with_confirmation(self):
        fake_response = {"flowId": "FL-PAY-001", "status": "Deposited"}
        mock_client = AsyncMock()
        mock_client.submit_flow = AsyncMock(return_value=fake_response)

        with (
            patch("mcp_einvoicing_core.confirmation._HITL_DISABLED", True),
            patch("tools.ereporting_tools._get_flow_client", return_value=mock_client),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "submit_payment_report",
                    {
                        **_HEADER,
                        "invoices_json": json.dumps([_MINIMAL_PAYMENT]),
                        "flow_type": "UnitaryCustomerPaymentReport",
                        "processing_rule": "B2BInt",
                    },
                )
        data = _parse(result)
        assert data.get("flowId") == "FL-PAY-001"
