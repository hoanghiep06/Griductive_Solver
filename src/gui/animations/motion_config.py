"""Centralized Motion Design System configuration for GRIDUCTIVE (Phase 5).

Single source of truth for all animation durations, physical perspective
constants, easing parameters, and reduced-motion preferences so no timing
values are scattered across widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.gui.animations.motion_tokens import (
    SCALE_CHOICE,
    SCALE_PRESS,
    STAGGER_STACK_MS,
    STAGGER_WAVE_MS,
    clamp_tempo,
    scale_duration_ms,
)


def _mode_key(mode: Any) -> str:
    val = getattr(mode, "value", mode)
    return str(val).strip().upper()


@dataclass(frozen=True, slots=True)
class MotionConfig:
    """Immutable timing & physical feel parameters (milliseconds / logical px)."""

    # Global Animate UI pace & expressiveness
    tempo: float = 1.0
    motion_level: str = "EXPRESSIVE"

    # 5.1 Physical 3D Card Flip (target 550-700 ms)
    card_flip_duration: int = 620
    flip_lift_end_ratio: float = 0.145      # 0..90 ms anticipation lift
    flip_rotate_end_ratio: float = 0.839    # 90..520 ms full 0->180 deg Y-rotation
    # 520..620 ms settle back onto board surface
    card_perspective_distance: float = 680.0
    card_edge_thickness: float = 4.5
    card_lift_distance_expanded: float = 12.0
    card_lift_distance_standard: float = 10.0
    card_lift_distance_compact: float = 6.5
    card_lift_scale_expanded: float = 1.055
    card_lift_scale_standard: float = 1.050
    card_lift_scale_compact: float = 1.038

    # 5.2 Luminous Evidence Highlight (0-180ms light-up, 180-650ms pulse, hold, 180ms fade)
    glow_light_up_duration: int = 180
    glow_pulse_duration: int = 470
    glow_fade_out_duration: int = 180
    glow_hold_intensity: float = 0.86

    # 5.3 Hover, Press & Selection Feedback (Animate UI Rules A5, B4)
    hover_duration: int = 150
    hover_lift_expanded: float = 3.5
    hover_lift_standard: float = 3.0
    hover_lift_compact: float = 2.0
    selection_duration: int = 210
    press_duration: int = 150
    press_scale_button: float = SCALE_PRESS
    press_scale_card: float = SCALE_CHOICE
    reveal_burst_duration: int = 420

    # 5.4 Professional Notification Motion (ease.soft enter, ease.away dismiss)
    notification_enter_duration: int = 220
    notification_exit_duration: int = 180
    notification_auto_dismiss_ms: int = 4500

    # Guided-play interaction rhythm
    focus_dim_duration: int = 180
    focus_dim_opacity: float = 0.42
    contradiction_shake_duration: int = 380
    assisted_flip_duration: int = 380
    auto_step_interval: int = 1500   # nghỉ SAU khi lật xong để kịp đọc lập luận
    auto_step_min: int = 600
    auto_step_max: int = 3000
    dialog_enter_duration: int = 280
    dialog_exit_duration: int = 190
    hint_particle_duration: int = 620
    board_collapse_duration: int = 210
    board_rebuild_duration: int = 360
    list_item_enter_duration: int = 320
    progress_spring_duration: int = 320
    results_stamp_duration: int = 440
    results_particles_duration: int = 680
    results_count_duration: int = 680
    stagger_stack_ms: int = STAGGER_STACK_MS
    stagger_wave_ms: int = STAGGER_WAVE_MS

    # Accessibility
    reduced_motion: bool = False

    def scaled_ms(self, base_ms: int) -> int:
        """Apply global Animate UI tempo scaling to a base duration."""
        return scale_duration_ms(base_ms, self.tempo)

    def with_tempo(self, tempo: float) -> "MotionConfig":
        """Return a copy of this config paced by a new tempo in [0.5, 2.0]."""
        return MotionConfig(
            tempo=clamp_tempo(tempo),
            motion_level=self.motion_level,
            card_flip_duration=self.card_flip_duration,
            reduced_motion=self.reduced_motion,
        )

    def lift_distance_for(self, mode: Any) -> float:
        key = _mode_key(mode)
        if key == "EXPANDED":
            return self.card_lift_distance_expanded
        if key == "COMPACT":
            return self.card_lift_distance_compact
        return self.card_lift_distance_standard

    def lift_scale_for(self, mode: Any) -> float:
        key = _mode_key(mode)
        if key == "EXPANDED":
            return self.card_lift_scale_expanded
        if key == "COMPACT":
            return self.card_lift_scale_compact
        return self.card_lift_scale_standard

    def hover_lift_for(self, mode: Any) -> float:
        key = _mode_key(mode)
        if key == "EXPANDED":
            return self.hover_lift_expanded
        if key == "COMPACT":
            return self.hover_lift_compact
        return self.hover_lift_standard


DEFAULT_MOTION = MotionConfig()

# Convenient named constants matching Phase 5 §16 naming
CARD_FLIP_DURATION: int = DEFAULT_MOTION.card_flip_duration
CARD_LIFT_DISTANCE: float = DEFAULT_MOTION.card_lift_distance_standard
HOVER_DURATION: int = DEFAULT_MOTION.hover_duration
SELECTION_DURATION: int = DEFAULT_MOTION.selection_duration
GLOW_LIGHT_UP_DURATION: int = DEFAULT_MOTION.glow_light_up_duration
GLOW_PULSE_DURATION: int = DEFAULT_MOTION.glow_pulse_duration
GLOW_FADE_DURATION: int = DEFAULT_MOTION.glow_fade_out_duration
NOTIFICATION_ENTER_DURATION: int = DEFAULT_MOTION.notification_enter_duration
NOTIFICATION_EXIT_DURATION: int = DEFAULT_MOTION.notification_exit_duration
REDUCED_MOTION: bool = DEFAULT_MOTION.reduced_motion