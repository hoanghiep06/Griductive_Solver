"""Animate UI Motion Token System adapted for PySide6 / Qt6.

Translates the Animate UI motion language (springs, role-based cubic-bezier
curves, scales, shifts, staggers, and global tempo scaling) into deterministic,
presentation-only Qt6 primitives with zero domain dependencies.

References (Animate UI skill):
    - tokens.md: spring.*, transition.*, ease.*, scale.*, shift.*, stagger.*, tempo
    - rules.md:  A1 (reduced motion), B1 (springs first), B2 (curves by role),
                 B4 (press-only scale), B8 (one token set, one tempo)
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPointF


# ---------------------------------------------------------------------------
# Tempo Helpers (Animate UI tempo law: duration * tempo, k / tempo^2, d / tempo)
# ---------------------------------------------------------------------------

MIN_TEMPO: float = 0.5
MAX_TEMPO: float = 2.0


def clamp_tempo(tempo: float) -> float:
    """Clamp global motion tempo to Animate UI's safe [0.5, 2.0] envelope."""
    return max(MIN_TEMPO, min(MAX_TEMPO, float(tempo)))


def scale_duration_ms(base_ms: int, tempo: float = 1.0) -> int:
    """Scale a duration in milliseconds by global tempo (minimum 1 ms)."""
    return max(1, int(round(float(base_ms) * clamp_tempo(tempo))))


# ---------------------------------------------------------------------------
# Analytical Damped Harmonic Oscillator Springs (mass = 1.0)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpringSpec:
    """Animate UI stiffness/damping spring specification (mass = 1.0)."""

    stiffness: float
    damping: float
    duration_ms: int
    mass: float = 1.0

    def scaled(self, tempo: float) -> "SpringSpec":
        """Preserve exact spring overshoot shape on a new global time scale."""
        t = clamp_tempo(tempo)
        if abs(t - 1.0) < 1e-6:
            return self
        return SpringSpec(
            stiffness=self.stiffness / (t * t),
            damping=self.damping / t,
            duration_ms=scale_duration_ms(self.duration_ms, t),
            mass=self.mass,
        )

    def evaluate(self, progress: float) -> float:
        """Evaluate spring displacement in [0, 1] -> ~[0, 1] (may overshoot).

        Uses the closed-form solution of ``m * x'' + d * x' + k * (x - 1) = 0``
        with initial conditions ``x(0) = 0, x'(0) = 0`` over ``[0, duration_s]``,
        blending smoothly to exact ``1.0`` at ``progress >= 1.0``.
        """
        u = max(0.0, min(1.0, float(progress)))
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0

        t = u * (max(1, self.duration_ms) / 1000.0)
        m = max(1e-6, self.mass)
        k = max(1e-6, self.stiffness)
        c = max(0.0, self.damping)

        omega0 = math.sqrt(k / m)
        zeta = c / (2.0 * math.sqrt(k * m))

        if zeta < 1.0 - 1e-5:
            # Underdamped (natural overshoot & settle)
            wd = omega0 * math.sqrt(1.0 - zeta * zeta)
            decay = math.exp(-zeta * omega0 * t)
            val = 1.0 - decay * (
                math.cos(wd * t) + (zeta * omega0 / wd) * math.sin(wd * t)
            )
        elif zeta <= 1.0 + 1e-5:
            # Critically damped (fast settle, zero overshoot)
            decay = math.exp(-omega0 * t)
            val = 1.0 - decay * (1.0 + omega0 * t)
        else:
            # Overdamped (calm roll, zero overshoot)
            root = omega0 * math.sqrt(zeta * zeta - 1.0)
            r1 = -zeta * omega0 + root
            r2 = -zeta * omega0 - root
            val = 1.0 - (r2 * math.exp(r1 * t) - r1 * math.exp(r2 * t)) / (r2 - r1)

        # Smooth tail clamp in final 6% so property always lands at exact 1.0
        if u > 0.94:
            blend = (u - 0.94) / 0.06
            val = val + (1.0 - val) * (blend * blend)
        return val

    def to_easing_curve(self, tempo: float = 1.0) -> QEasingCurve:
        """Build a native C++ single-segment BezierSpline QEasingCurve matching this spring.

        Fits a single-segment cubic Bezier to the spring's analytical damping
        ratio and overshoot peak so Qt evaluates it natively in C++ with zero
        Python callback overhead or PySide6 multi-segment spline instability.
        """
        spec = self.scaled(tempo)
        m = max(1e-6, spec.mass)
        k = max(1e-6, spec.stiffness)
        c = max(0.0, spec.damping)
        zeta = c / (2.0 * math.sqrt(k * m))

        if zeta < 0.98:
            # Underdamped spring: analytical peak overshoot = exp(-pi*zeta / sqrt(1-zeta^2))
            overshoot = math.exp((-math.pi * zeta) / math.sqrt(max(1e-6, 1.0 - zeta * zeta)))
            # Fit single-segment Bezier control points to reproduce overshoot cleanly
            y1 = min(1.68, 1.0 + overshoot * 3.85)
            y2 = min(1.12, 1.0 + overshoot * 0.32)
            x1 = 0.24 if zeta > 0.72 else 0.30
            x2 = 0.48 if zeta > 0.72 else 0.56
        elif zeta <= 1.25:
            # Critically damped: crisp fast settle, zero overshoot
            x1, y1, x2, y2 = 0.22, 1.0, 0.36, 1.0
        else:
            # Overdamped (e.g. spring.number): smooth long roll, zero overshoot
            x1, y1, x2, y2 = 0.16, 1.0, 0.30, 1.0

        curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
        curve.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1.0, 1.0))
        return curve


# ---------------------------------------------------------------------------
# Role-Based Cubic-Bezier Curves (Animate UI rules.md § B2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CubicBezierSpec:
    """Normalized CSS cubic-bezier(x1, y1, x2, y2) curve specification."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_easing_curve(self) -> QEasingCurve:
        curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
        curve.addCubicBezierSegment(
            QPointF(self.x1, self.y1),
            QPointF(self.x2, self.y2),
            QPointF(1.0, 1.0),
        )
        return curve


# ---------------------------------------------------------------------------
# Canonical Animate UI Token Tables
# ---------------------------------------------------------------------------

# Springs (Animate UI tokens.md § Springs)
SPRING_PRESS = SpringSpec(stiffness=550.0, damping=30.0, duration_ms=220)
SPRING_POP = SpringSpec(stiffness=400.0, damping=29.0, duration_ms=420)
SPRING_DIALOG = SpringSpec(stiffness=150.0, damping=25.0, duration_ms=440)
SPRING_TOAST = SpringSpec(stiffness=280.0, damping=24.0, duration_ms=480)
SPRING_SELECTION = SpringSpec(stiffness=300.0, damping=30.0, duration_ms=340)
SPRING_HIGHLIGHT = SpringSpec(stiffness=500.0, damping=40.0, duration_ms=260)
SPRING_BOUNCE = SpringSpec(stiffness=200.0, damping=16.0, duration_ms=520)
SPRING_CHECK_POP = SpringSpec(stiffness=500.0, damping=24.0, duration_ms=440)
SPRING_ENTRANCE = SpringSpec(stiffness=200.0, damping=20.0, duration_ms=460)
SPRING_PROGRESS = SpringSpec(stiffness=300.0, damping=35.0, duration_ms=320)
SPRING_NUMBER = SpringSpec(stiffness=90.0, damping=50.0, duration_ms=680)

# Curves by motion role (Animate UI tokens.md § Curves)
EASE_OUT = CubicBezierSpec(0.23, 1.0, 0.32, 1.0)
EASE_SOFT = CubicBezierSpec(0.215, 0.61, 0.355, 1.0)
EASE_AWAY = CubicBezierSpec(0.33, 0.17, 0.67, 0.5)
EASE_IN_OUT = CubicBezierSpec(0.77, 0.0, 0.175, 1.0)
EASE_COLOR = CubicBezierSpec(0.25, 0.1, 0.25, 1.0)
EASE_DRAWER = CubicBezierSpec(0.34, 1.2, 0.64, 1.0)

# Scale tokens (Animate UI tokens.md § Scales & rules.md § B4)
SCALE_PRESS: float = 0.97      # Buttons, toggles (never on hover)
SCALE_CHOICE: float = 0.985    # Whole cards, tiles, rows when pressed
SCALE_POPOVER: float = 0.80
SCALE_MENU: float = 0.90
SCALE_DIALOG: float = 0.88
SCALE_TOAST: float = 0.96
SCALE_ENTRANCE: float = 0.84   # Board deal-in start scale (never from 0 — Rule A7)
SCALE_STAMP_START: float = 0.74  # Case Closed emblem checkPop entry (>= 0.7 — Rule A7)

# Shift & Stagger tokens (Animate UI tokens.md § Shifts & Staggers)
SHIFT_HANDOFF: float = 6.0
SHIFT_TABS: float = 12.0
SHIFT_STEP: float = 24.0
SHIFT_SHAKE: float = 4.0       # Damped contradiction shake peak px
STAGGER_STACK_MS: int = 30     # 0.03s cascade between items
STAGGER_WAVE_MS: int = 28      # Diagonal wave stagger when dealing cards

# Tween durations (ms, at tempo 1.0)
DURATION_SWAP_MS: int = 150
DURATION_FADE_MS: int = 200
DURATION_DISMISS_MS: int = 190
DURATION_MENU_MS: int = 220
DURATION_REVEAL_MS: int = 300
DURATION_OVERLAY_MS: int = 360
DURATION_SHAKE_MS: int = 380


def damped_shake_keyframes(peak_px: float = SHIFT_SHAKE) -> tuple[tuple[float, float], ...]:
    """Return Animate UI damped 3-swing shake keyframes (1.0 -> 0.66 -> 0.33 -> 0)."""
    p = float(peak_px)
    return (
        (0.00, 0.0),
        (0.14, -p),
        (0.30, p * 0.85),
        (0.46, -p * 0.66),
        (0.62, p * 0.48),
        (0.78, -p * 0.28),
        (0.90, p * 0.14),
        (1.00, 0.0),
    )


def build_easing(spec: SpringSpec | CubicBezierSpec, *, tempo: float = 1.0) -> QEasingCurve:
    """Create a fresh Qt6 QEasingCurve from any Animate UI spring or bezier token."""
    if isinstance(spec, SpringSpec):
        return spec.to_easing_curve(tempo=tempo)
    return spec.to_easing_curve()


def make_clamped_evaluator(fn: Callable[[float], float]) -> Callable[[float], float]:
    """Wrap an easing callable so normalized endpoints always return exact 0 and 1."""

    def _wrapped(progress: float) -> float:
        if progress <= 0.0:
            return 0.0
        if progress >= 1.0:
            return 1.0
        return fn(progress)

    return _wrapped
