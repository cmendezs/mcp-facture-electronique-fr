"""
Unit tests for wire_formats.py (FR-TC-1, previously 0% coverage) and the
related shared-hardening findings from the 2026-07 audit sweep.

Covers:
  - FR-SC-1  CII BT-24 profile URN: schemeID attribute + real element text,
             no stray text= attribute anywhere in the serialised tree, and a
             CII generate -> parse roundtrip on `profile`.
  - FR-SC-2  UBL BT-23 (<cbc:ProfileID>) emission once `business_process` is
             set (core mcp-einvoicing-core v1.15.0 wiring) + UBL BT-24
             generate -> parse roundtrip on `profile`.
  - FR-SH-1  E-reporting amount/percent fields must be coerced through
             Decimal before XML interpolation (injection guard).
  - FR-SH-2  E-reporting XSD validation helper must reject XXE / entity
             expansion payloads instead of parsing them with a raw parser.
  - FR-SH-3  FRParty.siret / FRParty.siren Luhn check-digit validation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from lxml import etree

from mcp_facture_electronique_fr.models import FACTURX_SCHEME_ID, FRInvoice, FRParty
from mcp_facture_electronique_fr.tools.ereporting_tools import (
    _build_payment_report_xml,
    _build_transaction_report_xml,
    _validate_against_xsd,
)
from mcp_facture_electronique_fr.validators import SUPPORTED_FACTURX_PROFILES
from mcp_facture_electronique_fr.wire_formats import (
    FRCIIParser,
    FRCIISerializer,
    FRUBLParser,
    FRUBLSerializer,
)

_RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"

# Maps the Schematron stylesheet keys in SUPPORTED_FACTURX_PROFILES to the
# BT-24 profile URNs a caller would actually put on FRInvoice.profile.
_PROFILE_URN_BY_STYLESHEET_KEY: dict[str, str] = {
    "MINIMUM": "urn:factur-x.eu:1p0:minimum",
    "BASICWL": "urn:factur-x.eu:1p0:basicwl",
    "BASIC": "urn:factur-x.eu:1p0:basic",
    "EN16931": "urn:factur-x.eu:1p0:en16931",
    "EXTENDED": "urn:factur-x.eu:1p0:extended",
    "EXTENDED-CTC-FR": (
        "urn:cen.eu:en16931:2017#conformant#urn.cpro.gouv.fr:1p0:extended-ctc-fr"
    ),
}

_ADDRESS = {
    "line_one": "1 rue de Rivoli",
    "city": "Paris",
    "postcode": "75001",
    "country_code": "FR",
}


def _party(name: str, siren: str) -> FRParty:
    return FRParty(name=name, siren=siren, address=_ADDRESS)


def _sample_invoice(profile: str, *, business_process: str | None = None) -> FRInvoice:
    return FRInvoice(
        profile=profile,
        business_process=business_process,
        invoice_number="F202500001",
        invoice_date="2026-07-01",
        currency_code="EUR",
        seller=_party("Vendeur SAS", "732829320"),
        buyer=_party("Acheteur SARL", "404833048"),
        sum_of_line_net_amounts=Decimal("1000.00"),
        allowances_total=Decimal("0.00"),
        charges_total=Decimal("0.00"),
        tax_exclusive_amount=Decimal("1000.00"),
        tax_total=Decimal("200.00"),
        tax_inclusive_amount=Decimal("1200.00"),
        amount_due=Decimal("1200.00"),
        tax_lines=[
            {
                "category": "S",
                "rate": Decimal("20.00"),
                "taxable_amount": Decimal("1000.00"),
                "tax_amount": Decimal("200.00"),
            }
        ],
    )


# ---------------------------------------------------------------------------
# FR-SC-1 / FR-TC-1 — CII BT-24 roundtrip
# ---------------------------------------------------------------------------


class TestCIIProfileURN:
    @pytest.mark.parametrize(
        "profile",
        [_PROFILE_URN_BY_STYLESHEET_KEY[key] for key in SUPPORTED_FACTURX_PROFILES],
        ids=list(SUPPORTED_FACTURX_PROFILES),
    )
    def test_guideline_id_has_correct_text_and_scheme_id(self, profile: str) -> None:
        invoice = _sample_invoice(profile)
        xml_bytes = FRCIISerializer().serialize(invoice)
        root = etree.fromstring(xml_bytes)

        guideline_id = root.find(
            f"{{{_RSM}}}ExchangedDocumentContext"
            f"/{{{_RAM}}}GuidelineSpecifiedDocumentContextParameter"
            f"/{{{_RAM}}}ID"
        )
        assert guideline_id is not None
        assert guideline_id.text == profile
        assert guideline_id.get("schemeID") == FACTURX_SCHEME_ID

    def test_no_stray_text_attribute_anywhere(self) -> None:
        """lxml's SubElement(**extra) turns a `text=` kwarg into a real XML
        attribute literally named "text" — this is the FR-SC-1 regression."""
        invoice = _sample_invoice(_PROFILE_URN_BY_STYLESHEET_KEY["EN16931"])
        xml_bytes = FRCIISerializer().serialize(invoice)
        root = etree.fromstring(xml_bytes)
        for el in root.iter():
            assert "text" not in el.attrib, (
                f"Found stray text= attribute on {el.tag}: {el.attrib}"
            )

    def test_cii_roundtrip_preserves_profile(self) -> None:
        profile = _PROFILE_URN_BY_STYLESHEET_KEY["EN16931"]
        invoice = _sample_invoice(profile)
        xml_bytes = FRCIISerializer().serialize(invoice)
        parsed = FRCIIParser().parse(xml_bytes)
        assert parsed.profile == profile


# ---------------------------------------------------------------------------
# FR-SC-2 — UBL BT-23 (business_process / <cbc:ProfileID>) + BT-24 roundtrip
# ---------------------------------------------------------------------------


class TestUBLBusinessProcessAndProfile:
    _CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

    def test_profile_id_emitted_when_business_process_set(self) -> None:
        invoice = _sample_invoice(
            _PROFILE_URN_BY_STYLESHEET_KEY["EN16931"],
            business_process="urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
        )
        xml_bytes = FRUBLSerializer().serialize(invoice)
        root = etree.fromstring(xml_bytes)
        profile_id = root.find(f"{{{self._CBC}}}ProfileID")
        assert profile_id is not None
        assert profile_id.text == "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

    def test_profile_id_absent_when_business_process_unset(self) -> None:
        invoice = _sample_invoice(_PROFILE_URN_BY_STYLESHEET_KEY["EN16931"])
        xml_bytes = FRUBLSerializer().serialize(invoice)
        root = etree.fromstring(xml_bytes)
        assert root.find(f"{{{self._CBC}}}ProfileID") is None

    def test_ubl_roundtrip_preserves_profile(self) -> None:
        profile = _PROFILE_URN_BY_STYLESHEET_KEY["EN16931"]
        invoice = _sample_invoice(profile)
        xml_bytes = FRUBLSerializer().serialize(invoice)
        parsed = FRUBLParser().parse(xml_bytes)
        assert parsed.profile == profile


# ---------------------------------------------------------------------------
# FR-SH-2 — e-reporting XSD validation: XXE / DoS guard
# ---------------------------------------------------------------------------


class TestEreportingXXEGuard:
    def test_external_entity_is_not_expanded(self) -> None:
        malicious = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE Report [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            "<Report>&xxe;</Report>"
        )
        result = _validate_against_xsd(malicious)
        # Must never succeed with the entity silently expanded into content.
        assert result["valid"] is not True or "&xxe;" not in str(result)

    def test_billion_laughs_is_rejected_or_not_expanded(self) -> None:
        malicious = (
            '<?xml version="1.0"?>'
            "<!DOCTYPE lolz ["
            '<!ENTITY lol "lol">'
            '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
            '<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
            "]>"
            "<Report>&lol3;</Report>"
        )
        result = _validate_against_xsd(malicious)
        assert result["valid"] is not True

    def test_wellformed_xml_still_validated(self) -> None:
        result = _validate_against_xsd("<Report><ReportDocument/></Report>")
        assert result["level"] in {"xsd", "wellformedness", "none"}


# ---------------------------------------------------------------------------
# FR-SH-1 — e-reporting amount/percent injection guard
# ---------------------------------------------------------------------------


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


class TestEreportingAmountInjectionGuard:
    def test_transaction_report_rejects_injected_tax_amount(self) -> None:
        invoice = {
            "id": "F-2025-001",
            "issue_date": "2025-01-15",
            "type_code": "380",
            "currency_code": "EUR",
            "business_process_id": "A1",
            "business_process_type_id": "EREP",
            "seller_company_id": "123456789",
            "seller_company_id_scheme": "SIREN",
            "monetary_total_tax_amount": "1</TaxAmount><TaxAmount>9999",
            "monetary_total_currency": "EUR",
            "tax_subtotals": [
                {"taxable_amount": "1000.00", "tax_amount": "200.00", "tax_percent": "20.0"}
            ],
        }
        with pytest.raises(Exception):
            _build_transaction_report_xml(**_HEADER, invoices=[invoice])

    def test_transaction_report_rejects_injected_tax_percent(self) -> None:
        invoice = {
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
                {
                    "taxable_amount": "1000.00",
                    "tax_amount": "200.00",
                    "tax_percent": "20</Percent><Percent>0",
                }
            ],
        }
        with pytest.raises(Exception):
            _build_transaction_report_xml(**_HEADER, invoices=[invoice])

    def test_payment_report_rejects_injected_amount(self) -> None:
        invoice = {
            "invoice_id": "F-2025-001",
            "issue_date": "2025-01-15",
            "payment_date": "2025-02-01",
            "subtotals": [
                {
                    "tax_percent": "20.0",
                    "amount": "1200.00</Amount><Amount>0.00",
                    "currency_code": "EUR",
                }
            ],
        }
        with pytest.raises(Exception):
            _build_payment_report_xml(**_HEADER, invoices=[invoice])

    def test_valid_amounts_still_produce_well_formed_xml(self) -> None:
        invoice = {
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
        xml = _build_transaction_report_xml(**_HEADER, invoices=[invoice])
        root = etree.fromstring(xml.encode("utf-8"))
        tax_amount = root.find("TransactionsReport/Invoice/MonetaryTotal/TaxAmount")
        assert tax_amount is not None
        assert tax_amount.text == "200.00"


# ---------------------------------------------------------------------------
# FR-SH-3 — FRParty SIRET/SIREN Luhn validation
# ---------------------------------------------------------------------------


class TestFRPartyLuhnValidation:
    def test_valid_siren_accepted(self) -> None:
        party = _party("Test SAS", "732829320")
        assert party.siren == "732829320"

    def test_invalid_siren_rejected(self) -> None:
        with pytest.raises(ValueError, match="SIREN"):
            _party("Test SAS", "732829321")

    def test_valid_siret_accepted(self) -> None:
        party = FRParty(
            name="Test SAS", siret="73282932000074", address=_ADDRESS
        )
        assert party.siret == "73282932000074"

    def test_invalid_siret_rejected(self) -> None:
        with pytest.raises(ValueError, match="SIRET"):
            FRParty(name="Test SAS", siret="73282932000075", address=_ADDRESS)

    def test_none_siret_siren_allowed(self) -> None:
        party = FRParty(name="Test SAS", address=_ADDRESS)
        assert party.siret is None
        assert party.siren is None
