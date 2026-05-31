"""French e-invoicing Pydantic models — NF XP Z12-012 / EN 16931.

All three formats accepted by the French reform (Factur-X, UBL 2.1, CII)
are explicitly based on EN 16931 (NF EN 16931-1).  The primary invoice class
therefore extends EN16931Invoice from mcp-einvoicing-core.

FR-specific fields (SIRET, SIREN) are optional extensions on FRParty.
Validation of SIRET/SIREN check digits is not yet implemented in core:
# [GAP id=FR-SIRET-1 description="SIRET/SIREN Luhn validator not yet in core TaxIdentifier"]
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field

from mcp_einvoicing_core.en16931 import EN16931Invoice, EN16931Party

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

# [Unverified] UBL 2.1 profile URN mandated by NF XP Z12-012.
# Current value uses the Peppol BIS 3.0 URN as a placeholder.
# Verify the exact URN against NF XP Z12-012 §— before production use.
FR_UBL_PROFILE_URN: str = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)

# [Unverified] CII profile URN mandated by NF XP Z12-012 for standalone CII.
FR_CII_PROFILE_URN: str = "urn:cen.eu:en16931:2017"


# ---------------------------------------------------------------------------
# Party model
# ---------------------------------------------------------------------------


class FRParty(EN16931Party):
    """French trading party — adds SIRET and SIREN identifiers.

    SIRET: 14-digit INSEE establishment identifier (SIREN 9 + NIC 5).
    SIREN: 9-digit INSEE enterprise identifier.
    Both use the Luhn check-digit algorithm.

    Validation of check digits requires TaxIdentifier.validate_fr_siret() in core.
    # [GAP id=FR-SIRET-1 description="SIRET/SIREN Luhn validator not yet in core TaxIdentifier"]
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
