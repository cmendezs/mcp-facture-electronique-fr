"""Tests for French-specific Pydantic models."""

from __future__ import annotations

import pytest

from mcp_facture_electronique_fr.models import FRParty


class TestFRPartyTvaIntra:
    def _minimal_party(self, **kwargs) -> FRParty:
        defaults = {"name": "Test SAS", "address": {
            "line_one": "1 rue de Rivoli",
            "city": "Paris",
            "postcode": "75001",
            "country_code": "FR",
        }}
        defaults.update(kwargs)
        return FRParty(**defaults)

    def test_valid_tva_intra(self) -> None:
        party = self._minimal_party(tva_intra="FR44732829320")
        assert party.tva_intra == "FR44732829320"

    def test_tva_intra_normalized(self) -> None:
        party = self._minimal_party(tva_intra="fr 44 732 829 320")
        assert party.tva_intra == "FR44732829320"

    def test_tva_intra_syncs_to_vat_id(self) -> None:
        party = self._minimal_party(tva_intra="FR44732829320")
        assert party.vat_id == "FR44732829320"

    def test_tva_intra_does_not_override_explicit_vat_id(self) -> None:
        party = self._minimal_party(tva_intra="FR44732829320", vat_id="DE123456789")
        assert party.vat_id == "DE123456789"

    def test_invalid_tva_intra_rejected(self) -> None:
        with pytest.raises(ValueError, match="TVA intracommunautaire"):
            self._minimal_party(tva_intra="FR00732829320")

    def test_none_tva_intra_allowed(self) -> None:
        party = self._minimal_party()
        assert party.tva_intra is None
        assert party.vat_id is None
