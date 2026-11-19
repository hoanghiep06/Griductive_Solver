"""Phase 5 motion API with lazy imports for components using motion tokens.

``CharacterCard`` reads timing values from ``motion_config``. Importing the
package must therefore not eagerly import ``card_flip``, which itself depends
on ``CharacterCard``. The heavier animation classes remain available through
the same public names and are resolved only when requested.
"""

from src.gui.animations.motion_config import (
    CARD_FLIP_DURATION,
    CARD_LIFT_DISTANCE,
    DEFAULT_MOTION,
    GLOW_FADE_DURATION,
    GLOW_LIGHT_UP_DURATION,
    GLOW_PULSE_DURATION,
    HOVER_DURATION,
    NOTIFICATION_ENTER_DURATION,
    NOTIFICATION_EXIT_DURATION,
    REDUCED_MOTION,
    SELECTION_DURATION,
    MotionConfig,
)


def __getattr__(name: str):
    if name in {
        "CardFlipAnimation",
        "FlipFrameState",
        "build_perspective_y_transform",
        "compute_flip_frame",
    }:
        from src.gui.animations import card_flip

        return getattr(card_flip, name)
    if name == "EvidenceGlowController":
        from src.gui.animations.evidence_glow import EvidenceGlowController

        return EvidenceGlowController
    if name in {"AnimationLifecycleState", "MotionCoordinator"}:
        from src.gui.animations import motion_coordinator

        return getattr(motion_coordinator, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AnimationLifecycleState",
    "CARD_FLIP_DURATION",
    "CARD_LIFT_DISTANCE",
    "CardFlipAnimation",
    "DEFAULT_MOTION",
    "EvidenceGlowController",
    "FlipFrameState",
    "GLOW_FADE_DURATION",
    "GLOW_LIGHT_UP_DURATION",
    "GLOW_PULSE_DURATION",
    "HOVER_DURATION",
    "MotionConfig",
    "MotionCoordinator",
    "NOTIFICATION_ENTER_DURATION",
    "NOTIFICATION_EXIT_DURATION",
    "REDUCED_MOTION",
    "SELECTION_DURATION",
    "build_perspective_y_transform",
    "compute_flip_frame",
]
