"""Orchestrate the independent tutorial; never touches PlayController.session."""

import logging

from PySide6.QtCore import QObject

from src.core.game_engine import VerdictResponse
from src.tutorial.data import TUTORIAL_STEPS
from src.tutorial.session import TutorialSession
from src.gui.components.character_card import ClueNote

logger = logging.getLogger(__name__)


class TutorialController(QObject):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.model = TutorialSession()
        self._pending = None
        self._closed = False
        self._selected = False
        board = self.model.game.board()
        view.board.portrait_registry.set_tutorial_characters(board.characters)
        view.board.set_board(board)
        view.overlay.next_requested.connect(self.advance)
        view.overlay.skip_requested.connect(view.reject)
        view.overlay.activated.connect(self.activate)
        view.criminal_button.clicked.connect(lambda: self.submit("CRIMINAL"))
        view.innocent_button.clicked.connect(lambda: self.submit("INNOCENT"))
        view.board.animation_finished.connect(self._finish_reveal)
        self._render_step()

    def _render_step(self):
        step = self.model.step
        view = self.view
        self._selected = False
        view.selected = False
        view.focus_mode = step.focus
        view.target_cell = step.target
        view.expected_verdict = step.verdict
        view.board.clear_selection()
        public_clues = self.model.game.board().clues
        clue = next((c for c in public_clues if c.clue_id == step.clue_id), None)
        # Display the precise public clue discussed by this step, without
        # crowding the lesson with all previously opened clues.
        view.clues.set_clues([clue] if clue else public_clues[:1])
        self._sync_clue_notes()
        view.focus_cells = clue.referenced_cells if clue else ()
        view.board.highlight_cells(view.focus_cells)
        view.board.set_interactive(False)
        self._present()

    def _sync_clue_notes(self):
        """Use the same under-card clue strips as the real investigation desk."""
        active = self.model.step.clue_id
        if self.model.index == 0:
            active = self.model.game.board().clues[0].clue_id
        self.view.board.set_clue_notes({
            c.owner_id: ClueNote(c.clue_id, c.clue_type, c.text,
                                 "normal" if c.clue_id == active else "spent", c.clue_id == active)
            for c in self.model.game.board().clues
        })

    def _present(self, message=""):
        view = self.view
        ready = self._selected and not self.model.can_advance and self._pending is None and not self._closed
        view.criminal_button.setEnabled(ready)
        view.innocent_button.setEnabled(ready)
        view.overlay.present(self.model.step, self.model.index, len(TUTORIAL_STEPS),
                             can_advance=self.model.can_advance, selected=self._selected,
                             busy=self._pending is not None, message=message)
        count = len(self.model.game.engine.get_proved_verdicts())
        view.board_caption.setText(f"BÀN TẬP 4 × 4  •  {count}/16 thẻ đã mở")

    def activate(self, key):
        if self._closed or self._pending is not None or self.model.can_advance:
            return
        if key == f"cell:{self.model.step.target}":
            self._selected = True
            self.view.selected = True
            self.view.board.set_selection(self.model.step.target)
            self._present()
        elif key.startswith("verdict:"):
            verdict = key.partition(":")[2]
            if verdict == "CRIMINAL":
                self.view.criminal_button.click()
            elif verdict == "INNOCENT":
                self.view.innocent_button.click()

    def submit(self, verdict):
        if self._closed or not self._selected or self._pending is not None or self.model.can_advance:
            return
        step = self.model.step
        try:
            response = self.model.submit(step.target, verdict)
        except Exception:
            logger.exception("Tutorial proof failed at step %s", self.model.index)
            self._present("Không thể kiểm tra suy luận. Bạn có thể thử lại hoặc Bỏ qua hướng dẫn.")
            return
        if response is not VerdictResponse.ACCEPTED:
            self._present(
                "Chưa đúng. Hãy đọc lại phần Phân tích và Suy ra kết quả, rồi chọn phe phù hợp."
                if response is VerdictResponse.CONTRADICTED else
                "Chưa chứng minh được phán quyết này. Hãy xem lại manh mối đang sáng."
            )
            return
        board = self.model.game.board()
        token = (self.model.game.session_id, self.model.index)
        self._pending = (token, board)
        self._present()
        target = next(c for c in board.characters if c.cell_id == step.target)
        if not self.view.board.reveal_card(step.target, target, token=token):
            self._finish_reveal(step.target, token)

    def _finish_reveal(self, cell_id, token):
        if self._closed or self._pending is None or self._pending[0] != token:
            return
        _, board = self._pending
        self._pending = None
        self.view.board.set_board(board)
        self._sync_clue_notes()
        self.view.board.highlight_cells(self.view.focus_cells)
        self.view.board.set_interactive(False)
        self._present()
        self.view.overlay.next_button.setFocus()

    def advance(self):
        if self._closed or self._pending is not None or not self.model.can_advance:
            return
        if self.model.step.focus == "complete":
            self.view.accept()
        elif self.model.advance():
            self._render_step()

    def stop(self, *_):
        self._closed = True
        self._pending = None
        self.view.board.cancel_animations(revert_to_original=False)
        self.view.overlay.hide()
        self.view.board.motion_coordinator.reset_visuals(self.view.board.cards_by_id)
