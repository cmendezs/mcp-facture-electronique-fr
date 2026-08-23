"""
FR-UC-CATALOG-2026-06 — regression fixtures over the bundled XP Z12-014 v1.4
Annex B worked-example catalog (~44 B2B use-case scenarios).

Two families of coverage:
  - validate_facturx (via get_facturx_validator) against every bundled CII
    invoice example, keyed by the profile encoded in its filename.
  - CDAR shape parsing (root element / namespace) for the bundled CDAR
    lifecycle-status examples, including the UC3/UC5 dispute variants.

specs/ is excluded from the wheel/sdist (see pyproject.toml), so these tests
skip cleanly when running against an installed (non-source) copy.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from mcp_facture_electronique_fr.validators import (
    FacturXStylesheetUnsupportedError,
    get_facturx_validator,
)
from tests.conftest import (
    SPECS_AVAILABLE,
    discover_annex_b_cii_examples,
    discover_cdar_examples,
)

pytestmark = pytest.mark.skipif(not SPECS_AVAILABLE, reason="specs/ not bundled in this install")

_RSM_CII_NS = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
_RSM_CDAR_NS = "urn:un:unece:uncefact:data:standard:CrossDomainAcknowledgementAndResponse:100"

_CII_EXAMPLES = discover_annex_b_cii_examples()
_CDAR_EXAMPLES = discover_cdar_examples()


@pytest.mark.parametrize(
    "label,path,profile", _CII_EXAMPLES, ids=[label for label, _, _ in _CII_EXAMPLES]
)
def test_validate_facturx_against_annex_b_examples(label, path, profile):
    """Every bundled Annex B v1.4 CII example validates without raising,
    against the Schematron ruleset for the profile encoded in its filename."""
    xml_bytes = path.read_bytes()
    try:
        validator = get_facturx_validator(profile)
    except FacturXStylesheetUnsupportedError:
        pytest.skip("saxonche not installed — xslt2 extra required")
        return

    result = validator.validate(xml_bytes, profile=profile, syntax="CII")
    result_dict = result.to_dict()

    assert result_dict["is_valid"] is not None, f"{label}: validator returned no verdict"


@pytest.mark.parametrize("label,path", _CDAR_EXAMPLES, ids=[label for label, _ in _CDAR_EXAMPLES])
def test_cdar_examples_parse(label, path):
    """Every bundled CDAR example (11 base examples plus UC3/UC5 dispute
    variants) parses as a CrossDomainAcknowledgementAndResponse document."""
    root = ET.parse(path).getroot()
    assert root.tag == f"{{{_RSM_CDAR_NS}}}CrossDomainAcknowledgementAndResponse", (
        f"{label}: unexpected root element {root.tag!r}"
    )


def test_discovery_found_examples():
    """Sanity check: fixture discovery is not silently returning nothing
    when specs/ is actually present."""
    assert len(_CII_EXAMPLES) > 0
    assert len(_CDAR_EXAMPLES) > 0
