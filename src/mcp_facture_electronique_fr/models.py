"""French e-invoicing Pydantic models — NF XP Z12-012 / EN 16931.

All three formats accepted by the French reform (Factur-X, UBL 2.1, CII)
are explicitly based on EN 16931 (NF EN 16931-1).  The primary invoice class
therefore extends EN16931Invoice from mcp-einvoicing-core.

FR-specific fields (SIRET, SIREN, TVA intracommunautaire) are optional
extensions on FRParty. Validation delegates to core TaxIdentifier.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field, field_validator, model_validator

from mcp_einvoicing_core.en16931 import EN16931Invoice, EN16931Party
from mcp_einvoicing_core.models import TaxIdentifier

# ---------------------------------------------------------------------------
# Factur-X profile URN constants (NF XP Z12-012 / Factur-X 1.0.07)
# Profile URNs are embedded in the CII payload as ram:ID in the
# GuidelineSpecifiedDocumentContextParameter element.
# ---------------------------------------------------------------------------

FacturXProfile = Literal[
    "urn:factur-x.eu:1p0:minimum",
    "urn:factur-x.eu:1p0:basicwl",
    "urn:factur-x.eu:1p0:basic",
    "urn:factur-x.eu:1p0:en16931",
    "urn:factur-x.eu:1p0:extended",
    "urn:factur-x.eu:1p0:xrechnung",
]

FACTURX_PROFILE_MINIMUM: str = "urn:factur-x.eu:1p0:minimum"
FACTURX_PROFILE_BASICWL: str = "urn:factur-x.eu:1p0:basicwl"
FACTURX_PROFILE_BASIC: str = "urn:factur-x.eu:1p0:basic"
FACTURX_PROFILE_EN16931: str = "urn:factur-x.eu:1p0:en16931"
FACTURX_PROFILE_EXTENDED: str = "urn:factur-x.eu:1p0:extended"
FACTURX_PROFILE_XRECHNUNG: str = "urn:factur-x.eu:1p0:xrechnung"

# CII schemeID attribute value for Factur-X profile URN elements
# Source: Factur-X 1.0.07 spec §3.4
FACTURX_SCHEME_ID: str = "urn:cen.eu:en16931:2017"

# Profile URNs for BT-24 (NF XP Z12-012 v1.3, §4.4.2).
# EN16931 profile uses the same URN for both UBL and CII syntaxes.
FR_UBL_PROFILE_URN: str = "urn:cen.eu:en16931:2017"
FR_CII_PROFILE_URN: str = "urn:cen.eu:en16931:2017"

# EXTENDED-CTC-FR profile URN (NF XP Z12-012 v1.3, §4.4.2).
FR_EXTENDED_CTC_FR_PROFILE_URN: str = (
    "urn:cen.eu:en16931:2017#conformant#urn.cpro.gouv.fr:1p0:extended-ctc-fr"
)


# ---------------------------------------------------------------------------
# Party model
# ---------------------------------------------------------------------------


class FRParty(EN16931Party):
    """French trading party — adds SIRET and SIREN identifiers.

    SIRET: 14-digit INSEE establishment identifier (SIREN 9 + NIC 5).
    SIREN: 9-digit INSEE enterprise identifier.
    Both use the Luhn check-digit algorithm.

    Validation delegates to TaxIdentifier.validate_fr_siret/siren/tva_intra in core.
    """

    siret: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "SIRET — 14-digit INSEE establishment identifier (SIREN 9 + NIC 5). "
                "Format: [0-9]{14}. Check digit: Luhn algorithm on all 14 digits."
            ),
            pattern=r"^\d{14}$",
        ),
    ] = None

    siren: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "SIREN — 9-digit INSEE enterprise identifier. "
                "Format: [0-9]{9}. Check digit: Luhn algorithm on all 9 digits."
            ),
            pattern=r"^\d{9}$",
        ),
    ] = None

    tva_intra: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "TVA intracommunautaire (BT-31 seller / BT-48 buyer). "
                "Format: FR + 2 check digits + 9-digit SIREN. "
                "Check key: (12 + 3 * (SIREN mod 97)) mod 97."
            ),
        ),
    ] = None

    @field_validator("tva_intra")
    @classmethod
    def _validate_tva_intra(cls, v: str | None) -> str | None:
        if v is None:
            return v
        ok, error = TaxIdentifier.validate_fr_tva_intra(v)
        if not ok:
            msg = f"Invalid TVA intracommunautaire: {error}"
            raise ValueError(msg)
        return v.replace(" ", "").upper()

    @model_validator(mode="after")
    def _sync_tva_to_vat_id(self) -> FRParty:
        if self.tva_intra and not self.vat_id:
            normalized = self.tva_intra if self.tva_intra.startswith("FR") else f"FR{self.tva_intra}"
            self.vat_id = normalized
        return self


# ---------------------------------------------------------------------------
# Invoice model
# ---------------------------------------------------------------------------


class FRInvoice(EN16931Invoice):
    """French electronic invoice — NF XP Z12-012 / EN 16931.

    Extends EN16931Invoice with French-specific party identifiers.
    Accepted formats: Factur-X (PDF/A-3 + CII), UBL 2.1, CII (NF XP Z12-012).

    The `profile` field should be one of the FacturXProfile URNs for Factur-X
    submissions, or FR_UBL_PROFILE_URN / FR_CII_PROFILE_URN for UBL/CII.
    """

    seller: FRParty = Field(..., description="Seller (BG-4) with optional SIRET/SIREN")
    buyer: FRParty = Field(..., description="Buyer (BG-7) with optional SIRET/SIREN")
