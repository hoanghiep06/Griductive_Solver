"""PageHeader editorial masthead component (Design System V2)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.styles.tokens import GEOMETRY, SPACING


class PageHeader(QFrame):
    """Consistent editorial screen header with serif title, subtitle, and action slots."""

    def __init__(
        self,
        title: str,
        *,
        subtitle: Optional[str] = None,
        left_widget: Optional[QWidget] = None,
        right_widget: Optional[QWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("widgetKind", "pageHeader")
        self.setMinimumHeight(GEOMETRY.header_height + 6)

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACING.space_5, SPACING.space_2, SPACING.space_5, SPACING.space_2)
        row.setSpacing(SPACING.space_4)

        if left_widget is not None:
            row.addWidget(left_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        self._title_label = QLabel(title, self)
        self._title_label.setProperty("role", "paperTitle")
        text_col.addWidget(self._title_label)

        self._subtitle_label: Optional[QLabel] = None
        if subtitle:
            self._subtitle_label = QLabel(subtitle, self)
            self._subtitle_label.setProperty("role", "paperCaption")
            text_col.addWidget(self._subtitle_label)

        row.addLayout(text_col, 1)

        if right_widget is not None:
            row.addWidget(right_widget, 0, Qt.AlignmentFlag.AlignVCenter)

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def subtitle_label(self) -> Optional[QLabel]:
        return self._subtitle_label
