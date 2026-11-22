"""Physical 3D perspective card-flip math & Qt animation driver (Phase 5.1).

Implements TRUE projective 3D Y-axis rotation via an explicit homogeneous
perspective ``QTransform`` (NOT fake 2D ``scaleX``), paired with physical
anticipation lift, dynamic offset shadow, metallic card-edge thickness near
90 deg, directional angle lighting, and non-mirrored front face switching.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from PySide6.QtCore import QAbstractAnimation, QObject, QPropertyAnimation, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QTransform

from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.animations.motion_tokens import SPRING_POP
from src.gui.components.character_card import CardDisplayMode, CharacterCard
from src.gui.view_models import PublicCharacterView


@dataclass(frozen=True, slots=True)
class FlipFrameState:
    """Instantaneous physical state of a card at normalized timeline ``t`` in [0, 1]."""

    t: float
    angle_deg: float          # 0.0 (back flat) .. 90.0 (edge-on) .. 180.0 (front flat)
    lift_factor: float        # 0.0 (on table) .. 1.0 (peak lifted)
    lift_y: float             # negative vertical offset (upward) in logical px
    lift_scale: float         # >= 1.0 subtle proximity scale during lift
    show_front: bool          # False for angle < 90, True for angle >= 90
    effective_angle_deg: float  # angle used to orient visible face WITHOUT mirroring
    edge_visibility: float    # 0.0..1.0 thickness visibility near 90 deg
    lighting_tilt: float      # -1.0..1.0 directional sheen/shading intensity
    shadow_offset_x: float
    shadow_offset_y: float
    shadow_scale_x: float
    shadow_alpha: float
    pitch_deg: float = 0.0    # subtle X-axis pitch arc during physical hand lift


def _smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _ease_in_out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    if x < 0.5:
        return 4.0 * x * x * x
    return 1.0 - ((-2.0 * x + 2.0) ** 3) / 2.0


def _ease_out_back_subtle(x: float) -> float:
    """Animate UI spring.pop damped settle for landing cleanly back onto the table."""
    x = max(0.0, min(1.0, x))
    return SPRING_POP.evaluate(x)


def compute_flip_frame(
    t: float,
    *,
    mode: CardDisplayMode = CardDisplayMode.STANDARD,
    config: MotionConfig = DEFAULT_MOTION,
) -> FlipFrameState:
    """Evaluate physical 4-stage card-flip kinematics at normalized time ``t``.

    Stages (default 620 ms):
        - 0.000 .. 0.145 (0..90 ms):   Anticipation / Lift off board surface.
        - 0.145 .. 0.500 (90..310 ms): Y-rotation 0° -> 90° (back face tilting).
        - 0.500 .. 0.839 (310..520 ms): Y-rotation 90° -> 180° (front face arriving).
        - 0.839 .. 1.000 (520..620 ms): Gentle physical settle back onto table.
    """
    t = max(0.0, min(1.0, float(t)))
    lift_end = config.flip_lift_end_ratio
    rot_end = config.flip_rotate_end_ratio
    max_lift = config.lift_distance_for(mode)
    max_scale = config.lift_scale_for(mode)

    # 1. Angle curve (0° -> 180° across [lift_end, rot_end])
    if t <= lift_end:
        angle_deg = 0.0
    elif t >= rot_end:
        angle_deg = 180.0
    else:
        u = (t - lift_end) / max(1e-6, rot_end - lift_end)
        # Smooth ease-in-out acceleration through the 90° midpoint
        angle_deg = 180.0 * _ease_in_out_cubic(u)

    # 2. Lift curve (rises during anticipation, stays elevated through flip, settles smoothly)
    if t <= lift_end:
        lift_factor = _smoothstep(t / max(1e-6, lift_end))
    elif t < rot_end:
        # Slight zenith arc right over the 90° midpoint for physical hand-flip feel
        u = (t - lift_end) / max(1e-6, rot_end - lift_end)
        lift_factor = 1.0 + 0.12 * math.sin(math.pi * u)
    else:
        u = (t - rot_end) / max(1e-6, 1.0 - rot_end)
        # Settle smoothly from 1.0 -> 0.0 with negligible micro-settle
        settle = _ease_out_back_subtle(u)
        lift_factor = max(0.0, 1.0 - settle)

    lift_y = -max_lift * lift_factor
    lift_scale = 1.0 + (max_scale - 1.0) * lift_factor

    # 3. Face switch strictly at 90° midpoint, using (angle - 180°) so front is NEVER mirrored
    show_front = angle_deg >= 90.0
    effective_angle_deg = (angle_deg - 180.0) if show_front else angle_deg

    # 4. Physical card thickness edge visibility & directional tilt lighting
    rad = math.radians(angle_deg)
    sin_a = math.sin(rad)
    cos_a = math.cos(rad)
    # Visible rim near midpoint (peaks at 90°)
    edge_visibility = max(0.0, sin_a) if abs(cos_a) < 0.35 else 0.0
    # Signed lighting shift across card width
    lighting_tilt = math.sin(math.radians(effective_angle_deg))

    # 5. Dynamic shadow beneath lifted & rotating card
    shadow_offset_x = 3.0 + 8.0 * lift_factor + 6.0 * sin_a
    shadow_offset_y = 5.0 + 12.0 * lift_factor
    shadow_scale_x = max(0.14, abs(cos_a)) * (1.0 + 0.04 * lift_factor)
    shadow_alpha = (0.28 + 0.24 * lift_factor) * (0.45 + 0.55 * abs(cos_a))
    pitch_deg = -7.5 * math.sin(math.pi * t) * lift_factor

    return FlipFrameState(
        t=t,
        angle_deg=angle_deg,
        lift_factor=lift_factor,
        lift_y=lift_y,
        lift_scale=lift_scale,
        show_front=show_front,
        effective_angle_deg=effective_angle_deg,
        edge_visibility=edge_visibility,
        lighting_tilt=lighting_tilt,
        shadow_offset_x=shadow_offset_x,
        shadow_offset_y=shadow_offset_y,
        shadow_scale_x=shadow_scale_x,
        shadow_alpha=shadow_alpha,
        pitch_deg=pitch_deg,
    )


def build_perspective_3d_transform(
    width: float,
    height: float,
    yaw_deg: float,
    pitch_deg: float = 0.0,
    *,
    lift_y: float = 0.0,
    lift_scale: float = 1.0,
    perspective_distance: float = DEFAULT_MOTION.card_perspective_distance,
) -> QTransform:
    """Build a TRUE 3D dual-axis projective ``QTransform`` (Yaw around Y + Pitch around X)."""
    cx = width * 0.5
    cy = height * 0.5
    rad_y = math.radians(yaw_deg)
    rad_x = math.radians(pitch_deg)
    cos_y = math.cos(rad_y)
    sin_y = math.sin(rad_y)
    cos_x = math.cos(rad_x)
    sin_x = math.sin(rad_x)

    if abs(cos_y) < 0.015:
        cos_y = 0.015 if cos_y >= 0.0 else -0.015
    if abs(cos_x) < 0.015:
        cos_x = 0.015 if cos_x >= 0.0 else -0.015

    d = max(120.0, perspective_distance)
    rot_3d = QTransform(
        cos_y,        sin_y * sin_x, (sin_y * cos_x) / d,
        0.0,          cos_x,         -sin_x / d,
        0.0,          0.0,           1.0,
    )

    tx = QTransform()
    tx.translate(cx, cy + lift_y)
    if lift_scale != 1.0:
        tx.scale(lift_scale, lift_scale)
    tx = rot_3d * tx
    pre = QTransform.fromTranslate(-cx, -cy)
    return pre * tx


def build_perspective_y_transform(
    width: float,
    height: float,
    effective_angle_deg: float,
    *,
    pitch_deg: float = 0.0,
    lift_y: float = 0.0,
    lift_scale: float = 1.0,
    perspective_distance: float = DEFAULT_MOTION.card_perspective_distance,
) -> QTransform:
    """Build a TRUE 3D projective ``QTransform`` rotating a card around its center Y-axis."""
    return build_perspective_3d_transform(
        width,
        height,
        effective_angle_deg,
        pitch_deg,
        lift_y=lift_y,
        lift_scale=lift_scale,
        perspective_distance=perspective_distance,
    )


class CardFlipAnimation(QObject):
    """Controllable single-card 3D flip animation driver with strict cancel vs complete."""

    completed = Signal(str, object)   # (cell_id, token) — ONLY on successful finish
    cancelled = Signal(str, object)   # (cell_id, token) — ONLY on explicit cancel/abort

    def __init__(
        self,
        card: CharacterCard,
        target_public_data: PublicCharacterView,
        *,
        token: object = None,
        config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._card = card
        self._cell_id = card.cell_id
        self._original_data = card.public_data
        self._target_data = target_public_data
        self._token = token
        self._config = config
        self._active = False
        self._cancelled = False
        self._finished = False

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(max(1, config.scaled_ms(config.card_flip_duration)))
        self._anim.valueChanged.connect(self._on_value_changed)
        self._anim.finished.connect(self._on_anim_finished)

    @property
    def cell_id(self) -> str:
        return self._cell_id

    @property
    def token(self) -> object:
        return self._token

    @property
    def is_running(self) -> bool:
        return self._active and self._anim.state() == QAbstractAnimation.State.Running

    def start(self) -> None:
        if self._active or self._finished or self._cancelled:
            return
        self._active = True
        self._card.begin_flip_animation(self._target_data)
        self._apply_t(0.0)
        self._anim.start()

    def seek_normalized(self, t: float) -> FlipFrameState:
        """Deterministic frame evaluation helper for visual QA screenshots & tests."""
        if not self._card.is_animating_flip:
            self._card.begin_flip_animation(self._target_data)
        return self._apply_t(t)

    def cancel(self, *, revert_to_original: bool = True) -> None:
        """Abort animation safely without ever emitting ``completed``."""
        if self._finished or self._cancelled:
            return
        self._cancelled = True
        self._active = False
        if self._anim.state() != QAbstractAnimation.State.Stopped:
            self._anim.stop()
        try:
            self._card.cancel_flip_animation(
                restore_data=self._original_data if revert_to_original else None
            )
        except RuntimeError:
            # Card C++ QGraphicsObject already deleted during window close
            pass
        self.cancelled.emit(self._cell_id, self._token)

    def _apply_t(self, t: float) -> FlipFrameState:
        frame = compute_flip_frame(t, mode=self._card.display_mode, config=self._config)
        self._card.set_flip_frame(frame)
        return frame

    def _on_value_changed(self, value: object) -> None:
        if not self._active or self._cancelled:
            return
        try:
            self._apply_t(float(value))
        except RuntimeError:
            self.cancel(revert_to_original=False)

    def _on_anim_finished(self) -> None:
        if self._cancelled or self._finished:
            return
        self._active = False
        self._finished = True
        try:
            self._card.finish_flip_animation(self._target_data)
        except RuntimeError:
            return
        self.completed.emit(self._cell_id, self._token)
