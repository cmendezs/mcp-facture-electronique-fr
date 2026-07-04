"""
Unit tests for Factur-X validation (validators.py, tools/facturx_tools.py).

Covers:
  - Resource bundling: stylesheet paths resolve under the installed package
  - Unsupported profile name -> UnsupportedFacturXProfileError
  - FR-XSLT2-1 (resolved in mcp-einvoicing-core 1.14.0): bundled profiles
    resolve to SaxonSchematronValidator and actually validate
  - MCP tool: validate_facturx returns real Schematron findings
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client
from mcp_einvoicing_core.schematron import SaxonSchematronValidator

from mcp_facture_electronique_fr.server import mcp
from mcp_facture_electronique_fr.validators import (
    SUPPORTED_FACTURX_PROFILES,
    UnsupportedFacturXProfileError,
    get_facturx_validator,
)


def _parse(result) -> dict | list:
    return json.loads(result.content[0].text)


class TestValidatorResourceResolution:
    def test_all_supported_profiles_have_a_bundled_stylesheet(self):
        from mcp_facture_electronique_fr.validators import _STYLESHEET_MAP

        for profile in SUPPORTED_FACTURX_PROFILES:
            assert _STYLESHEET_MAP[profile].exists(), (
                f"Bundled stylesheet missing for profile {profile!r}"
            )


class TestGetFacturxValidator:
    def test_unsupported_profile_raises(self):
        with pytest.raises(UnsupportedFacturXProfileError):
            get_facturx_validator("NOT-A-PROFILE")

    @pytest.mark.parametrize("profile", SUPPORTED_FACTURX_PROFILES)
    def test_bundled_profiles_resolve_to_saxon_backend(self, profile):
        """FR-XSLT2-1: all bundled stylesheets are XSLT 2.0 -> SaxonSchematronValidator."""
        validator = get_facturx_validator(profile)
        assert isinstance(validator, SaxonSchematronValidator)

    def test_validator_is_cached(self):
        first = get_facturx_validator("EN16931")
        second = get_facturx_validator("EN16931")
        assert first is second


class TestValidateFacturxTool:
    @pytest.mark.asyncio
    async def test_minimal_xml_returns_schematron_findings(self):
        """`<root/>` matches the "no empty elements" rule (warning, not error)."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "validate_facturx",
                {"xml_content": "<root/>", "profile": "EN16931"},
            )
        payload = _parse(result)
        assert payload["level"] == "schematron"
        assert payload["is_valid"] is True
        assert payload["warning_count"] > 0

    @pytest.mark.asyncio
    async def test_unsupported_profile_returns_profile_error(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "validate_facturx",
                {"xml_content": "<root/>", "profile": "BOGUS"},
            )
        payload = _parse(result)
        assert payload["is_valid"] is False
        assert payload["level"] == "profile-error"
        assert payload["error_count"] == 1
