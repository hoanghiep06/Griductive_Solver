"""Phase 5 Cinematic Motion & Animation system for GRIDUCTIVE."""

from src.gui.animations.card_flip import (
    CardFlipAnimation,
    FlipFrameState,
    build_perspective_y_transform,
    compute_flip_frame,
)
from src.gui.animations.evidence_glow import EvidenceGlowController
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
from src.gui.animations.motion_coordinator import (
    AnimationLifecycleState,
    MotionCoordinator,
)

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
