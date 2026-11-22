"""CaseTile — Compact archival case-index row for Kho Hồ Sơ Vụ Án (LevelSelectionScreen).

Displays an official case index (``#01``..``#15``), clean Vietnamese editorial
title, and color-coded Vietnamese difficulty badge without showing raw technical
IDs. Renders a luminous antique-gold selection band with circular indicator when
selected, plus a silky brass hover sheen on mouse enter.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Property, QPointF, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QLinearGradient, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import EASE_SOFT, build_easing
from src.gui.case_catalog import (
    difficulty_pill_tone,
    localize_difficulty,
    split_case_number_and_name,
)
from src.gui.components.status_label import StatusLabel
from src.gui.view_models import LevelSummary

# Semantic difficulty badge palette on warm archival parchment (high contrast >= 5.5:1)
_DIFF_BADGE_STYLES: dict[str, tuple[str, str, str]] = {
    "nhập môn": ("#D6E7D4", "#9DC09A", "#1E4F30"),
    "dễ": ("#E3E5DB", "#BCC2B1", "#444E3B"),
    "trung bình": ("#EAE1CF", "#CCBFA4", "#524430"),
    "khó": ("#F0DDB7", "#D4B476", "#6A4714"),
    "rất khó": ("#F0D5C9", "#D3A490", "#7B3120"),
}


class CaseTile(QFrame):
    """Selectable archival case slip emitting ``case_selected`` and ``case_activated``."""

    case_selected = Signal(str)
    case_activated = Signal(str)

    def __init__(
        self,
        summary: LevelSummary,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._summary = summary
        self._selected = False
        self._hovered = False

        self.setObjectName(f"CaseTile_{summary.puzzle_id}")
        self.setProperty("widgetKind", "caseTile")
        self.setProperty("selected", "false")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        case_number, clean_title = split_case_number_and_name(summary.puzzle_id, summary.title)
        localized_diff = localize_difficulty(summary.difficulty_label)

        diff_tip = localized_diff or f"Lưới {summary.grid_size}×{summary.grid_size}"
        tip_prefix = f"{case_number} · " if case_number else ""
        self.setToolTip(f"{tip_prefix}{clean_title} ({diff_tip} · Mã {summary.puzzle_id})")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 2, 8, 2)
        row.setSpacing(7)

        self._code_label = QLabel(case_number or "", self)
        self._code_label.setTextFormat(Qt.TextFormat.PlainText)
        self._code_label.setProperty("role", "caseNumber")
        self._code_label.setFixedWidth(28)
        self._code_label.setVisible(bool(case_number))
        row.addWidget(self._code_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._title_label = QLabel(clean_title, self)
        self._title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._title_label.setProperty("role", "paperSubheading")
        self._title_label.setWordWrap(False)
        row.addWidget(self._title_label, 1, Qt.AlignmentFlag.AlignVCenter)

        # Kept hidden on the tile to avoid duplicating raw technical IDs (e.g. 3x3_01)
        self._id_label = QLabel(summary.puzzle_id, self)
        self._id_label.setTextFormat(Qt.TextFormat.PlainText)
        self._id_label.setProperty("role", "paperMono")
        self._id_label.setVisible(False)

        self._meta_pill = StatusLabel(
            localized_diff or f"{summary.grid_size}×{summary.grid_size}",
            tone=difficulty_pill_tone(localized_diff),
            parent=self,
        )
        self._meta_pill.setVisible(bool(localized_diff))
        self._apply_diff_pill_style(localized_diff)
        row.addWidget(self._meta_pill, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._sheen_progress: float = 1.0
        self._sheen_anim = QPropertyAnimation(self, b"sheen_progress", self)
        self._sheen_anim.setDuration(DEFAULT_MOTION.scaled_ms(400))
        self._sheen_anim.setEasingCurve(build_easing(EASE_SOFT))

        self._sync_text_colors()

    def _apply_diff_pill_style(self, localized_diff: Optional[str]) -> None:
        key = (localized_diff or "").strip().lower()
        bg, bd, fg = _DIFF_BADGE_STYLES.get(key, ("#EAE1CF", "#CCBFA4", "#4D4030"))
        self._meta_pill.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {bd}; "
            "border-radius: 4px; padding: 1px 7px; font-weight: 700; font-size: 11px;"
        )

    def _sync_text_colors(self) -> None:
        if self._selected:
            self._code_label.setStyleSheet(
                "color: #2B1A06; font-weight: 800; font-size: 12px; background: transparent; border: none;"
            )
            self._title_label.setStyleSheet(
                "color: #1D1205; font-weight: 800; font-size: 12.5px; background: transparent; border: none;"
            )
        else:
            self._code_label.setStyleSheet(
                "color: #6E5838; font-weight: 700; font-size: 11.5px; background: transparent; border: none;"
            )
            self._title_label.setStyleSheet(
                "color: #212A38; font-weight: 600; font-size: 12.5px; background: transparent; border: none;"
            )

    def _get_sheen_progress(self) -> float:
        return self._sheen_progress

    def _set_sheen_progress(self, value: float) -> None:
        self._sheen_progress = max(0.0, min(1.0, float(value)))
        self.update()

    sheen_progress = Property(float, _get_sheen_progress, _set_sheen_progress)

    def _trigger_sheen(self) -> None:
        if DEFAULT_MOTION.reduced_motion or not self.isVisible():
            return
        self._sheen_anim.stop()
        self._sheen_progress = 0.0
        self._sheen_anim.setStartValue(0.0)
        self._sheen_anim.setEndValue(1.0)
        self._sheen_anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._trigger_sheen()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        if w <= 4 or h <= 4:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(1.0, 1.0, w - 2.0, h - 2.0)

        if self._selected:
            # Signature luminous antique-gold selection band (matching #14 mockup highlight!)
            sel_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
            sel_grad.setColorAt(0.0, QColor("#E4B150"))
            sel_grad.setColorAt(0.55, QColor("#F3D284"))
            sel_grad.setColorAt(1.0, QColor("#E7BC64"))
            painter.setBrush(sel_grad)
            painter.setPen(QPen(QColor("#BC8528"), 1.3))
            painter.drawRoundedRect(rect, 5.0, 5.0)

            # Crisp selection dot indicator on far left edge
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFF8E6"))
            painter.drawEllipse(QPointF(6.5, h * 0.5), 2.8, 2.8)
        else:
            bg = QColor("#F4E8CE") if self._hovered else QColor("#FAF4E6")
            painter.setBrush(bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 4.0, 4.0)

            # Subtle bottom archival hairline rule
            painter.setPen(QPen(QColor("#E3D2B2"), 1.0))
            painter.drawLine(QPointF(6.0, h - 1.0), QPointF(w - 6.0, h - 1.0))

        # Silk arrival sheen sweep on hover
        t = self._sheen_progress
        if t < 0.995:
            fade = 1.0 - t
            cx = -0.25 * w + t * 1.50 * w
            grad = QLinearGradient(cx - 0.28 * w, 0.0, cx + 0.28 * w, h * 0.25)
            grad.setColorAt(0.0, QColor(228, 185, 102, 0))
            grad.setColorAt(0.5, QColor(228, 185, 102, int(48 * fade)))
            grad.setColorAt(1.0, QColor(228, 185, 102, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(rect.adjusted(1.0, 1.0, -1.0, -1.0), 4.0, 4.0)

        painter.end()

    @property
    def summary(self) -> LevelSummary:
        return self._summary

    @property
    def puzzle_id(self) -> str:
        return self._summary.puzzle_id

    @property
    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        flag = bool(selected)
        if self._selected == flag:
            return
        self._selected = flag
        self.setProperty("selected", "true" if flag else "false")
        self._sync_text_colors()
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.case_selected.emit(self._summary.puzzle_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.case_selected.emit(self._summary.puzzle_id)
            self.case_activated.emit(self._summary.puzzle_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self.case_selected.emit(self._summary.puzzle_id)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.case_selected.emit(self._summary.puzzle_id)
            self.case_activated.emit(self._summary.puzzle_id)
            event.accept()
            return
        super().keyPressEvent(event)
