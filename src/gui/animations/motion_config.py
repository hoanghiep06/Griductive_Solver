"""Centralized Motion Design System configuration for GRIDUCTIVE (Phase 5).

Single source of truth for all animation durations, physical perspective
constants, easing parameters, and reduced-motion preferences so no timing
values are scattered across widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _mode_key(mode: Any) -> str:
    val = getattr(mode, "value", mode)
    return str(val).strip().upper()


@dataclass(frozen=True, slots=True)
class MotionConfig:
    """Immutable timing & physical feel parameters (milliseconds / logical px)."""

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

    # 5.3 Hover & Selection Feedback
    hover_duration: int = 150
    hover_lift_expanded: float = 3.5
    hover_lift_standard: float = 3.0
    hover_lift_compact: float = 2.0
    selection_duration: int = 210

    # 5.4 Professional Notification Motion
    notification_enter_duration: int = 210
    notification_exit_duration: int = 170
    notification_auto_dismiss_ms: int = 4500

    # Accessibility
    reduced_motion: bool = False

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
