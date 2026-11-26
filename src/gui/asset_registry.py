"""Canonical Asset Registry & Validator for GRIDUCTIVE — Detective Case Files.

Pure Python (standard library only, zero PySide6 dependency) so it can be
imported and validated from any working directory before or after Qt setup.

Responsibilities:
    1. Locate the repository's ``assets/`` root independent of CWD.
    2. Provide centralized, strongly-named asset IDs (no scattered string paths).
    3. Support opting into non-destructive alpha-cleaned derived PNGs while
       preserving all 18 original V1.2 files untouched.
    4. Gracefully report missing assets without crashing domain code.
    5. Validate ``assets/manifest.json`` and PNG headers/dimensions deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import struct
from typing import Mapping, Optional


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class AssetId(str, Enum):
    """Canonical identifiers for all 18 original V1.2 PNG assets."""

    # Branding
    A04_LOGO_WIDE = "A04_LOGO_WIDE"
    A04_APP_EMBLEM = "A04_APP_EMBLEM"

    # Backgrounds
    A03_MAIN_MENU_BACKGROUND = "A03_MAIN_MENU_BACKGROUND"
    A05_GAMEPLAY_BACKGROUND = "A05_GAMEPLAY_BACKGROUND"

    # Character Cards
    A01_CARD_BACK = "A01_CARD_BACK"
    A02_CARD_FRONT_TEMPLATE = "A02_CARD_FRONT_TEMPLATE"

    # Case Covers (Decorative Level Selection illustrations ONLY)
    A06_CASE_COVER_3X3 = "A06_CASE_COVER_3X3"
    A06_CASE_COVER_4X4 = "A06_CASE_COVER_4X4"
    A06_CASE_COVER_5X5 = "A06_CASE_COVER_5X5"

    # Results
    A07_CASE_CLOSED_EMBLEM = "A07_CASE_CLOSED_EMBLEM"

    # Evidence Texture (Non-seamless decorative artwork)
    A08_EVIDENCE_TEXTURE = "A08_EVIDENCE_TEXTURE"

    # Clue Icons (Legacy V1.2 RGB + New Vietnamese 512x512 RGBA set)
    A10_CLUE_ICON_ATLAS = "A10_CLUE_ICON_ATLAS"
    A10_FACT = "A10_FACT"
    A10_SAME = "A10_SAME"
    A10_DIFFERENT = "A10_DIFFERENT"
    A10_EXACTLY = "A10_EXACTLY"
    A10_AT_LEAST = "A10_AT_LEAST"
    A10_AT_MOST = "A10_AT_MOST"
    A10_PARITY = "A10_PARITY"
    A10_COUNT_COMPARE = "A10_COUNT_COMPARE"


ORIGINAL_RELATIVE_PATHS: Mapping[AssetId, str] = {
    AssetId.A04_LOGO_WIDE: "branding/A04_logo_wide.png",
    AssetId.A04_APP_EMBLEM: "branding/A04_app_emblem.png",
    AssetId.A03_MAIN_MENU_BACKGROUND: "backgrounds/A03_main_menu_background.png",
    AssetId.A05_GAMEPLAY_BACKGROUND: "backgrounds/A05_gameplay_background.png",
    AssetId.A01_CARD_BACK: "cards/A01_card_back.png",
    AssetId.A02_CARD_FRONT_TEMPLATE: "cards/A02_card_front_template.png",
    AssetId.A06_CASE_COVER_3X3: "case_covers/A06_case_cover_3x3.png",
    AssetId.A06_CASE_COVER_4X4: "case_covers/A06_case_cover_4x4.png",
    AssetId.A06_CASE_COVER_5X5: "case_covers/A06_case_cover_5x5.png",
    AssetId.A07_CASE_CLOSED_EMBLEM: "results/A07_case_closed_emblem.png",
    AssetId.A08_EVIDENCE_TEXTURE: "textures/A08_evidence_texture.png",
    AssetId.A10_CLUE_ICON_ATLAS: "clue_icons/A10_clue_icon_atlas.png",
    AssetId.A10_FACT: "clue_icons/A10_fact.png",
    AssetId.A10_SAME: "clue_icons/A10_same.png",
    AssetId.A10_DIFFERENT: "clue_icons/A10_different.png",
    AssetId.A10_EXACTLY: "clue_icons/A10_exactly.png",
    AssetId.A10_AT_LEAST: "clue_icons/A10_at_least.png",
    AssetId.A10_AT_MOST: "clue_icons/A10_at_most.png",
}

DERIVED_RELATIVE_PATHS: Mapping[AssetId, str] = {
    AssetId.A04_LOGO_WIDE: "derived/A04_logo_wide_clean.png",
    AssetId.A04_APP_EMBLEM: "derived/A04_app_emblem_clean.png",
    AssetId.A07_CASE_CLOSED_EMBLEM: "derived/A07_case_closed_emblem_clean.png",
}

CASE_COVER_BY_GRID_SIZE: Mapping[int, AssetId] = {
    3: AssetId.A06_CASE_COVER_3X3,
    4: AssetId.A06_CASE_COVER_4X4,
    5: AssetId.A06_CASE_COVER_5X5,
}

CLUE_ICON_BY_TYPE: Mapping[str, AssetId] = {
    "FACT": AssetId.A10_FACT,
    "SAME": AssetId.A10_SAME,
    "DIFFERENT": AssetId.A10_DIFFERENT,
    "EXACTLY": AssetId.A10_EXACTLY,
    "AT_LEAST": AssetId.A10_AT_LEAST,
    "AT_MOST": AssetId.A10_AT_MOST,
}

# Production 8-icon Vietnamese RGBA set (from GRIDUCTIVE_8_Clue_Icons_Vietnamese.zip)
VIETNAMESE_CLUE_ICON_IDS: Mapping[str, AssetId] = {
    "FACT": AssetId.A10_FACT,
    "SAME": AssetId.A10_SAME,
    "DIFFERENT": AssetId.A10_DIFFERENT,
    "EXACTLY": AssetId.A10_EXACTLY,
    "AT_LEAST": AssetId.A10_AT_LEAST,
    "AT_MOST": AssetId.A10_AT_MOST,
    "PARITY": AssetId.A10_PARITY,
    "COUNT_COMPARE": AssetId.A10_COUNT_COMPARE,
}

VIETNAMESE_CLUE_ICON_PATHS: Mapping[str, str] = {
    "FACT": "clue_icons/A10_fact_vi.png",
    "SAME": "clue_icons/A10_same_vi.png",
    "DIFFERENT": "clue_icons/A10_different_vi.png",
    "EXACTLY": "clue_icons/A10_exactly_vi.png",
    "AT_LEAST": "clue_icons/A10_at_least_vi.png",
    "AT_MOST": "clue_icons/A10_at_most_vi.png",
    "PARITY": "clue_icons/A10_parity_vi.png",
    "COUNT_COMPARE": "clue_icons/A10_count_compare_vi.png",
}

VIETNAMESE_CLUE_LABELS: Mapping[str, str] = {
    "FACT": "SỰ THẬT",
    "SAME": "CÙNG PHE",
    "DIFFERENT": "KHÁC PHE",
    "EXACTLY": "CHÍNH XÁC",
    "AT_LEAST": "ÍT NHẤT",
    "AT_MOST": "NHIỀU NHẤT",
    "PARITY": "CHẴN / LẺ",
    "COUNT_COMPARE": "SO SÁNH SỐ LƯỢNG",
    "IMPLIES": "NẾU · THÌ",
}


@dataclass(frozen=True, slots=True)
class AssetResolution:
    """Result of resolving one asset without raising on missing optional files."""

    asset_id: AssetId
    path: Optional[Path]
    exists: bool
    used_derived: bool
    warning: Optional[str] = None


@dataclass(frozen=True, slots=True)
class AssetValidationReport:
    """Summary returned by ``validate_assets()``."""

    valid: bool
    assets_root: Path
    checked_originals: int
    checked_derived: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def get_assets_root() -> Path:
    """Return the canonical ``<repo_root>/assets`` path independent of CWD."""
    return Path(__file__).resolve().parents[2] / "assets"


def read_png_dimensions(path: Path) -> tuple[int, int]:
    """Read (width, height) from a PNG IHDR chunk using only Python stdlib."""
    with path.open("rb") as fh:
        header = fh.read(24)
    if len(header) < 24 or header[:8] != _PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG header: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


class AssetRegistry:
    """Lightweight, CWD-independent asset path resolver and manifest validator."""

    def __init__(self, assets_root: Optional[Path] = None) -> None:
        self._root = Path(assets_root).resolve() if assets_root is not None else get_assets_root()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def manifest_path(self) -> Path:
        return self._root / "manifest.json"

    def resolve(self, asset_id: AssetId, *, prefer_derived: bool = True) -> AssetResolution:
        """Resolve an asset path gracefully, optionally preferring cleaned derivatives."""
        if not isinstance(asset_id, AssetId):
            raise TypeError(f"asset_id must be AssetId, got {type(asset_id).__name__}")

        if prefer_derived and asset_id in DERIVED_RELATIVE_PATHS:
            derived_path = self._root / DERIVED_RELATIVE_PATHS[asset_id]
            if derived_path.is_file():
                return AssetResolution(
                    asset_id=asset_id,
                    path=derived_path,
                    exists=True,
                    used_derived=True,
                )

        rel = ORIGINAL_RELATIVE_PATHS.get(asset_id)
        if rel is None:
            for ctype, aid in VIETNAMESE_CLUE_ICON_IDS.items():
                if aid is asset_id:
                    rel = VIETNAMESE_CLUE_ICON_PATHS[ctype]
                    break
        if rel is None:
            return AssetResolution(
                asset_id=asset_id,
                path=None,
                exists=False,
                used_derived=False,
                warning=f"No registered path for asset {asset_id.value}.",
            )

        original_path = self._root / rel
        if original_path.is_file():
            warning = None
            if prefer_derived and asset_id in DERIVED_RELATIVE_PATHS:
                warning = (
                    f"Derived cleaned asset missing for {asset_id.value}; "
                    f"falling back to original {original_path.name}."
                )
            return AssetResolution(
                asset_id=asset_id,
                path=original_path,
                exists=True,
                used_derived=False,
                warning=warning,
            )

        return AssetResolution(
            asset_id=asset_id,
            path=None,
            exists=False,
            used_derived=False,
            warning=f"Missing asset {asset_id.value} (expected {original_path}).",
        )

    def resolve_case_cover(self, grid_size: int) -> AssetResolution:
        """Resolve the decorative Level Selection cover for grid size 3, 4, or 5."""
        if grid_size not in CASE_COVER_BY_GRID_SIZE:
            raise ValueError(f"Unsupported grid_size {grid_size!r}; expected 3, 4, or 5")
        return self.resolve(CASE_COVER_BY_GRID_SIZE[grid_size], prefer_derived=False)

    def load_vi_clue_manifest(self) -> dict[str, dict]:
        """Read ``assets/clue_icons/manifest_vi.json`` keyed by canonical clue type."""
        manifest_path = self._root / "clue_icons" / "manifest_vi.json"
        if not manifest_path.is_file():
            return {}
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        mapping: dict[str, dict] = {}
        for entry in data.get("mapping", []):
            key = str(entry.get("key", "")).strip().upper()
            if key:
                mapping[key] = entry
        return mapping

    def resolve_clue_icon(
        self,
        clue_type: str,
        *,
        prefer_vietnamese: bool = True,
    ) -> Optional[AssetResolution]:
        """Resolve the clue icon for ``clue_type`` (prefers 8-icon Vietnamese RGBA set).

        Uses ``assets/clue_icons/manifest_vi.json`` mapping when available,
        falling back to ``VIETNAMESE_CLUE_ICON_PATHS`` and then legacy V1.2
        ``CLUE_ICON_BY_TYPE`` without ever inferring type from localized text.
        """
        key = clue_type.strip().upper()
        if prefer_vietnamese:
            manifest_map = self.load_vi_clue_manifest()
            entry = manifest_map.get(key)
            rel_vi: Optional[str] = None
            if entry is not None and entry.get("file"):
                rel_vi = f"clue_icons/{Path(str(entry['file'])).name}"
            elif key in VIETNAMESE_CLUE_ICON_PATHS:
                rel_vi = VIETNAMESE_CLUE_ICON_PATHS[key]

            if rel_vi is not None:
                vi_path = self._root / rel_vi
                aid = VIETNAMESE_CLUE_ICON_IDS.get(key, AssetId.A10_FACT)
                if vi_path.is_file():
                    return AssetResolution(
                        asset_id=aid,
                        path=vi_path,
                        exists=True,
                        used_derived=True,
                    )

        asset_id = CLUE_ICON_BY_TYPE.get(key)
        if asset_id is None:
            return None
        return self.resolve(asset_id, prefer_derived=False)

    def validate_vietnamese_clue_icons(self, *, verify_sha256: bool = True) -> tuple[bool, tuple[str, ...]]:
        """Validate all 8 Vietnamese RGBA clue icons against ``assets/manifest.json``."""
        errors: list[str] = []
        manifest = self.load_manifest()
        vi_section = manifest.get("vietnamese_clue_icons", {})
        icons = vi_section.get("icons", [])
        if len(icons) != 8:
            errors.append(f"Expected 8 Vietnamese clue icons in manifest, found {len(icons)}")
        seen: set[str] = set()
        for entry in icons:
            ctype = str(entry.get("clue_type", "")).upper()
            rel = str(entry.get("relative_path", ""))
            seen.add(ctype)
            full = self._root / rel
            if not full.is_file():
                errors.append(f"Missing Vietnamese clue icon: {rel}")
                continue
            try:
                w, h = read_png_dimensions(full)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            dims = entry.get("dimensions", {})
            if (w, h) != (dims.get("width"), dims.get("height")):
                errors.append(f"Dimension mismatch for {rel}: file={w}x{h}, manifest={dims}")
            if verify_sha256 and entry.get("sha256"):
                actual_sha = hashlib.sha256(full.read_bytes()).hexdigest()
                if actual_sha != entry["sha256"]:
                    errors.append(f"SHA-256 mismatch for {rel}")
        missing_keys = set(VIETNAMESE_CLUE_ICON_PATHS.keys()) - seen
        if missing_keys:
            errors.append(f"Missing clue types in vietnamese_clue_icons manifest: {sorted(missing_keys)}")
        return (len(errors) == 0, tuple(errors))

    def load_manifest(self) -> dict:
        """Load the canonical ``assets/manifest.json``."""
        with self.manifest_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def validate(self, *, verify_sha256: bool = True) -> AssetValidationReport:
        """Validate manifest integrity, file existence, PNG headers, and checksums."""
        errors: list[str] = []
        warnings: list[str] = []
        checked_originals = 0
        checked_derived = 0

        if not self.manifest_path.is_file():
            return AssetValidationReport(
                valid=False,
                assets_root=self._root,
                checked_originals=0,
                checked_derived=0,
                errors=(f"Missing manifest: {self.manifest_path}",),
                warnings=(),
            )

        manifest = self.load_manifest()
        manifest_assets = {entry["asset_id"]: entry for entry in manifest.get("assets", [])}

        for asset_id, rel in ORIGINAL_RELATIVE_PATHS.items():
            full = self._root / rel
            if not full.is_file():
                errors.append(f"Missing original PNG: {rel}")
                continue
            try:
                w, h = read_png_dimensions(full)
            except ValueError as exc:
                errors.append(str(exc))
                continue

            entry = manifest_assets.get(asset_id.value)
            if entry is None:
                errors.append(f"Asset {asset_id.value} missing from manifest.json")
            else:
                dims = entry.get("dimensions", {})
                if (w, h) != (dims.get("width"), dims.get("height")):
                    errors.append(
                        f"Dimension mismatch for {rel}: file={w}x{h}, "
                        f"manifest={dims.get('width')}x{dims.get('height')}"
                    )
                if verify_sha256 and entry.get("sha256"):
                    actual_sha = hashlib.sha256(full.read_bytes()).hexdigest()
                    if actual_sha != entry["sha256"]:
                        errors.append(f"SHA-256 mismatch for original {rel}")
                if entry.get("validation_status") == "NEEDS_FIX":
                    warnings.append(
                        f"{asset_id.value} original flagged NEEDS_FIX (use derived cleaned PNG)."
                    )
            checked_originals += 1

        for entry in manifest.get("derived_assets", []):
            rel = entry["relative_path"]
            full = self._root / rel
            if not full.is_file():
                errors.append(f"Missing derived PNG: {rel}")
                continue
            try:
                w, h = read_png_dimensions(full)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            dims = entry.get("dimensions", {})
            if (w, h) != (dims.get("width"), dims.get("height")):
                errors.append(f"Dimension mismatch for derived {rel}")
            if verify_sha256 and entry.get("sha256"):
                actual_sha = hashlib.sha256(full.read_bytes()).hexdigest()
                if actual_sha != entry["sha256"]:
                    errors.append(f"SHA-256 mismatch for derived {rel}")
            checked_derived += 1

        return AssetValidationReport(
            valid=len(errors) == 0,
            assets_root=self._root,
            checked_originals=checked_originals,
            checked_derived=checked_derived,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )


DEFAULT_REGISTRY = AssetRegistry()


def resolve_asset(asset_id: AssetId, *, prefer_derived: bool = True) -> AssetResolution:
    """Module-level convenience wrapper around ``DEFAULT_REGISTRY.resolve``."""
    return DEFAULT_REGISTRY.resolve(asset_id, prefer_derived=prefer_derived)
