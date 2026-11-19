"""CaseTile — Selectable public case-file entry for LevelSelectionScreen (Phase 4).

Renders ONLY whitelisted public metadata from ``LevelSummary``:
``puzzle_id``, ``title``, ``grid_size``, and optional ``difficulty_label``.
Never fabricates difficulty ratings and never reads puzzle JSON files.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QFrame, QWidget

from src.gui.components.status_label import StatusLabel
from src.gui.styles.tokens import SPACING
from src.gui.view_models import LevelSummary


class CaseTile(QFrame):
    """Selectable case-file tile inside a 3×3 / 4×4 / 5×5 group."""

    case_selected = Signal(str)  # puzzle_id
    case_activated = Signal(str)  # double-click / Enter -> direct open intent

    def __init__(
        self,
        summary: LevelSummary,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._summary = summary
        self._selected = False

        self.setProperty("widgetKind", "caseTile")
        self.setProperty("selected", "false")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        diff_tip = summary.difficulty_label or f"Lưới {summary.grid_size}×{summary.grid_size}"
        self.setToolTip(
            f"{summary.puzzle_id} — {summary.title} ({diff_tip})"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACING.space_3, SPACING.space_1, SPACING.space_3, SPACING.space_1)
        row.setSpacing(SPACING.space_2)

        self._title_label = QLabel(summary.title, self)
        self._title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._title_label.setProperty("role", "paperSubheading")
        self._title_label.setWordWrap(True)
        row.addWidget(self._title_label, 1)

        self._id_label = QLabel(summary.puzzle_id, self)
        self._id_label.setTextFormat(Qt.TextFormat.PlainText)
        self._id_label.setProperty("role", "paperMono")
        row.addWidget(self._id_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._meta_pill = StatusLabel(
            summary.difficulty_label or f"{summary.grid_size}×{summary.grid_size}",
            tone="paperNeutral",
            parent=self,
        )
        self._meta_pill.setVisible(bool(summary.difficulty_label))
        row.addWidget(self._meta_pill, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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
