"""Visual ClueHighlighter helper for GameBoard (Phase 3–5).

Strict responsibility boundary (``docs/STAGE2_SHARED_BASELINE.md`` §5 & §9.4):
    - ONLY applies/clears luminous cyan highlight visuals on ``CharacterCard``
      items matching the cell IDs supplied by Hiệp's Controller.
    - NEVER parses ``Clue.parameters``, NEVER resolves ROW/COLUMN/NEIGHBORS
      regions, and NEVER touches ``GameEngine`` or SAT solvers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional

from PySide6.QtCore import QObject

from src.gui.animations.evidence_glow import EvidenceGlowController
from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.components.character_card import CharacterCard

Coord = tuple[int, int]


class HighlightRole(str, Enum):
    """Cell highlight role classification (preserved for GĐ2 compatibility)."""

    SOURCE = "SOURCE"
    TARGET = "TARGET"
    REGION_A = "REGION_A"
    REGION_B = "REGION_B"
    CONTRADICTION = "CONTRADICTION"
    HINT = "HINT"


@dataclass
class CellHighlight:
    coord: Coord
    role: HighlightRole


@dataclass
class HighlightState:
    mode: str = "NONE"
    active_clue_id: Optional[str] = None
    cell_highlights: dict[Coord, CellHighlight] = field(default_factory=dict)
    related_clue_ids: list[str] = field(default_factory=list)


class ClueHighlighter:
    """Visual highlight coordinator delegating luminous glow & pulse to ``EvidenceGlowController``."""

    def __init__(
        self,
        clues: Optional[Iterable[Any]] = None,
        *,
        glow_controller: Optional[EvidenceGlowController] = None,
        config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QObject] = None,
    ) -> None:
        self._glow = glow_controller or EvidenceGlowController(config=config, parent=parent)
        self._clues: list[Any] = list(clues or [])
        self._state = HighlightState()
        self._saturated: set[str] = set()

    @property
    def state(self) -> HighlightState:
        return self._state

    @property
    def active_cell_ids(self) -> tuple[str, ...]:
        return self._glow.active_cell_ids

    @property
    def glow_controller(self) -> EvidenceGlowController:
        return self._glow

    @property
    def reduced_motion(self) -> bool:
        return self._glow.reduced_motion

    def set_reduced_motion(self, enabled: bool) -> None:
        self._glow.set_reduced_motion(enabled)

    def apply_highlight(
        self,
        cards_by_id: Mapping[str, CharacterCard],
        cell_ids: Iterable[str],
    ) -> tuple[str, ...]:
        """Highlight only valid ``cell_ids`` present in ``cards_by_id``."""
        return self._glow.apply_highlight(cards_by_id, cell_ids)

    def clear_highlight(self, cards_by_id: Mapping[str, CharacterCard]) -> None:
        """Clear all highlight overlays across the board (smooth fade or instant)."""
        self._glow.clear_highlight(cards_by_id)

    def stop_all_immediately(self) -> None:
        """Immediately halt all glow animations (board rebuild / window teardown)."""
        self._glow.stop_all_immediately()

    # ------------------------------------------------------------------
    # Legacy GĐ2 Coordinate / Role Helpers (Pure Presentation Data)
    # ------------------------------------------------------------------

    def set_clues(self, clues: Iterable[Any]) -> None:
        self._clues = list(clues)

    def clear(self) -> HighlightState:
        self._state = HighlightState()
        return self._state

    def select_clue(self, clue_id: str, *, toggle: bool = True) -> HighlightState:
        if toggle and self._state.mode == "CLUE" and self._state.active_clue_id == clue_id:
            return self.clear()
        clue = next((c for c in self._clues if getattr(c, "id", getattr(c, "clue_id", None)) == clue_id), None)
        if clue is None:
            return self.clear()
        highlights: dict[Coord, CellHighlight] = {}
        for rc in getattr(clue, "target_cells", ()) or ():
            highlights[tuple(rc)] = CellHighlight(tuple(rc), HighlightRole.TARGET)
        for rc in getattr(clue, "region_a", ()) or ():
            highlights[tuple(rc)] = CellHighlight(tuple(rc), HighlightRole.REGION_A)
        for rc in getattr(clue, "region_b", ()) or ():
            highlights[tuple(rc)] = CellHighlight(tuple(rc), HighlightRole.REGION_B)
        src = getattr(clue, "source_cell", None)
        if src is not None:
            highlights[tuple(src)] = CellHighlight(tuple(src), HighlightRole.SOURCE)
        self._state = HighlightState(
            mode="CLUE",
            active_clue_id=clue_id,
            cell_highlights=highlights,
            related_clue_ids=[clue_id],
        )
        return self._state

    def inspect_cell(self, row: int, col: int) -> HighlightState:
        coord = (row, col)
        related: list[str] = []
        for c in self._clues:
            cid = getattr(c, "id", getattr(c, "clue_id", ""))
            cells = set(getattr(c, "target_cells", ()) or ()) | set(getattr(c, "region_a", ()) or ()) | set(getattr(c, "region_b", ()) or ())
            src = getattr(c, "source_cell", None)
            if src is not None:
                cells.add(tuple(src))
            if coord in cells:
                related.append(cid)
        self._state = HighlightState(
            mode="CELL_INSPECT",
            cell_highlights={coord: CellHighlight(coord, HighlightRole.TARGET)},
            related_clue_ids=related,
        )
        return self._state

    def update_saturated_clues(self, revealed_coords: Iterable[Coord]) -> set[str]:
        rev = {tuple(rc) for rc in revealed_coords}
        sat: set[str] = set()
        for c in self._clues:
            cid = getattr(c, "id", getattr(c, "clue_id", ""))
            targets = set(getattr(c, "target_cells", ()) or ()) | set(getattr(c, "region_a", ()) or ()) | set(getattr(c, "region_b", ()) or ())
            if targets and targets.issubset(rev):
                sat.add(cid)
        self._saturated = sat
        return set(sat)

    def highlight_contradiction(self, coord: Coord, culprit_ids: Iterable[str]) -> HighlightState:
        rc = tuple(coord)
        self._state = HighlightState(
            mode="CONTRADICTION",
            cell_highlights={rc: CellHighlight(rc, HighlightRole.CONTRADICTION)},
            related_clue_ids=list(culprit_ids),
        )
        return self._state

    def highlight_hint(self, coord: Coord, supporting_ids: Iterable[str]) -> HighlightState:
        rc = tuple(coord)
        self._state = HighlightState(
            mode="HINT",
            cell_highlights={rc: CellHighlight(rc, HighlightRole.HINT)},
            related_clue_ids=list(supporting_ids),
        )
        return self._state
