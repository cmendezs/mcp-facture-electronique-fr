"""French e-invoicing Pydantic models.

Re-exports the invoice-tree models (FRParty, FRInvoice, Factur-X profile
constants) from models.invoice, preserving the pre-package import path
`mcp_facture_electronique_fr.models`. PPF Annuaire write-path models live in
models.annuaire and are imported directly from there.
"""

from __future__ import annotations

from mcp_facture_electronique_fr.models.invoice import (
    FACTURX_PROFILE_BASIC,
    FACTURX_PROFILE_BASICWL,
    FACTURX_PROFILE_EN16931,
    FACTURX_PROFILE_EXTENDED,
    FACTURX_PROFILE_MINIMUM,
    FACTURX_PROFILE_XRECHNUNG,
    FACTURX_SCHEME_ID,
    FR_CII_PROFILE_URN,
    FR_EXTENDED_CTC_FR_PROFILE_URN,
    FR_UBL_PROFILE_URN,
    FacturXProfile,
    FRInvoice,
    FRParty,
)

__all__ = [
    "FACTURX_PROFILE_BASIC",
    "FACTURX_PROFILE_BASICWL",
    "FACTURX_PROFILE_EN16931",
    "FACTURX_PROFILE_EXTENDED",
    "FACTURX_PROFILE_MINIMUM",
    "FACTURX_PROFILE_XRECHNUNG",
    "FACTURX_SCHEME_ID",
    "FR_CII_PROFILE_URN",
    "FR_EXTENDED_CTC_FR_PROFILE_URN",
    "FR_UBL_PROFILE_URN",
    "FacturXProfile",
    "FRInvoice",
    "FRParty",
]
