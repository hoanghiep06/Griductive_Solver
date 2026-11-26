"""MotionCoordinator — Presentation-only animation lifecycle manager (Phase 5.5).

Manages visual animation lifecycles for ``GameBoard`` without containing ANY
game logic, SAT calls, or Controller orchestration:
    - Single active card reveal flip with reentrancy guard
    - Explicit lifecycle states: IDLE, PREPARING, ANIMATING, COMPLETING, CANCELLED
    - Strict separation between successful completion (``animation_finished``)
      and cancellation (``animation_cancelled`` — NEVER emits ``animation_finished``)
    - Generation tokening to drop stale callbacks after Restart / Load / close
    - Reduced-motion mode delivering queued completion so Controller never deadlocks
"""

from __future__ import annotations

from enum import Enum
import logging
from typing import Any, Iterable, Mapping, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from src.gui.animations.card_flip import CardFlipAnimation
from src.gui.animations.evidence_glow import EvidenceGlowController
from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.components.character_card import CharacterCard
from src.gui.view_models import CardVisibility, PublicCharacterView, normalize_character_view

logger = logging.getLogger(__name__)


class AnimationLifecycleState(str, Enum):
    """Visual animation coordinator lifecycle states (Phase 5 §9)."""

    IDLE = "IDLE"
    PREPARING = "PREPARING"
    ANIMATING = "ANIMATING"
    COMPLETING = "COMPLETING"
    CANCELLED = "CANCELLED"


class MotionCoordinator(QObject):
    """Coordinates card flips, evidence glow, and reduced-motion lifecycle."""

    animation_finished = Signal(str, object)   # (cell_id, token) — ONLY on completion
    animation_cancelled = Signal(str, object)  # (cell_id, token) — ONLY on cancel/abort
    state_changed = Signal(object)             # AnimationLifecycleState

    def __init__(
        self,
        *,
        config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._reduced_motion: bool = bool(config.reduced_motion)
        self._state: AnimationLifecycleState = AnimationLifecycleState.IDLE
        self._generation: int = 0
        self._active_flip: Optional[CardFlipAnimation] = None
        self._pending_reduced_completion: Optional[tuple[int, str, object]] = None
        self._glow_controller = EvidenceGlowController(config=config, parent=self)

    # ------------------------------------------------------------------
    # Read-Only Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> MotionConfig:
        return self._config

    @property
    def state(self) -> AnimationLifecycleState:
        return self._state

    @property
    def is_animating(self) -> bool:
        return (
            self._state in (AnimationLifecycleState.PREPARING, AnimationLifecycleState.ANIMATING)
            or self._active_flip is not None
            or self._pending_reduced_completion is not None
        )

    @property
    def active_cell_id(self) -> Optional[str]:
        if self._active_flip is not None:
            return self._active_flip.cell_id
        if self._pending_reduced_completion is not None:
            return self._pending_reduced_completion[1]
        return None

    @property
    def active_flip(self) -> Optional[CardFlipAnimation]:
        return self._active_flip

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @property
    def animation_enabled(self) -> bool:
        return not self._reduced_motion

    @property
    def glow_controller(self) -> EvidenceGlowController:
        return self._glow_controller

    # ------------------------------------------------------------------
    # Motion Preference Control
    # ------------------------------------------------------------------

    def set_reduced_motion(self, enabled: bool) -> None:
        flag = bool(enabled)
        self._reduced_motion = flag
        self._glow_controller.set_reduced_motion(flag)

    def set_animation_enabled(self, enabled: bool) -> None:
        """Inverse alias of ``set_reduced_motion`` (Phase 5 §9 API)."""
        self.set_reduced_motion(not bool(enabled))

    # ------------------------------------------------------------------
    # Card Reveal Flip API (Authorized by Controller)
    # ------------------------------------------------------------------

    def animate_card_reveal(
        self,
        cards_by_id: Mapping[str, CharacterCard],
        cell_id: str,
        public_character: Any,
        token: object = None,
    ) -> bool:
        """Start a single physical 3D card flip for an authorized REVEALED character.

        Returns ``True`` if accepted and started (or scheduled in reduced-motion),
        ``False`` if rejected due to busy/reentrancy, unknown cell, mismatched ID,
        non-REVEALED data, or already-revealed card.
        """
        if self.is_animating:
            logger.warning(
                "Rejecting reveal animation for %r while animation for %r is active",
                cell_id,
                self.active_cell_id,
            )
            return False

        card = cards_by_id.get(cell_id)
        if card is None:
            logger.warning("Rejecting reveal animation for unknown cell_id %r", cell_id)
            return False

        norm = normalize_character_view(public_character)
        if norm.cell_id != cell_id:
            raise ValueError(
                f"Reveal target mismatch: cell_id={cell_id!r} vs public_data.cell_id={norm.cell_id!r}"
            )
        if norm.visibility is not CardVisibility.REVEALED:
            raise ValueError(
                f"Refusing reveal animation for {cell_id!r}: public_data must be REVEALED"
            )

        # Case D: Already revealed — do not replay meaningless flip
        if card.is_revealed:
            logger.info("Ignoring redundant reveal animation for already-revealed card %r", cell_id)
            return False

        self._generation += 1
        gen = self._generation
        self._set_state(AnimationLifecycleState.PREPARING)

        # Case J: Reduced motion -> update immediately & emit queued completion
        if self._reduced_motion:
            card.set_public_data(norm)
            self._pending_reduced_completion = (gen, cell_id, token)
            self._set_state(AnimationLifecycleState.ANIMATING)
            QTimer.singleShot(0, self, lambda g=gen, cid=cell_id, tok=token: self._complete_reduced(g, cid, tok))
            return True

        flip = CardFlipAnimation(
            card,
            norm,
            token=token,
            config=self._config,
            parent=self,
        )
        self._active_flip = flip
        flip.completed.connect(lambda cid, tok, g=gen: self._on_flip_completed(g, cid, tok))
        flip.cancelled.connect(lambda cid, tok, g=gen: self._on_flip_cancelled(g, cid, tok))
        self._set_state(AnimationLifecycleState.ANIMATING)
        flip.start()
        return True

    def cancel_active_animation(self, *, revert_to_original: bool = True) -> bool:
        """Cancel any active card flip safely without emitting ``animation_finished``."""
        self._generation += 1
        cancelled_any = False

        if self._pending_reduced_completion is not None:
            _gen, cid, tok = self._pending_reduced_completion
            self._pending_reduced_completion = None
            cancelled_any = True
            self._set_state(AnimationLifecycleState.CANCELLED)
            self.animation_cancelled.emit(cid, tok)
            self._set_state(AnimationLifecycleState.IDLE)

        if self._active_flip is not None:
            flip = self._active_flip
            self._active_flip = None
            cancelled_any = True
            self._set_state(AnimationLifecycleState.CANCELLED)
            flip.cancel(revert_to_original=revert_to_original)
            flip.deleteLater()
            self._set_state(AnimationLifecycleState.IDLE)

        return cancelled_any

    def reset_visuals(self, cards_by_id: Optional[Mapping[str, CharacterCard]] = None) -> None:
        """Cancel active flips and stop all glow animations (e.g. Restart / Load / Close)."""
        self.cancel_active_animation(revert_to_original=False)
        self._glow_controller.stop_all_immediately()
        if cards_by_id:
            for card in cards_by_id.values():
                try:
                    card.reset_motion_visuals()
                except RuntimeError:
                    pass

    # ------------------------------------------------------------------
    # Highlight Delegation (Controller supplies cell_ids)
    # ------------------------------------------------------------------

    def highlight_cells(
        self,
        cards_by_id: Mapping[str, CharacterCard],
        cell_ids: Iterable[str],
    ) -> tuple[str, ...]:
        return self._glow_controller.apply_highlight(cards_by_id, cell_ids)

    def clear_highlights(self, cards_by_id: Mapping[str, CharacterCard]) -> None:
        self._glow_controller.clear_highlight(cards_by_id)

    # ------------------------------------------------------------------
    # Internal Lifecycle Handlers
    # ------------------------------------------------------------------

    def _set_state(self, new_state: AnimationLifecycleState) -> None:
        if self._state != new_state:
            self._state = new_state
            self.state_changed.emit(new_state)

    def _on_flip_completed(self, gen: int, cell_id: str, token: object) -> None:
        if gen != self._generation:
            return
        flip = self._active_flip
        self._active_flip = None
        if flip is not None:
            flip.deleteLater()
        self._set_state(AnimationLifecycleState.COMPLETING)
        self._set_state(AnimationLifecycleState.IDLE)
        self.animation_finished.emit(cell_id, token)

    def _on_flip_cancelled(self, gen: int, cell_id: str, token: object) -> None:
        # Cancellation signal already routed from cancel_active_animation or external stop
        if self._active_flip is not None and gen == self._generation:
            self._active_flip.deleteLater()
            self._active_flip = None
            self._set_state(AnimationLifecycleState.CANCELLED)
            self._set_state(AnimationLifecycleState.IDLE)
        self.animation_cancelled.emit(cell_id, token)

    def _complete_reduced(self, gen: int, cell_id: str, token: object) -> None:
        if gen != self._generation or self._pending_reduced_completion is None:
            return
        self._pending_reduced_completion = None
        self._set_state(AnimationLifecycleState.COMPLETING)
        self._set_state(AnimationLifecycleState.IDLE)
        self.animation_finished.emit(cell_id, token)
