"""
Fixture discovery for the bundled AFNOR worked examples under specs/.

specs/ is excluded from both the wheel and sdist (see pyproject.toml), so a
wheel-installed copy of this package has no specs/ directory. Collection
must not fail in that case — tests parametrized over these fixtures are
skipped instead.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent.parent
_SPECS_DIR = _PACKAGE_ROOT / "specs"
_ANNEX_B_ROOT = (
    _SPECS_DIR
    / "XP_Z12-014_V1.4_annexes"
    / "FR_and_ENG_XP_Z12-014_CAS_USAGE_Annexes_A_et_B_EXEMPLES_V1.4"
    / "XP_Z12-014_CAS_USAGE_Annexe_B_V1.4"
)
_CDAR_EXAMPLES_DIR = _SPECS_DIR / "examples" / "cdar"

SPECS_AVAILABLE: bool = _SPECS_DIR.is_dir()


def _profile_from_filename(name: str) -> str | None:
    """Derive the Factur-X Schematron profile from a worked-example filename.

    Checks EXTENDED-CTC-FR before EXTENDED since the former's filename
    substring contains the latter's.
    """
    if "EXTENDED-CTC-FR" in name:
        return "EXTENDED-CTC-FR"
    if "EXTENDED" in name:
        return "EXTENDED"
    if "EN16931" in name:
        return "EN16931"
    return None


def discover_annex_b_cii_examples() -> list[tuple[str, Path, str]]:
    """Discover bundled Annex B v1.4 CII invoice examples with their profile.

    Returns a list of (label, path, profile) tuples for every
    "*_FX_CII_Commentee.xml" file under the Annex B v1.4 example tree, or an
    empty list if specs/ is not present (wheel-installed copy).
    """
    if not SPECS_AVAILABLE or not _ANNEX_B_ROOT.is_dir():
        return []
    results: list[tuple[str, Path, str]] = []
    for path in sorted(_ANNEX_B_ROOT.rglob("*_FX_CII_Commentee.xml")):
        profile = _profile_from_filename(path.name)
        if profile is None:
            continue
        label = str(path.relative_to(_ANNEX_B_ROOT))
        results.append((label, path, profile))
    return results


def discover_cdar_examples() -> list[tuple[str, Path]]:
    """Discover bundled CDAR worked examples (11 under specs/examples/cdar/
    plus the UC3/UC5 dispute variants under the Annex B v1.4 tree), or an
    empty list if specs/ is not present.
    """
    if not SPECS_AVAILABLE:
        return []
    results: list[tuple[str, Path]] = []
    if _CDAR_EXAMPLES_DIR.is_dir():
        for path in sorted(_CDAR_EXAMPLES_DIR.glob("*.xml")):
            results.append((path.name, path))
    if _ANNEX_B_ROOT.is_dir():
        for path in sorted(_ANNEX_B_ROOT.rglob("*-CDV-*.xml")):
            label = str(path.relative_to(_ANNEX_B_ROOT))
            if (label, path) not in results and not any(
                p.name == path.name for _, p in results
            ):
                results.append((label, path))
    return results
