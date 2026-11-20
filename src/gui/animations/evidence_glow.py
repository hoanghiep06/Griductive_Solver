"""Luminous Evidence Highlight animation controller (Phase 5.2).

Drives lightweight per-card ``glow_intensity`` and ``glow_pulse`` painter
properties on ``CharacterCard`` items supplied by Controller (NEVER parses
clue logic or resolves grid regions).

Timeline (default):
    - Light Up:  0 .. 180 ms (0.0 -> 1.0, OutCubic)
    - Pulse:     180 .. 650 ms (2 restrained cyan luminance waves -> steady hold 0.86)
    - Hold:      Steady at 0.86 until cleared or changed (NEVER infinite pulse)
    - Fade Out:  180 ms smooth decay -> 0.0
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional

from PySide6.QtCore import QAbstractAnimation, QObject, QVariantAnimation

from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.components.character_card import CharacterCard


class EvidenceGlowController(QObject):
    """Coordinates luminous cyan light-up, restrained pulse, hold & fade-out."""

    def __init__(
        self,
        *,
        config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._reduced_motion: bool = bool(config.reduced_motion)
        self._active_cards: dict[str, CharacterCard] = {}
        self._fading_cards: dict[str, CharacterCard] = {}
        self._active_ids: tuple[str, ...] = ()

        # Light-up + Pulse driver (single lightweight shared timer across highlighted subset)
        self._enter_anim = QVariantAnimation(self)
        self._enter_anim.setStartValue(0.0)
        self._enter_anim.setEndValue(1.0)
        self._enter_anim.setDuration(
            max(1, int(config.glow_light_up_duration + config.glow_pulse_duration))
        )
        self._enter_anim.valueChanged.connect(self._on_enter_tick)
        self._enter_anim.finished.connect(self._on_enter_finished)

        # Fade-out driver for cards leaving highlight set
        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setDuration(max(1, int(config.glow_fade_out_duration)))
        self._fade_anim.valueChanged.connect(self._on_fade_tick)
        self._fade_anim.finished.connect(self._on_fade_finished)

    @property
    def active_cell_ids(self) -> tuple[str, ...]:
        return self._active_ids

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            self._snap_to_steady()

    def apply_highlight(
        self,
        cards_by_id: Mapping[str, CharacterCard],
        cell_ids: Iterable[str],
    ) -> tuple[str, ...]:
        """Highlight only valid ``cell_ids`` present in ``cards_by_id``."""
        requested = {cid for cid in cell_ids if cid in cards_by_id}

        # Stop in-flight animations cleanly before updating membership
        if self._enter_anim.state() == QAbstractAnimation.State.Running:
            self._enter_anim.stop()
        if self._fade_anim.state() == QAbstractAnimation.State.Running:
            self._fade_anim.stop()
            self._finalize_fading_cards()

        # Cards leaving highlight set fade out smoothly (or clear immediately in reduced motion)
        leaving: dict[str, CharacterCard] = {}
        for cid, card in list(self._active_cards.items()):
            if cid not in requested:
                leaving[cid] = card
        for cid, card in cards_by_id.items():
            if cid not in requested and card.is_highlighted and cid not in leaving:
                leaving[cid] = card

        # Cards entering or remaining in highlight set
        next_active: dict[str, CharacterCard] = {}
        ordered_ids: list[str] = []
        for cid, card in cards_by_id.items():
            if cid in requested:
                next_active[cid] = card
                ordered_ids.append(cid)

        self._active_cards = next_active
        self._active_ids = tuple(ordered_ids)

        if self._reduced_motion:
            for card in leaving.values():
                self._safe_clear_card_glow(card)
            for card in self._active_cards.values():
                self._safe_set_card_glow(card, highlighted=True, intensity=self._config.glow_hold_intensity, pulse=0.0)
            return self._active_ids

        # Smooth fade out for leaving cards (immediately clear semantic flag while fading glow)
        if leaving:
            for card in leaving.values():
                try:
                    card.set_highlighted(False)
                except RuntimeError:
                    pass
            self._fading_cards = leaving
            self._fade_anim.start()

        # Light-up + 2-wave pulse -> steady hold for active cards
        if self._active_cards:
            for card in self._active_cards.values():
                self._safe_set_card_glow(card, highlighted=True, intensity=0.15, pulse=0.0)
            self._enter_anim.start()

        return self._active_ids

    def clear_highlight(self, cards_by_id: Mapping[str, CharacterCard]) -> None:
        """Fade out (or immediately clear in reduced-motion) all highlights."""
        if self._enter_anim.state() == QAbstractAnimation.State.Running:
            self._enter_anim.stop()
        if self._fade_anim.state() == QAbstractAnimation.State.Running:
            self._fade_anim.stop()
            self._finalize_fading_cards()

        to_clear: dict[str, CharacterCard] = dict(self._active_cards)
        for cid, card in cards_by_id.items():
            if card.is_highlighted or card.glow_intensity > 0.0:
                to_clear[cid] = card

        self._active_cards.clear()
        self._active_ids = ()

        if not to_clear:
            return

        if self._reduced_motion:
            for card in to_clear.values():
                self._safe_clear_card_glow(card)
            return

        # Immediately clear semantic is_highlighted flag while glow_intensity fades smoothly to 0
        for card in to_clear.values():
            try:
                card.set_highlighted(False)
            except RuntimeError:
                pass
        self._fading_cards = to_clear
        self._fade_anim.start()

    def stop_all_immediately(self) -> None:
        """Hard-stop all glow animations immediately (used on board rebuild/close)."""
        if self._enter_anim.state() != QAbstractAnimation.State.Stopped:
            self._enter_anim.stop()
        if self._fade_anim.state() != QAbstractAnimation.State.Stopped:
            self._fade_anim.stop()
        for card in list(self._active_cards.values()) + list(self._fading_cards.values()):
            self._safe_clear_card_glow(card)
        self._active_cards.clear()
        self._fading_cards.clear()
        self._active_ids = ()

    # ------------------------------------------------------------------
    # Internal Animation Callbacks
    # ------------------------------------------------------------------

    def _snap_to_steady(self) -> None:
        if self._enter_anim.state() != QAbstractAnimation.State.Stopped:
            self._enter_anim.stop()
        if self._fade_anim.state() != QAbstractAnimation.State.Stopped:
            self._fade_anim.stop()
        self._finalize_fading_cards()
        for card in self._active_cards.values():
            self._safe_set_card_glow(
                card,
                highlighted=True,
                intensity=self._config.glow_hold_intensity,
                pulse=0.0,
            )

    def _on_enter_tick(self, value: object) -> None:
        u = max(0.0, min(1.0, float(value)))
        total_ms = max(1, self._config.glow_light_up_duration + self._config.glow_pulse_duration)
        light_ratio = self._config.glow_light_up_duration / float(total_ms)
        hold = self._config.glow_hold_intensity

        if u <= light_ratio:
            # 0..180ms smooth ease-out light up (0 -> 1.0)
            p = u / max(1e-6, light_ratio)
            eased = 1.0 - ((1.0 - p) ** 3)
            intensity = eased
            pulse = 0.35 * eased
        else:
            # 180..650ms restrained 2-beat damped luminance pulse -> settles smoothly to hold
            p = (u - light_ratio) / max(1e-6, 1.0 - light_ratio)
            damping = 1.0 - p
            wave = 0.5 * (1.0 + math.sin(2.0 * math.pi * 1.5 * p - math.pi / 2.0))
            pulse = damping * wave
            intensity = hold + (1.0 - hold) * damping * (0.4 + 0.6 * wave)

        for card in list(self._active_cards.values()):
            self._safe_set_card_glow(card, highlighted=True, intensity=intensity, pulse=pulse)

    def _on_enter_finished(self) -> None:
        for card in list(self._active_cards.values()):
            self._safe_set_card_glow(
                card,
                highlighted=True,
                intensity=self._config.glow_hold_intensity,
                pulse=0.0,
            )

    def _on_fade_tick(self, value: object) -> None:
        factor = max(0.0, min(1.0, float(value)))
        intensity = self._config.glow_hold_intensity * (factor * factor)
        for card in list(self._fading_cards.values()):
            self._safe_set_card_glow(card, highlighted=False, intensity=intensity, pulse=0.0)

    def _on_fade_finished(self) -> None:
        self._finalize_fading_cards()

    def _finalize_fading_cards(self) -> None:
        for card in list(self._fading_cards.values()):
            self._safe_clear_card_glow(card)
        self._fading_cards.clear()

    @staticmethod
    def _safe_set_card_glow(
        card: CharacterCard,
        *,
        highlighted: bool,
        intensity: float,
        pulse: float,
    ) -> None:
        try:
            card.set_highlighted(highlighted)
            card.set_glow_state(intensity, pulse)
        except RuntimeError:
            pass

    @staticmethod
    def _safe_clear_card_glow(card: CharacterCard) -> None:
        try:
            card.set_highlighted(False)
            card.set_glow_state(0.0, 0.0)
        except RuntimeError:
            pass
