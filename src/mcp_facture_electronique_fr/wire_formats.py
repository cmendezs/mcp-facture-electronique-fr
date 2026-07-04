"""French wire-format serialisers and parsers — NF XP Z12-012 v1.4 (June 2026) / EN 16931.

Extends the core EN 16931 UBL 2.1 and CII serialisers/parsers with:

    FRUBLSerializer   — FRInvoice → UBL 2.1 XML (NF XP Z12-012 profile)
    FRUBLParser       — UBL 2.1 XML → FRInvoice
    FRCIISerializer   — FRInvoice → CII XML with Factur-X schemeID attribute
    FRCIIParser       — CII XML → FRInvoice

The CII serialiser adds the mandatory schemeID="urn:cen.eu:en16931:2017"
attribute on the GuidelineSpecifiedDocumentContextParameter/ID element,
required by the Factur-X 1.0.07 specification §3.4.

Profile URNs verified against NF XP Z12-012 v1.3 §4.4.2. Also cited against v1.4
(June 2026) [Unverified against v1.4].
"""

from __future__ import annotations

from lxml import etree

from mcp_einvoicing_core.wire_formats import (
    EN16931CIIParser,
    EN16931CIISerializer,
    EN16931UBLParser,
    EN16931UBLSerializer,
    _RAM,  # noqa: PLC2701
    _RSM,  # noqa: PLC2701
    CII_NSMAP,
)

from mcp_facture_electronique_fr.models import FACTURX_SCHEME_ID, FRInvoice


def _q(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


# ---------------------------------------------------------------------------
# UBL 2.1
# ---------------------------------------------------------------------------


class FRUBLSerializer(EN16931UBLSerializer):
    """Serialise a FRInvoice to UBL 2.1 XML (NF XP Z12-012 v1.4, June 2026).

    The base class handles the full EN 16931 field set including PartyTaxScheme
    emission when vat_id is set (auto-synced from FRParty.tva_intra).
    """

    def serialize(self, invoice: FRInvoice) -> bytes:  # type: ignore[override]
        return super().serialize(invoice)


class FRUBLParser(EN16931UBLParser):
    """Parse UBL 2.1 XML into a FRInvoice.

    Overrides parse() to return FRInvoice.  SIRET/SIREN extraction from
    PartyLegalEntity will be added once FR-SIRET-1 is resolved in core.
    """

    def parse(self, xml_bytes: bytes) -> FRInvoice:  # type: ignore[override]
        base = super().parse(xml_bytes)
        return FRInvoice(**base.model_dump())


# ---------------------------------------------------------------------------
# CII (Cross Industry Invoice) — Factur-X payload
# ---------------------------------------------------------------------------


class FRCIISerializer(EN16931CIISerializer):
    """Serialise a FRInvoice to CII XML with Factur-X schemeID attribute.

    Overrides _build_root to add schemeID="urn:cen.eu:en16931:2017" on the
    GuidelineSpecifiedDocumentContextParameter/ID element, as required by
    Factur-X 1.0.07 §3.4.  The profile URN value comes from invoice.profile
    and must be one of the FacturXProfile constants defined in models.py.
    """

    def serialize(self, invoice: FRInvoice) -> bytes:  # type: ignore[override]
        return super().serialize(invoice)

    def _build_root(self, invoice: FRInvoice) -> etree._Element:  # type: ignore[override]
        root = etree.Element(_q(_RSM, "CrossIndustryInvoice"), nsmap=CII_NSMAP)

        ctx = etree.SubElement(root, _q(_RSM, "ExchangedDocumentContext"))
        guideline = etree.SubElement(
            ctx, _q(_RAM, "GuidelineSpecifiedDocumentContextParameter")
        )
        profile_id = etree.SubElement(guideline, _q(_RAM, "ID"), text=invoice.profile)
        profile_id.set("schemeID", FACTURX_SCHEME_ID)

        # Delegate the remainder of the document to the base class by rebuilding
        # from the base implementation and replacing the context block.
        # We call the grandparent _build_root and then patch the first child.
        base_root = super()._build_root(invoice)

        # Replace the ExchangedDocumentContext subtree with the one that has schemeID.
        existing_ctx = base_root.find(_q(_RSM, "ExchangedDocumentContext"))
        if existing_ctx is not None:
            idx = list(base_root).index(existing_ctx)
            base_root.remove(existing_ctx)
            base_root.insert(idx, ctx)

        return base_root


class FRCIIParser(EN16931CIIParser):
    """Parse CII XML (Factur-X payload) into a FRInvoice.

    Overrides parse() to return FRInvoice.  SIRET/SIREN extraction will be
    added once FR-SIRET-1 is resolved in core.
    """

    def parse(self, xml_bytes: bytes) -> FRInvoice:  # type: ignore[override]
        base = super().parse(xml_bytes)
        return FRInvoice(**base.model_dump())
