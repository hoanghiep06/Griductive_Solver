"""StyledButton accessible desktop button primitive (Design System V2).

Supports clear multi-tier visual hierarchy across both Nocturne (dark) and
Warm Paper (editorial) surfaces:
    - Dark surfaces:  primary (Brass/Gold CTA), secondary (Editorial Ink-Outline),
                      ghost (Quiet minimal), tertiary (Subtle text/hairline),
                      danger (Crimson verdict), success (Innocent Teal verdict)
    - Paper surfaces: inkPrimary (Deep Ink CTA), paperSecondary (Ivory Ink-Outline),
                      paperGhost (Quiet archival link-button)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Property, QAbstractAnimation, QPropertyAnimation, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter, QWidget

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import SCALE_PRESS, SPRING_PRESS, build_easing
from src.gui.styles.tokens import GEOMETRY

VALID_BUTTON_VARIANTS = frozenset(
    {
        "primary",
        "secondary",
        "danger",
        "success",
        "ghost",
        "tertiary",
        "inkPrimary",
        "paperSecondary",
        "paperGhost",
    }
)

_VARIANT_CANONICAL: dict[str, str] = {v.lower(): v for v in VALID_BUTTON_VARIANTS}


class StyledButton(QPushButton):
    """Consistent, accessible themed QPushButton (>=44px tap target, pointer cursor)."""

    def __init__(
        self,
        text: str = "",
        *,
        variant: str = "secondary",
        min_height: int = GEOMETRY.button_min_height,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("widgetKind", "styledButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(min_height)
        self._variant = "secondary"
        self._press_level: float = 0.0
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)
        self._press_anim = QPropertyAnimation(self, b"press_level", self)
        self._press_anim.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.press_duration))
        self._press_anim.setEasingCurve(build_easing(SPRING_PRESS, tempo=DEFAULT_MOTION.tempo))
        self.set_variant(variant)

    def _get_press_level(self) -> float:
        return self._press_level

    def _set_press_level(self, value: float) -> None:
        clamped = max(0.0, min(1.2, float(value)))
        if clamped != self._press_level:
            self._press_level = clamped
            self.update()

    press_level = Property(float, _get_press_level, _set_press_level)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            if self._press_anim.state() != QAbstractAnimation.State.Stopped:
                self._press_anim.stop()
            self._press_level = 0.0
            self.update()

    def _animate_press(self, target: float) -> None:
        if self._press_anim.state() != QAbstractAnimation.State.Stopped:
            self._press_anim.stop()
        if self._reduced_motion:
            self._press_level = 0.0
            return
        self._press_anim.setKeyValues([])
        self._press_anim.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.press_duration))
        self._press_anim.setStartValue(self._press_level)
        self._press_anim.setEndValue(target)
        self._press_anim.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self._animate_press(1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press_level > 0.01 or self._press_anim.state() == QAbstractAnimation.State.Running:
            self._animate_press(0.0)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self._reduced_motion:
                if self._press_anim.state() != QAbstractAnimation.State.Stopped:
                    self._press_anim.stop()
                self._press_anim.setDuration(DEFAULT_MOTION.scaled_ms(180))
                self._press_anim.setKeyValues([(0.0, self._press_level), (0.38, 1.0), (1.0, 0.0)])
                self._press_anim.start()
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if self._press_level <= 0.005:
            super().paintEvent(event)
            return
        painter = QStylePainter(self)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        scale = 1.0 - (1.0 - SCALE_PRESS) * min(1.0, self._press_level)
        cx = self.width() * 0.5
        cy = self.height() * 0.5
        painter.translate(cx, cy)
        painter.scale(scale, scale)
        painter.translate(-cx, -cy)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, opt)
        painter.end()

    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, variant: str) -> None:
        key = variant.strip().lower()
        canonical = _VARIANT_CANONICAL.get(key)
        if canonical is None:
            raise ValueError(
                f"Unsupported StyledButton variant {variant!r}; "
                f"expected one of {sorted(VALID_BUTTON_VARIANTS)}"
            )
        self._variant = canonical
        self.setProperty("variant", canonical)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()
