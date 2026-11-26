"""A readable view of one public clue; the clue still belongs to its board card."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from src.gui.asset_registry import VIETNAMESE_CLUE_LABELS
from src.gui.styles.investigation import PANEL_STYLE
from src.gui.view_models import normalize_clue_view


class ClueReader(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ClueReader")
        self.setStyleSheet(PANEL_STYLE)
        self.setMinimumHeight(156)
        self._clues = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.source_label = QLabel("MANH MỐI ĐANG ĐỌC", self)
        self.source_label.setObjectName("ClueReaderSource")
        self.type_label = QLabel(self)
        self.type_label.setObjectName("ClueReaderType")
        header.addWidget(self.source_label, 1)
        header.addWidget(self.type_label)
        layout.addLayout(header)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumHeight(40)
        copy = QWidget(self.scroll_area)
        copy.setObjectName("ClueReaderCopy")
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 5, 0)
        self.body_label = QLabel(copy)
        self.body_label.setObjectName("ClueReaderText")
        self.body_label.setWordWrap(True)
        self.body_label.setTextFormat(Qt.TextFormat.PlainText)
        self.body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        copy_layout.addWidget(self.body_label)
        copy_layout.addStretch(1)
        self.scroll_area.setWidget(copy)
        layout.addWidget(self.scroll_area, 1)
        self.reference_label = QLabel(self)
        self.reference_label.setObjectName("ClueReaderReferences")
        self.reference_label.setWordWrap(True)
        self.reference_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.reference_label)
        self.set_clues(())

    @property
    def clues(self):
        return self._clues

    def set_clues(self, clues):
        projected = tuple(normalize_clue_view(c) for c in clues)
        old_id = self._clues[0].clue_id if self._clues else None
        self._clues = projected[:1]
        clue = self._clues[0] if self._clues else None
        if clue:
            self.source_label.setText(f"MANH MỐI ĐANG ĐỌC  ·  Ô {clue.owner_id}")
            self.type_label.setText(VIETNAMESE_CLUE_LABELS.get(clue.clue_type, clue.clue_type))
            self.body_label.setText(clue.text)
            cells = clue.referenced_cells
            if clue.scope == "ALL":
                refs = f"Toàn bàn · {len(cells)} nghi phạm"
            else:
                refs = ", ".join(cells[:7])
                if len(cells) > 7:
                    refs += f" và {len(cells) - 7} ô khác"
            self.reference_label.setText(f"Phạm vi: {refs}" if refs else "Manh mối công khai")
            self.setAccessibleName(f"Manh mối ô {clue.owner_id}. {clue.text}")
            if old_id != clue.clue_id:
                self.scroll_area.verticalScrollBar().setValue(0)
        else:
            self.setAccessibleName("Manh mối đang đọc. Chưa chọn manh mối.")
            self.source_label.setText("MANH MỐI ĐANG ĐỌC")
            self.type_label.clear()
            self.body_label.setText("Di chuột lên manh mối dưới thẻ để đọc đầy đủ. Nhấp để ghim và xem các ô liên quan.")
            self.reference_label.setText("Nhấp đúp vào dải manh mối để thu gọn / mở lại.")

    def set_reduced_motion(self, enabled):
        pass  # This reading surface has no decorative motion.

    def set_interactive(self, enabled):
        pass  # Reading never submits a verdict or changes the board.
