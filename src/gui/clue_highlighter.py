"""Visual ClueHighlighter helper for GameBoard (Phase 3–5).

Strict responsibility boundary (``docs/STAGE2_SHARED_BASELINE.md`` §5 & §9.4):
    - ONLY applies/clears luminous cyan highlight visuals on ``CharacterCard``
      items matching the cell IDs supplied by Hiệp's Controller.
    - NEVER parses ``Clue.parameters``, NEVER resolves ROW/COLUMN/NEIGHBORS
      regions, and NEVER touches ``GameEngine`` or SAT solvers.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from PySide6.QtCore import QObject

from src.gui.animations.evidence_glow import EvidenceGlowController
from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.components.character_card import CharacterCard


class ClueHighlighter:
    """Visual highlight coordinator delegating luminous glow & pulse to ``EvidenceGlowController``."""

    def __init__(
        self,
        *,
        glow_controller: Optional[EvidenceGlowController] = None,
        config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QObject] = None,
    ) -> None:
        self._glow = glow_controller or EvidenceGlowController(config=config, parent=parent)

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
