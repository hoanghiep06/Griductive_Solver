"""SectionPlaceholder temporary container marking GĐ3/GĐ4 extension slots (Phase 2)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.gui.components.status_label import StatusLabel
from src.gui.styles.tokens import SPACING


class SectionPlaceholder(QFrame):
    """Clearly labeled temporary region reserved for future GĐ3/GĐ4 widgets."""

    def __init__(
        self,
        title: str,
        *,
        target_phase: str,
        description: str,
        emphasis: str = "standard",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("widgetKind", "sectionPlaceholder")
        self.setProperty("emphasis", emphasis)

        self._title = title
        self._target_phase = target_phase

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.space_3, SPACING.space_3, SPACING.space_3, SPACING.space_3)
        layout.setSpacing(SPACING.space_2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._phase_badge = StatusLabel(f"VÙNG CHỜ · {target_phase}", tone="accent", parent=self)
        layout.addWidget(self._phase_badge, 0, Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel(title, self)
        self._title_label.setProperty("role", "subheading")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self._title_label)

        self._desc_label = QLabel(description, self)
        self._desc_label.setProperty("role", "caption")
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc_label.setWordWrap(True)
        self._desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self._desc_label)

    @property
    def title(self) -> str:
        return self._title

    @property
    def target_phase(self) -> str:
        return self._target_phase
