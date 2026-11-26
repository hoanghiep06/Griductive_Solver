"""ScratchpadPanel — free-form personal notes (\"Nháp\") beside the board.

Presentation-only: never touches GameEngine / SAT / hints. The text and the
per-card draft marks are the player's own memory aids and are cleared on
Restart / new case by GameplayScreen.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QSizePolicy, QWidget

from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import SPACING


class ScratchpadPanel(StyledPanel):
    """Cream notebook page with a free-text editor and a draft-mark summary."""

    text_changed = Signal(str)
    clear_requested = Signal()

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Nháp",
            subtitle="Ghi chú riêng của bạn, không ảnh hưởng suy luận",
            variant="paper",
            padding=SPACING.space_3,
            decorative_texture=False,
            accent_bar=None,
            parent=parent,
        )
        self.setObjectName("ScratchpadPanel")
        if self.title_label is not None:
            self.title_label.setStyleSheet(
                "color: #162436; font-family: Georgia, serif; font-size: 18px; "
                "font-weight: 800; font-style: italic; background: transparent;"
            )
        self.setStyleSheet(
            "QFrame#ScratchpadPanel {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCF6E9, stop:1 #F4E9D2);"
            "  border: 1.5px solid #C9AC78;"
            "  border-radius: 9px;"
            "}"
        )
        self.content_layout.setSpacing(SPACING.space_2)

        self._legend = QLabel(
            "Thẻ chưa lật: chuột phải (hoặc phím D) để xoay dấu "
            "? → nghi phạm → vô tội → bỏ dấu.",
            self,
        )
        self._legend.setTextFormat(Qt.TextFormat.PlainText)
        self._legend.setWordWrap(True)
        self._legend.setStyleSheet(
            "color: #4E5A67; font-size: 11.5px; background: transparent;"
        )
        self.content_layout.addWidget(self._legend)

        self._summary = QLabel("Chưa đánh dấu thẻ nào.", self)
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        self._summary.setStyleSheet(
            "color: #7C5821; font-size: 12px; font-weight: 700; background: transparent;"
        )
        self.content_layout.addWidget(self._summary)

        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText("Viết nháp tại đây: giả thiết, phép loại trừ, việc cần kiểm tra...")
        self._editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._editor.setMinimumHeight(72)
        self._editor.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #FBF7F0; color: #1F2430; border: 1px solid #D5C7B2;"
            "  border-radius: 6px; padding: 6px; font-size: 13px;"
            "  selection-background-color: #C9AC78;"
            "}"
        )
        self._editor.textChanged.connect(lambda: self.text_changed.emit(self._editor.toPlainText()))
        self.content_layout.addWidget(self._editor, 1)

        self._clear_button = StyledButton("Xóa nháp", variant="ghost", min_height=28, parent=self)
        self._clear_button.setProperty("compact", "true")
        self._clear_button.setToolTip("Xóa ghi chú nháp (không xóa dấu trên thẻ)")
        self._clear_button.clicked.connect(self._on_clear_clicked)
        self.content_layout.addWidget(self._clear_button, 0, Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------

    @property
    def editor(self) -> QPlainTextEdit:
        return self._editor

    def text(self) -> str:
        return self._editor.toPlainText()

    def set_text(self, value: str) -> None:
        self._editor.setPlainText(value)

    def clear(self) -> None:
        self._editor.clear()
        self.set_mark_summary(0, 0, 0)

    def set_mark_summary(self, unsure: int, suspect: int, innocent: int) -> None:
        if unsure + suspect + innocent == 0:
            self._summary.setText("Chưa đánh dấu thẻ nào.")
        else:
            self._summary.setText(
                f"Đã đánh dấu: {unsure} nghi vấn · {suspect} nghi phạm · {innocent} vô tội"
            )

    def _on_clear_clicked(self) -> None:
        self._editor.clear()
        self.clear_requested.emit()