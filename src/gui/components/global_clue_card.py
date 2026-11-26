"""Pinned overview of already-public global constraints and proved counts."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class GlobalClueCard(QFrame):
    clicked = Signal(str)
    hovered = Signal(str)
    hover_left = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GlobalClueCard")
        self.setStyleSheet(
            "QFrame#GlobalClueCard {background:#F6E7C3; border:1px solid #B99451; border-radius:7px;}"
            "QFrame#GlobalClueCard QLabel {color:#233247; background:transparent; border:none; font-size:12px;}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(3)
        self.title = QLabel("◎  TỔNG QUAN TOÀN BÀN", self)
        self.title.setStyleSheet("font-weight:700; color:#745529;")
        self.text_label = QLabel(self)
        self.text_label.setTextFormat(Qt.TextFormat.PlainText)
        self.text_label.setWordWrap(True)
        self.count_label = QLabel(self)
        self.count_label.setWordWrap(True)
        for label in (self.title, self.text_label, self.count_label):
            layout.addWidget(label)
        self._clue_id = None
        self._interactive = True
        self.hide()

    def set_clues(self, clues):
        chosen = next((c for c in clues if c.clue_type == "EXACTLY"), next(iter(clues), None))
        self._clue_id = chosen.clue_id if chosen else None
        self.text_label.setText(chosen.text if chosen else "")
        self.setVisible(chosen is not None)
        self.setAccessibleName(f"Manh mối toàn bàn: {chosen.text}" if chosen else "Tổng quan toàn bàn")

    def set_public_counts(self, criminals, innocent, unresolved):
        self.count_label.setText(f"Đã chứng minh: {criminals} tội phạm · {innocent} vô tội · {unresolved} chưa rõ")

    def set_interactive(self, enabled):
        self._interactive = bool(enabled)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._interactive and self._clue_id:
                self.clicked.emit(self._clue_id)
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._interactive and self._clue_id:
                self.clicked.emit(self._clue_id)
            event.accept()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event):  # noqa: N802
        if self._interactive and self._clue_id:
            self.hovered.emit(self._clue_id)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        if self._clue_id:
            self.hover_left.emit(self._clue_id)
        super().leaveEvent(event)
