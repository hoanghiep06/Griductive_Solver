"""PortraitRegistry — Manifest-driven 2D character portrait lookup & QPixmap cache.

Key responsibilities (Phase B, C, G, H):
1. Parses ``assets/characters/portrait_manifest.json`` ONCE (46 portrait PNGs,
   12 professions, 15 official puzzle IDs, 250 ``(puzzle_id, cell_id)`` slots).
2. Enforces strict ``(puzzle_id, cell_id)`` lookup:
   - NEVER guesses by ``character_name``, ``profession``, or ``cell_id`` alone.
   - NEVER maps ``MOCK_*`` demo puzzle IDs to official ``3x3_01..5x5_05`` IDs.
   - Verifies ``expected_name`` and ``expected_profession`` when supplied; if
     public metadata mismatches the manifest entry, logs a warning and returns
     ``None`` (triggering intentional fallback rather than showing the wrong
     person/profession).
3. Two-tier ``QPixmap`` cache:
   - Base cache keyed by resolved ``Path`` (at most 46 decoded pixmaps shared
     across all 250 slots).
   - Scaled cache keyed by ``(Path, width, height)`` so ``CharacterCard.paint()``
     and 3D ``CardFlipAnimation`` frames perform zero disk I/O or rescaling.
4. Strictly presentation-only: contains ZERO ``GameEngine``, ``hidden_solution``,
   SAT, DPLL, or verdict logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any, Mapping, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CHARACTERS_ROOT = _REPO_ROOT / "assets" / "characters"
_VALID_CELL_RE = re.compile(r"^[A-E][1-5]$")


def _is_safe_relative_path(rel_str: str) -> bool:
    if not isinstance(rel_str, str) or not rel_str.strip():
        return False
    p = Path(rel_str.strip())
    if p.is_absolute():
        return False
    if ".." in p.parts:
        return False
    return True


def _expected_grid_size_from_puzzle_id(puzzle_id: str) -> Optional[int]:
    if puzzle_id.startswith("3x3_"):
        return 3
    if puzzle_id.startswith("4x4_"):
        return 4
    if puzzle_id.startswith("5x5_"):
        return 5
    return None


def _is_cell_within_grid(cell_id: str, grid_size: int) -> bool:
    if not _VALID_CELL_RE.fullmatch(cell_id):
        return False
    col_idx = ord(cell_id[0]) - ord("A")
    row_idx = int(cell_id[1]) - 1
    return 0 <= col_idx < grid_size and 0 <= row_idx < grid_size


@dataclass(frozen=True, slots=True)
class PortraitAssetEntry:
    """One portrait file entry from ``manifest['assets']``."""

    filename: str
    profession: str
    variant: int
    width: int
    height: int
    format: str
    alpha: bool


@dataclass(frozen=True, slots=True)
class PortraitMappingEntry:
    """One ``(puzzle_id, cell_id)`` slot mapping from ``manifest['mapping']``."""

    portrait_slot_id: str
    puzzle_id: str
    cell_id: str
    character_name: str
    profession: str
    archetype: str
    source_candidate_file: str
    name_profession_candidate: str
    portrait_file: str
    portrait_path: str


@dataclass(frozen=True, slots=True)
class PortraitValidationReport:
    """Comprehensive validation report for the portrait manifest & asset library."""

    is_valid: bool
    schema_version: str
    portrait_count: int
    puzzle_count: int
    slot_count: int
    profession_count: int
    puzzles_by_size: dict[int, tuple[str, ...]]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class PortraitRegistry:
    """Centralized manifest loader, ``(puzzle_id, cell_id)`` resolver, and QPixmap cache."""

    def __init__(
        self,
        *,
        characters_root: Optional[Path] = None,
        prefer_cleaned: bool = True,
        auto_load: bool = True,
    ) -> None:
        self._root: Path = Path(characters_root) if characters_root is not None else _DEFAULT_CHARACTERS_ROOT
        self._prefer_cleaned: bool = bool(prefer_cleaned)
        self._manifest_path: Path = self._root / "portrait_manifest.json"

        self._raw_metadata: dict[str, Any] = {}
        self._assets_by_filename: dict[str, PortraitAssetEntry] = {}
        self._mapping_by_key: dict[tuple[str, str], PortraitMappingEntry] = {}
        self._warnings: list[str] = []
        self._last_report: Optional[PortraitValidationReport] = None

        # Two-level QPixmap cache: base 512x512 by Path, scaled by (Path, w, h)
        self._base_pixmap_cache: dict[Path, QPixmap] = {}
        self._scaled_pixmap_cache: dict[tuple[Path, int, int], QPixmap] = {}

        if auto_load and self._manifest_path.is_file():
            self.load_manifest(self._manifest_path)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def manifest_path(self) -> Path:
        return self._manifest_path

    @property
    def prefer_cleaned(self) -> bool:
        return self._prefer_cleaned

    @property
    def assets(self) -> Mapping[str, PortraitAssetEntry]:
        return dict(self._assets_by_filename)

    @property
    def mappings(self) -> Mapping[tuple[str, str], PortraitMappingEntry]:
        return dict(self._mapping_by_key)

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    @property
    def last_report(self) -> Optional[PortraitValidationReport]:
        return self._last_report

    @property
    def cached_base_count(self) -> int:
        return len(self._base_pixmap_cache)

    @property
    def cached_scaled_count(self) -> int:
        return len(self._scaled_pixmap_cache)

    # ------------------------------------------------------------------
    # Manifest Loading & Comprehensive Validation (Phase B1-B5)
    # ------------------------------------------------------------------

    def load_manifest(
        self,
        manifest_path: Optional[Path] = None,
    ) -> PortraitValidationReport:
        """Load and validate ``portrait_manifest.json``, populating internal lookup tables."""
        path = Path(manifest_path) if manifest_path is not None else self._manifest_path
        self._manifest_path = path
        self.clear_cache_if_needed()
        self._assets_by_filename.clear()
        self._mapping_by_key.clear()

        errors: list[str] = []
        warnings: list[str] = []

        if not path.is_file():
            msg = f"Portrait manifest not found: {path}"
            errors.append(msg)
            self._warnings.append(msg)
            report = PortraitValidationReport(
                is_valid=False,
                schema_version="",
                portrait_count=0,
                puzzle_count=0,
                slot_count=0,
                profession_count=0,
                puzzles_by_size={3: (), 4: (), 5: ()},
                errors=tuple(errors),
                warnings=tuple(warnings),
            )
            self._last_report = report
            return report

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            msg = f"Failed to parse portrait manifest {path}: {exc}"
            errors.append(msg)
            self._warnings.append(msg)
            report = PortraitValidationReport(
                is_valid=False,
                schema_version="",
                portrait_count=0,
                puzzle_count=0,
                slot_count=0,
                profession_count=0,
                puzzles_by_size={3: (), 4: (), 5: ()},
                errors=tuple(errors),
                warnings=tuple(warnings),
            )
            self._last_report = report
            return report

        if not isinstance(raw, dict):
            errors.append("Portrait manifest root must be a JSON object")
            raw = {}

        self._raw_metadata = {
            k: v for k, v in raw.items() if k not in ("assets", "mapping")
        }
        schema_version = str(raw.get("schema_version", ""))
        raw_assets = raw.get("assets")
        raw_mappings = raw.get("mapping")

        if not isinstance(raw_assets, list):
            errors.append("Manifest 'assets' field must be a list")
            raw_assets = []
        if not isinstance(raw_mappings, list):
            errors.append("Manifest 'mapping' field must be a list")
            raw_mappings = []

        # 1. Parse and validate assets list
        for idx, item in enumerate(raw_assets):
            if not isinstance(item, dict):
                errors.append(f"assets[{idx}] is not an object")
                continue
            fname = str(item.get("filename", "")).strip()
            prof = str(item.get("profession", "")).strip()
            if not _is_safe_relative_path(fname) or "/" in fname or "\\" in fname:
                errors.append(f"Unsafe or invalid asset filename at assets[{idx}]: {fname!r}")
                continue
            if not fname.lower().endswith(".png"):
                errors.append(f"Unsupported non-PNG asset filename at assets[{idx}]: {fname!r}")
                continue
            if fname in self._assets_by_filename:
                errors.append(f"Duplicate asset filename in manifest: {fname!r}")
                continue

            asset_file = self._root / "portraits" / fname
            if not asset_file.is_file():
                errors.append(f"Missing portrait PNG file on disk: {asset_file}")

            entry = PortraitAssetEntry(
                filename=fname,
                profession=prof,
                variant=int(item.get("variant", 0)),
                width=int(item.get("width", 512)),
                height=int(item.get("height", 512)),
                format=str(item.get("format", "PNG")),
                alpha=bool(item.get("alpha", True)),
            )
            self._assets_by_filename[fname] = entry

        # 2. Parse and validate 250 slot mappings
        per_puzzle_files: dict[str, set[str]] = {}
        puzzles_seen: set[str] = set()
        professions_seen: set[str] = set()

        for idx, m in enumerate(raw_mappings):
            if not isinstance(m, dict):
                errors.append(f"mapping[{idx}] is not an object")
                continue
            pid = str(m.get("puzzle_id", "")).strip()
            cid = str(m.get("cell_id", "")).strip()
            cname = str(m.get("character_name", "")).strip()
            prof = str(m.get("profession", "")).strip()
            arch = str(m.get("archetype", "")).strip()
            slot_id = str(m.get("portrait_slot_id", "")).strip()
            src_cand = str(m.get("source_candidate_file", "")).strip()
            pair_cand = str(m.get("name_profession_candidate", "")).strip()
            pfile = str(m.get("portrait_file", "")).strip()
            ppath = str(m.get("portrait_path", "")).strip()

            if not pid or not cid:
                errors.append(f"mapping[{idx}] missing puzzle_id or cell_id")
                continue
            if not cname or not prof:
                errors.append(f"mapping[{idx}] ({pid}/{cid}) missing character_name or profession")
                continue

            if not _is_safe_relative_path(pfile) or not _is_safe_relative_path(ppath):
                errors.append(f"Unsafe portrait path at {pid}/{cid}: file={pfile!r}, path={ppath!r}")
                continue
            if not pfile.lower().endswith(".png") or not ppath.lower().endswith(".png"):
                errors.append(f"Unsupported non-PNG portrait at {pid}/{cid}: {ppath!r}")
                continue
            if Path(ppath).name != pfile:
                errors.append(
                    f"Filename mismatch at {pid}/{cid}: portrait_file={pfile!r} vs portrait_path={ppath!r}"
                )
                continue

            gsize = _expected_grid_size_from_puzzle_id(pid)
            if gsize is None:
                errors.append(f"Unknown or unsupported puzzle_id format: {pid!r}")
                continue
            if not _is_cell_within_grid(cid, gsize):
                errors.append(
                    f"Out-of-bounds cell_id {cid!r} for {gsize}x{gsize} puzzle {pid!r}"
                )
                continue

            key = (pid, cid)
            if key in self._mapping_by_key:
                errors.append(f"Duplicate mapping key: ({pid!r}, {cid!r})")
                continue

            disk_path = self._root / ppath
            if not disk_path.is_file():
                errors.append(f"Mapped portrait file does not exist: {disk_path}")

            asset_meta = self._assets_by_filename.get(pfile)
            if asset_meta is not None and asset_meta.profession != prof:
                errors.append(
                    f"Profession mismatch between mapping {pid}/{cid} ({prof!r}) "
                    f"and asset {pfile!r} ({asset_meta.profession!r})"
                )

            used_in_puzzle = per_puzzle_files.setdefault(pid, set())
            if pfile in used_in_puzzle:
                errors.append(
                    f"Duplicate portrait file {pfile!r} reused within the same puzzle {pid!r}"
                )
            used_in_puzzle.add(pfile)

            puzzles_seen.add(pid)
            professions_seen.add(prof)

            self._mapping_by_key[key] = PortraitMappingEntry(
                portrait_slot_id=slot_id,
                puzzle_id=pid,
                cell_id=cid,
                character_name=cname,
                profession=prof,
                archetype=arch,
                source_candidate_file=src_cand,
                name_profession_candidate=pair_cand,
                portrait_file=pfile,
                portrait_path=ppath,
            )

        puzzles_by_size: dict[int, tuple[str, ...]] = {3: (), 4: (), 5: ()}
        for sz in (3, 4, 5):
            puzzles_by_size[sz] = tuple(
                sorted(p for p in puzzles_seen if _expected_grid_size_from_puzzle_id(p) == sz)
            )

        declared_portraits = int(raw.get("portrait_count", len(self._assets_by_filename)))
        declared_puzzles = int(raw.get("puzzle_count", len(puzzles_seen)))
        declared_slots = int(raw.get("slot_count", len(self._mapping_by_key)))

        if len(self._assets_by_filename) != declared_portraits:
            errors.append(
                f"Asset count {len(self._assets_by_filename)} != declared portrait_count {declared_portraits}"
            )
        if len(puzzles_seen) != declared_puzzles:
            errors.append(
                f"Puzzle count {len(puzzles_seen)} != declared puzzle_count {declared_puzzles}"
            )
        if len(self._mapping_by_key) != declared_slots:
            errors.append(
                f"Mapping count {len(self._mapping_by_key)} != declared slot_count {declared_slots}"
            )

        self._warnings.extend(errors)
        self._warnings.extend(warnings)

        report = PortraitValidationReport(
            is_valid=(len(errors) == 0),
            schema_version=schema_version,
            portrait_count=len(self._assets_by_filename),
            puzzle_count=len(puzzles_seen),
            slot_count=len(self._mapping_by_key),
            profession_count=len(professions_seen),
            puzzles_by_size=puzzles_by_size,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )
        self._last_report = report
        return report

    def validate_mapping(
        self,
        public_roster: Optional[Mapping[tuple[str, str], tuple[str, str]]] = None,
    ) -> PortraitValidationReport:
        """Validate current manifest and optionally cross-check against a public roster.

        ``public_roster`` maps ``(puzzle_id, cell_id) -> (character_name, profession)``.
        """
        base = self._last_report or self.load_manifest(self._manifest_path)
        errors = list(base.errors)
        warnings = list(base.warnings)

        if public_roster is not None:
            for key, (exp_name, exp_prof) in public_roster.items():
                entry = self._mapping_by_key.get(key)
                if entry is None:
                    errors.append(f"Missing portrait mapping for public roster slot {key!r}")
                    continue
                if entry.character_name != exp_name:
                    errors.append(
                        f"Character name mismatch at {key!r}: manifest={entry.character_name!r} "
                        f"vs public={exp_name!r}"
                    )
                if entry.profession != exp_prof:
                    errors.append(
                        f"Profession mismatch at {key!r}: manifest={entry.profession!r} "
                        f"vs public={exp_prof!r}"
                    )

        return PortraitValidationReport(
            is_valid=(len(errors) == 0),
            schema_version=base.schema_version,
            portrait_count=base.portrait_count,
            puzzle_count=base.puzzle_count,
            slot_count=base.slot_count,
            profession_count=base.profession_count,
            puzzles_by_size=base.puzzles_by_size,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # Lookup & QPixmap Caching (Phase B2-B5, G, H)
    # ------------------------------------------------------------------

    def get_mapping(self, puzzle_id: str, cell_id: str) -> Optional[PortraitMappingEntry]:
        """Lookup mapping strictly by ``(puzzle_id, cell_id)`` (never strips MOCK_)."""
        if not isinstance(puzzle_id, str) or not isinstance(cell_id, str):
            return None
        key = (puzzle_id.strip(), cell_id.strip().upper())
        return self._mapping_by_key.get(key)

    def list_puzzle_mappings(self, puzzle_id: str) -> tuple[PortraitMappingEntry, ...]:
        """Return all mappings for ``puzzle_id`` sorted by row-major cell order."""
        if not isinstance(puzzle_id, str):
            return ()
        pid = puzzle_id.strip()
        items = [e for (p, _), e in self._mapping_by_key.items() if p == pid]
        items.sort(key=lambda e: (int(e.cell_id[1]), e.cell_id[0]))
        return tuple(items)

    def _record_warning(self, message: str) -> None:
        self._warnings.append(message)
        logger.warning(message)

    def get_portrait_path(
        self,
        puzzle_id: str,
        cell_id: str,
        *,
        expected_name: Optional[str] = None,
        expected_profession: Optional[str] = None,
        prefer_cleaned: Optional[bool] = None,
    ) -> Optional[Path]:
        """Resolve verified portrait PNG path for ``(puzzle_id, cell_id)``.

        Returns ``None`` (and records a warning) when:
        - ``(puzzle_id, cell_id)`` has no mapping (e.g., ``MOCK_*`` or unknown ID),
        - ``expected_name`` or ``expected_profession`` mismatches the manifest, or
        - the PNG file does not exist on disk.
        """
        entry = self.get_mapping(puzzle_id, cell_id)
        if entry is None:
            if isinstance(puzzle_id, str) and not puzzle_id.upper().startswith("MOCK_"):
                self._record_warning(
                    f"No portrait mapping found for ({puzzle_id!r}, {cell_id!r})"
                )
            return None

        if expected_name is not None and expected_name.strip() != entry.character_name:
            self._record_warning(
                f"Portrait name mismatch at ({entry.puzzle_id}, {entry.cell_id}): "
                f"expected {expected_name!r}, manifest has {entry.character_name!r}"
            )
            return None

        if expected_profession is not None and expected_profession.strip() != entry.profession:
            self._record_warning(
                f"Portrait profession mismatch at ({entry.puzzle_id}, {entry.cell_id}): "
                f"expected {expected_profession!r}, manifest has {entry.profession!r}"
            )
            return None

        use_clean = self._prefer_cleaned if prefer_cleaned is None else bool(prefer_cleaned)
        if use_clean:
            clean_candidate = self._root / "portraits_clean" / entry.portrait_file
            if clean_candidate.is_file():
                return clean_candidate

        orig_candidate = self._root / entry.portrait_path
        if orig_candidate.is_file():
            return orig_candidate

        self._record_warning(f"Portrait file missing on disk: {orig_candidate}")
        return None

    def get_portrait(
        self,
        puzzle_id: str,
        cell_id: str,
        *,
        size: Optional[tuple[int, int]] = None,
        expected_name: Optional[str] = None,
        expected_profession: Optional[str] = None,
        prefer_cleaned: Optional[bool] = None,
    ) -> Optional[QPixmap]:
        """Return a cached ``QPixmap`` (optionally smooth-scaled to ``size``).

        Never decodes from disk more than once per unique portrait file.
        Returns ``None`` on missing mapping, metadata mismatch, or corrupt PNG.
        """
        path = self.get_portrait_path(
            puzzle_id,
            cell_id,
            expected_name=expected_name,
            expected_profession=expected_profession,
            prefer_cleaned=prefer_cleaned,
        )
        if path is None:
            return None

        resolved = path.resolve()
        base_pm = self._base_pixmap_cache.get(resolved)
        if base_pm is None:
            img = QImage(str(resolved))
            if img.isNull():
                self._warnings.append(f"Corrupt or unreadable portrait PNG: {resolved}")
                return None
            base_pm = QPixmap.fromImage(img)
            if base_pm.isNull():
                self._warnings.append(f"Failed to convert portrait QImage to QPixmap: {resolved}")
                return None
            self._base_pixmap_cache[resolved] = base_pm

        if size is None:
            return base_pm

        tw = max(16, int(size[0]))
        th = max(16, int(size[1]))
        cache_key = (resolved, tw, th)
        scaled_pm = self._scaled_pixmap_cache.get(cache_key)
        if scaled_pm is None:
            scaled_pm = base_pm.scaled(
                tw,
                th,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_pixmap_cache[cache_key] = scaled_pm
        return scaled_pm

    def clear_cache_if_needed(self) -> None:
        """Clear decoded and scaled ``QPixmap`` caches safely."""
        self._base_pixmap_cache.clear()
        self._scaled_pixmap_cache.clear()

    def clear_cache(self) -> None:
        """Alias of ``clear_cache_if_needed``."""
        self.clear_cache_if_needed()


_DEFAULT_PORTRAIT_REGISTRY: Optional[PortraitRegistry] = None


def default_portrait_registry() -> PortraitRegistry:
    """Return the shared application-wide ``PortraitRegistry`` instance."""
    global _DEFAULT_PORTRAIT_REGISTRY
    if _DEFAULT_PORTRAIT_REGISTRY is None:
        _DEFAULT_PORTRAIT_REGISTRY = PortraitRegistry()
    return _DEFAULT_PORTRAIT_REGISTRY
