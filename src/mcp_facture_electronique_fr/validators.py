"""Factur-X document validation — Schematron (SVRL) checks per profile.

Stylesheets are pre-compiled Skeleton Schematron XSLT files bundled under
resources/facturx/<PROFILE>/ (FNFE-MPE Factur-X 1.09.2, no AFNOR copyright
restriction — see specs/README.md). They are the dev-reference copies at
specs/facturx/<PROFILE>/XSLT/, mirrored here because specs/ is excluded from
the published wheel/sdist (pyproject.toml).

FR-XSLT2-1 (resolved in mcp-einvoicing-core 1.14.0): the FNFE-MPE Factur-X
1.09.2 Schematron stylesheets use XPath 2.0 constructs (`every ... satisfies`,
`string-join`) that `lxml`/`libxslt` (XSLT 1.0 only) cannot compile. This was
the same core-level gap tracked for ZUGFeRD as DE-XSLT2-1. Core now provides
`load_schematron_validator()`, which auto-dispatches to `SchematronValidator`
(XSLT 1.x) or `SaxonSchematronValidator` (XSLT 2.x/3.x, via the optional
`saxonche` extra) based on the stylesheet's declared version — all five
bundled profiles here are XSLT 2.0, so this resolves to `SaxonSchematronValidator`.
Callers must install `mcp-einvoicing-core[xslt2]` for validate_facturx to work;
`get_facturx_validator()` surfaces a missing `saxonche` install as
`FacturXStylesheetUnsupportedError` rather than letting the underlying
`ImportError` propagate, so callers get a clear, structured "not available"
result instead of a stack trace.

Only the five profiles that ship a Schematron ruleset in this delivery are
modelled: MINIMUM, BASICWL, BASIC, EN16931, EXTENDED. XRECHNUNG has no bundled
ruleset. EXTENDED-CTC-FR (the French CTC extension of EXTENDED, BT-24 profile
URN suffix `#conformant#urn.cpro.gouv.fr:1p0:extended-ctc-fr`) maps to the
generic EXTENDED ruleset — AFNOR has not published a CTC-FR-specific
Schematron; French-specific rules on top of EXTENDED remain [Unverified] by
this validator.
"""

from __future__ import annotations

from pathlib import Path

from mcp_einvoicing_core.schematron import BaseStructuredValidator, load_schematron_validator

_RESOURCES_DIR = Path(__file__).parent / "resources" / "facturx"

_STYLESHEET_MAP: dict[str, Path] = {
    "MINIMUM": _RESOURCES_DIR / "MINIMUM" / "FACTUR-X_MINIMUM.xslt",
    "BASICWL": _RESOURCES_DIR / "BASICWL" / "FACTUR-X_BASIC-WL.xslt",
    "BASIC": _RESOURCES_DIR / "BASIC" / "FACTUR-X_BASIC.xslt",
    "EN16931": _RESOURCES_DIR / "EN16931" / "FACTUR-X_EN16931.xslt",
    "EXTENDED": _RESOURCES_DIR / "EXTENDED" / "FACTUR-X_EXTENDED.xslt",
    # EXTENDED-CTC-FR reuses the generic EXTENDED ruleset — see module docstring.
    "EXTENDED-CTC-FR": _RESOURCES_DIR / "EXTENDED" / "FACTUR-X_EXTENDED.xslt",
}

SUPPORTED_FACTURX_PROFILES: tuple[str, ...] = tuple(_STYLESHEET_MAP)

_validators: dict[str, BaseStructuredValidator] = {}


class UnsupportedFacturXProfileError(ValueError):
    """Raised when the requested profile has no bundled Schematron ruleset."""


class FacturXStylesheetUnsupportedError(RuntimeError):
    """Raised when a bundled stylesheet cannot be compiled by the resolved backend.

    Most commonly this fires when `saxonche` (the `mcp-einvoicing-core[xslt2]`
    extra) is not installed — every bundled Factur-X 1.09.2 stylesheet requires
    the Saxon-HE backend. See FR-XSLT2-1 in the module docstring.
    """


def get_facturx_validator(profile: str) -> BaseStructuredValidator:
    """Return a cached validator for *profile*, building it on first use.

    Dispatches to core's `load_schematron_validator()`, which resolves to
    `SaxonSchematronValidator` for these XSLT 2.0 stylesheets (FR-XSLT2-1).

    Raises:
        UnsupportedFacturXProfileError: profile has no bundled ruleset.
        FacturXStylesheetUnsupportedError: ruleset exists but the required
            backend is unavailable (e.g. `saxonche` not installed) or the
            stylesheet failed to compile.
    """
    validator = _validators.get(profile)
    if validator is not None:
        return validator

    path = _STYLESHEET_MAP.get(profile)
    if path is None:
        msg = (
            f"Unsupported Factur-X profile: {profile!r}. "
            f"Supported: {', '.join(SUPPORTED_FACTURX_PROFILES)}."
        )
        raise UnsupportedFacturXProfileError(msg)

    try:
        validator = load_schematron_validator(path)
    except ImportError as exc:
        msg = (
            f"Factur-X profile {profile!r} stylesheet requires XSLT 2.0 (Saxon-HE), "
            "which is not installed. Install with: pip install "
            f"mcp-einvoicing-core[xslt2]. Underlying error: {exc}"
        )
        raise FacturXStylesheetUnsupportedError(msg) from exc
    except ValueError as exc:
        msg = (
            f"Factur-X profile {profile!r} stylesheet could not be compiled. "
            f"Underlying error: {exc}"
        )
        raise FacturXStylesheetUnsupportedError(msg) from exc

    _validators[profile] = validator
    return validator
