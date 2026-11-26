"""Dedicated tutorial view using the production board and public clue cards."""

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from src.gui.components.clue_panel import CluePanel
from src.gui.components.tutorial_overlay import TutorialOverlay
from src.gui.assets.tutorial_portraits import TutorialPortraitRegistry
from src.gui.grid_view import GameBoard


class TutorialDialog(QDialog):
    def __init__(self, *, pixmap_loader=None, reduced_motion=False, parent=None):
        super().__init__(parent)
        self.setObjectName("TutorialDialog")
        self.setWindowTitle("Hướng dẫn chơi · Griductive Solvers")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(760, 560)
        if parent:
            self.resize(parent.size())
        else:
            self.resize(1200, 800)
        self.setStyleSheet(
            "QDialog#TutorialDialog {background:#182435;}"
            "QDialog#TutorialDialog QLabel#TutorialHeading {color:#F4DEAC; font-size:18px; font-weight:700;}"
            "QDialog#TutorialDialog QLabel#TutorialBoardCaption {color:#ECDAB5; font-size:12px;}"
            "QDialog#TutorialDialog QPushButton#TutorialVerdict {min-height:38px; border:1px solid #C6A466;"
            "border-radius:7px; background:#EDE0C4; color:#253348; font-size:14px; font-weight:700;}"
            "QDialog#TutorialDialog QPushButton#TutorialVerdict:disabled {color:#817A6C; background:#C6BEAE;}"
            "QDialog#TutorialDialog QPushButton#TutorialVerdict:focus {border:2px solid #48BFDD;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        self.heading = QLabel("HƯỚNG DẪN CHƠI  /  HỒ SƠ ĐẦU TIÊN", self)
        self.heading.setObjectName("TutorialHeading")
        header.addWidget(self.heading, 1)
        self.skip_slot = QWidget(self)
        self.skip_slot.setFixedSize(178, 36)
        header.addWidget(self.skip_slot)
        layout.addLayout(header)

        workspace = QHBoxLayout()
        workspace.setSpacing(16)
        left = QVBoxLayout()
        self.board = GameBoard(pixmap_loader=pixmap_loader,
                               portrait_registry=TutorialPortraitRegistry(), parent=self)
        self.board.set_interactive(False)  # Only the spotlight's permitted target may be selected.
        self.board.set_reduced_motion(reduced_motion)
        left.addWidget(self.board, 1)
        self.board_caption = QLabel("BÀN TẬP 4 × 4  •  1/16 thẻ đã mở", self)
        self.board_caption.setObjectName("TutorialBoardCaption")
        self.board_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.board_caption)
        workspace.addLayout(left, 6)

        sidebar = QWidget(self)
        sidebar.setMinimumWidth(330)
        sidebar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right = QVBoxLayout(sidebar)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)
        self.clues = CluePanel(pixmap_loader=pixmap_loader, parent=sidebar)
        self.clues.set_reduced_motion(reduced_motion)
        self.clues.set_interactive(False)
        self.clues.setFixedHeight(190)
        right.addWidget(self.clues)
        self.tooltip_slot = QWidget(sidebar)
        self.tooltip_slot.setMinimumHeight(225)
        right.addWidget(self.tooltip_slot, 1)
        verdicts = QHBoxLayout()
        self.criminal_button = QPushButton("Tội phạm", sidebar)
        self.innocent_button = QPushButton("Vô tội", sidebar)
        for button in (self.criminal_button, self.innocent_button):
            button.setObjectName("TutorialVerdict")
            button.setAutoDefault(False)
            verdicts.addWidget(button)
        right.addLayout(verdicts)
        workspace.addWidget(sidebar, 4)
        layout.addLayout(workspace, 1)

        self.focus_mode = "board"
        self.focus_cells = ()
        self.target_cell = None
        self.expected_verdict = None
        self.selected = False
        self.overlay = TutorialOverlay(self, self.target_geometry, self.tooltip_slot, self.skip_slot)
        self.overlay.set_reduced_motion(reduced_motion)
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(self._refresh_overlay)
        self.finished.connect(self._layout_timer.stop)
        # Refresh after Qt completes any deferred layouts. All rectangles are
        # recalculated on demand, including when reduced motion stops the timer.
        for widget in (self, self.board, self.board.viewport(), self.clues,
                       sidebar, self.tooltip_slot, self.skip_slot):
            widget.installEventFilter(self)
        self.board.horizontalScrollBar().valueChanged.connect(self.overlay.update)
        self.board.verticalScrollBar().valueChanged.connect(self.overlay.update)
        self.clues.scroll_area.verticalScrollBar().valueChanged.connect(self.overlay.update)

        from src.controller.tutorial_controller import TutorialController
        self.controller = TutorialController(self)
        self.finished.connect(self.controller.stop)

    def widget_rect(self, widget):
        origin = self.overlay.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0)))
        return QRectF(origin, widget.size())

    def cell_rect(self, cell_id):
        card = self.board.cards_by_id.get(cell_id)
        if card is None:
            return QRectF()
        # mapRectToScene includes each card's current position/transform; the
        # viewport mapping includes the board's fit scale and scroll offset.
        rect = self.board.mapFromScene(card.mapRectToScene(card.card_rect())).boundingRect()
        rect = rect.intersected(self.board.viewport().rect())
        origin = self.overlay.mapFromGlobal(self.board.viewport().mapToGlobal(rect.topLeft()))
        return QRectF(origin, rect.size())

    def target_geometry(self):
        if self.focus_mode in {"board", "complete"}:
            return [self.widget_rect(self.board)], [], self.cell_rect("A1")
        clue_rect = self.widget_rect(self.clues)
        if self.focus_mode == "clue":
            return [clue_rect], [], clue_rect
        highlights = [clue_rect]
        highlights.extend(self.cell_rect(cid) for cid in dict.fromkeys(self.focus_cells)
                          if cid != self.target_cell)
        actions = []
        pointer = None
        if self.target_cell:
            cell_rect = self.cell_rect(self.target_cell)
            highlights.append(cell_rect)
            pointer = cell_rect
            actions.append((f"cell:{self.target_cell}", cell_rect))
            if self.selected:
                for verdict, button in (("CRIMINAL", self.criminal_button), ("INNOCENT", self.innocent_button)):
                    rect = self.widget_rect(button)
                    highlights.append(rect)
                    actions.append((f"verdict:{verdict}", rect))
                    if verdict == self.expected_verdict:
                        pointer = rect
        return [r for r in highlights if not r.isEmpty()], actions, pointer

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.LayoutRequest):
            if hasattr(self, "overlay"):
                self._layout_timer.start(0)
        return super().eventFilter(watched, event)

    def _refresh_overlay(self):
        if self.isVisible():
            self.overlay.refresh_geometry()
            self.overlay.update()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._layout_timer.start(0)
        self.overlay.setFocus()

    def set_reduced_motion(self, enabled):
        self.board.set_reduced_motion(enabled)
        self.clues.set_reduced_motion(enabled)
        self.overlay.set_reduced_motion(enabled)
