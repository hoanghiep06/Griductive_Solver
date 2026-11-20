"""Qt orchestration for real play; presentation state stays on GameplayScreen.

SAT requests run in a worker pool. Request generations, session IDs and KB
versions guard every completion against Load / Restart / Pause races.
"""

import json
import logging
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from src.agent.entailment import Verdict
from src.core.game_engine import VerdictResponse
from src.controller.gameplay_session import Analysis, Evidence, GameplaySession
from src.gui.view_models import (
    ActionCode, ActionResult, DeductionStepView, GameState, HintView, LevelSummary,
)
from src.gui.animations.motion_config import DEFAULT_MOTION

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _WorkSignals(QObject):
    finished = Signal(int, str, object, object)


class _Work(QRunnable):
    def __init__(self, generation, operation, function):
        super().__init__()
        self.generation, self.operation, self.function = generation, operation, function
        self.signals = _WorkSignals()

    def run(self):
        try:
            result, error = self.function(), None
        except Exception as exc:
            logger.exception("Gameplay request failed: %s", self.operation)
            result, error = None, exc
        self.signals.finished.emit(self.generation, self.operation, result, error)


class PlayController(QObject):
    """Composition adapter; the engine remains the sole authority for reveals."""

    def __init__(self, window, puzzle_dir: Path | None = None):
        super().__init__(window)
        self.window = window
        self.screen = window.gameplay_screen
        self.session: GameplaySession | None = None
        self.puzzle_dir = puzzle_dir or PROJECT_ROOT / "puzzles"
        self._paths: dict[str, Path] = {}
        self._generation = 0
        self._busy = False
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._pending = None
        self._evidence = Evidence()
        self._steps = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._auto_interval_ms = DEFAULT_MOTION.auto_step_interval
        self._timer.setInterval(self._auto_interval_ms)
        self._timer.timeout.connect(self._auto_step)
        window.play_requested.connect(self.open_levels)
        window.level_selection_requested.connect(self.open_levels)
        window.load_requested.connect(self.load)
        window.restart_requested.connect(self.restart)
        window.hint_requested.connect(self.hint)
        window.auto_solve_requested.connect(self.toggle_auto)
        window.verdict_requested.connect(self.guess)
        window.back_requested.connect(self.back)
        window.exit_requested.connect(window.close)
        window.how_to_play_requested.connect(window.show_how_to_play)
        window.animation_finished.connect(self._finish_reveal)
        self.screen.auto_solve_speed_changed.connect(self.set_auto_speed)
        self.screen.notification_banner.inspect_requested.connect(self.inspect_contradiction)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self.stop)

    @property
    def state(self):
        return self.screen.ui_state

    def _catalog(self):
        path = self.puzzle_dir / "manifest.json"
        entries = json.loads(path.read_text(encoding="utf-8")).get("puzzles", [])
        catalog = []
        self._paths = {}
        root = self.puzzle_dir.resolve()
        for entry in entries:
            target = (root / entry["file"]).resolve()
            if not target.is_relative_to(root):
                continue
            pid = entry["puzzle_id"]
            self._paths[pid] = target
            catalog.append(LevelSummary(pid, f"Hồ sơ {pid}", entry["size"], entry.get("difficulty_label")))
        return catalog

    def open_levels(self):
        self.stop()
        self.screen.dismiss_interaction_dialogs()
        try:
            self.window.level_selection_screen.set_levels(self._catalog())
            self.window.show_level_selection()
        except (OSError, ValueError, KeyError):
            self._notice(ActionCode.LOAD_FAILED, "Không thể đọc danh sách màn chơi. Kiểm tra puzzles/manifest.json.")

    def back(self):
        self.stop()
        self.screen.dismiss_interaction_dialogs()
        self.window.show_main_menu()

    def _cancel_request(self):
        self._generation += 1
        self._busy = False
        self._timer.stop()
        self._pool.clear()

    def stop(self):
        self._cancel_request()
        self.state.is_auto_solving = False
        self.screen.action_bar.set_auto_solving(False)
        if self._pending is not None:
            # Accepted engine transactions survive Pause/navigation; commit the
            # public view immediately and invalidate the old animation token.
            pending, self._pending = self._pending, None
            self.screen.cancel_animations(revert_to_original=False)
            self.screen.set_board(pending[1])
            if pending[2] is not None:
                self.screen.show_hint(pending[2])
        if self.session is not None:
            self._ready()

    def load(self, puzzle_id: str):
        self.stop()
        if not self._paths:
            self._catalog()
        path = self._paths.get(puzzle_id)
        if path is None:
            self._notice(ActionCode.LOAD_FAILED, "Không tìm thấy màn chơi được chọn.")
            return
        self.screen.set_game_status(GameState.PROCESSING)
        self._submit("load", lambda: GameplaySession(path))

    def restart(self):
        self.stop()
        if self.session is None:
            return
        self.session.restart()
        self.screen.set_game_status(GameState.PROCESSING)
        self.screen.restart_with_transition(self.session.board(), self._finish_restart)

    def _finish_restart(self):
        self._steps = 0
        self._evidence = Evidence()
        self._ready()
        self.window.show_gameplay()

    def _reset_screen(self):
        self._steps = 0
        self._evidence = Evidence()
        self.screen.reset_for_new_case(self.session.board())
        self._ready()
        self.window.show_gameplay()

    def guess(self, cell_id, verdict):
        if self._busy or self.state.is_auto_solving or self._pending or not self.session:
            return
        if cell_id not in self.session.engine.get_unsolved_characters():
            return
        label = getattr(verdict, "value", verdict)
        if label not in {"CRIMINAL", "INNOCENT"}:
            return
        self.screen.dismiss_notification()
        self.screen.clear_hint()
        self._claimed = label == "CRIMINAL"
        session = self.session
        self._submit("guess", lambda: session.analyze(cell_id))

    def hint(self):
        if self._busy or self._pending or self.state.is_auto_solving or not self.session or self.session.engine.is_solved():
            return
        self.screen.dismiss_notification()
        session = self.session
        self._submit("hint", session.analyze)

    def toggle_auto(self):
        if self.state.is_auto_solving:
            self.stop()
            return
        if self._busy or self._pending or not self.session or self.session.engine.is_solved():
            return
        self.screen.dismiss_notification()
        self.state.is_auto_solving = True
        self.screen.action_bar.set_auto_solving(True)
        self._auto_step()

    def set_auto_speed(self, interval_ms: int):
        self._auto_interval_ms = max(250, min(1200, int(interval_ms)))
        self._timer.setInterval(self._auto_interval_ms)
        if self.state.is_auto_solving and self._timer.isActive():
            self._timer.start(self._auto_interval_ms)

    def _auto_step(self):
        if not self.state.is_auto_solving or self._busy or self._pending:
            return
        self._submit("auto", self.session.analyze)

    def _submit(self, operation, function):
        self._busy = True
        self.screen.set_game_status(GameState.PROCESSING)
        work = _Work(self._generation, operation, function)
        work.signals.finished.connect(self._completed)
        self._pool.start(work)

    @Slot(int, str, object, object)
    def _completed(self, generation, operation, result, error):
        if generation != self._generation:
            return
        self._busy = False
        if error is not None:
            self.stop()
            self._notice(ActionCode.LOAD_FAILED if operation == "load" else ActionCode.SOLVER_FAILED,
                         "Không thể nạp hồ sơ. Ván hiện tại vẫn được giữ lại." if operation == "load"
                         else "Không thể hoàn thành suy luận. Hãy thử lại hoặc chọn hồ sơ khác.")
            return
        if operation == "load":
            self.session = result
            self._reset_screen()
            return
        if result.version != self.session.engine.public_kb_version:
            self._ready()
            return
        if result.inconsistent:
            self.stop()
            self.screen.set_game_status(GameState.ERROR)
            self._notice(ActionCode.INCONSISTENT, "Các dữ kiện công khai không nhất quán. Hãy kiểm tra dữ liệu màn chơi.")
            return
        if result.classification is None:
            self.stop()
            self.screen.set_game_status(GameState.STUCK)
            self.screen.show_hint(HintView(self.session.session_id, result.version, "NO_FORCED", None, None,
                                          "Chưa tìm thấy bước chắc chắn từ dữ kiện hiện có. Hãy xem lại các manh mối đang mở."))
            return
        claimed = self._claimed if operation == "guess" else result.classification.verdict is Verdict.CRIMINAL
        proof = result.classification.to_engine_result(result.cell_id, result.version)
        try:
            response, _ = self.session.engine.submit_verdict(result.cell_id, claimed, proof)
        except Exception:
            logger.exception("Engine refused a proof")
            self.stop()
            self._notice(ActionCode.INTERNAL_ERROR, "Không thể xác nhận bước suy luận này. Hãy chọn lại hồ sơ.")
            return
        if response is VerdictResponse.ACCEPTED:
            if operation == "hint":
                self.state.hint_count += 1
            self._accept(result, operation)
            return
        self._ready()
        if response in (VerdictResponse.NOT_PROVABLE, VerdictResponse.CONTRADICTED):
            self.state.mistake_count += 1
            self._evidence = result.evidence
            if response is VerdictResponse.NOT_PROVABLE:
                message = (f"Ô {result.cell_id}: lựa chọn này chưa thể khẳng định chắc chắn. "
                           "Cả hai khả năng tội phạm và vô tội vẫn phù hợp với dữ kiện hiện có. "
                           "Hãy khai thác thêm manh mối trước khi kết luận.")
            else:
                message = (f"Ô {result.cell_id}: lựa chọn này mâu thuẫn trực tiếp với các manh mối "
                           "hoặc các ô đã được chứng minh. Soi chứng cứ để đối chiếu lại kết luận.")
                card = self.screen.game_board.cards_by_id.get(result.cell_id)
                if card:
                    card.shake()
            self._notice(ActionCode(response.value), message, result.cell_id)
            self.screen.set_contradiction_inspect_available(
                response is VerdictResponse.CONTRADICTED
                and bool(result.evidence.clue_ids or result.evidence.cell_ids)
            )
            self._stats()
        else:
            self._notice(ActionCode(response.value), "Dữ kiện đã thay đổi. Hãy thử lại trên bàn cờ hiện tại.")

    def _accept(self, analysis: Analysis, operation: str):
        self._steps += 1
        board = self.session.board()
        verdict = analysis.classification.verdict.value
        text = self._explanation(analysis)
        self.screen.focus_evidence(analysis.evidence.clue_ids, (*analysis.evidence.cell_ids, analysis.cell_id))
        if operation in {"hint", "auto"}:
            self.screen.animate_hint_flow(
                analysis.evidence.clue_ids,
                analysis.evidence.cell_ids,
                analysis.cell_id,
            )
        self.screen.append_deduction_step(DeductionStepView(
            self.session.session_id, self._steps, board.kb_version, analysis.cell_id, verdict, text,
            source_clue_ids=analysis.evidence.clue_ids, step=self._steps,
            sat_calls=analysis.classification.sat_calls,
        ))
        short_text = text if len(text) <= 260 else (
            f"Dựa vào {len(analysis.evidence.clue_ids)} manh mối được tô sáng và các ô đã chứng minh, "
            f"{analysis.cell_id} bắt buộc là {'tội phạm' if verdict == 'CRIMINAL' else 'vô tội'}. "
            "Giả thiết ngược lại mâu thuẫn với tập chứng cứ này. Xem chi tiết trong nhật ký bên dưới."
        )
        hint = HintView(self.session.session_id, board.kb_version, "FORCED", analysis.cell_id, verdict,
                        short_text, analysis.evidence.clue_ids) if operation in {"hint", "auto"} else None
        if hint:
            self.screen.show_hint(hint)
        token = (self.session.session_id, self._steps)
        self._pending = (token, board, hint)
        self._last_analysis = analysis
        self._reveal_started = perf_counter()
        self.screen.set_game_status(GameState.ANIMATING)
        target = next(c for c in board.characters if c.cell_id == analysis.cell_id)
        if not self.screen.reveal_card(analysis.cell_id, target, token):
            self._finish_reveal(analysis.cell_id, token)
        self._stats()

    def _explanation(self, analysis):
        clues = {c.clue_id: c for c in self.screen.clue_panel.clues}
        statements = [clues[cid].text for cid in analysis.evidence.clue_ids if cid in clues]
        cells = analysis.evidence.cell_ids
        source = " ".join(statements)
        if cells:
            source += f" Kết hợp các ô đã chứng minh: {', '.join(cells)}."
        status = "tội phạm" if analysis.classification.verdict is Verdict.CRIMINAL else "vô tội"
        name = self.session.engine.get_character(analysis.cell_id).name
        return f"{source.strip()} Vì vậy {name} ({analysis.cell_id}) bắt buộc là {status}; giả thiết ngược lại không thỏa mãn các chứng cứ này."

    def _finish_reveal(self, cell_id, token):
        if self._pending is None or token != self._pending[0]:
            return
        _, board, hint = self._pending
        self._pending = None
        self.screen.set_board(board)
        self.screen.focus_evidence(self._last_analysis.evidence.clue_ids,
                                   (*self._last_analysis.evidence.cell_ids, cell_id))
        if hint:
            self.screen.show_hint(hint)
        self._ready()
        if self.session.engine.is_solved():
            self.state.is_auto_solving = False
            self.screen.action_bar.set_auto_solving(False)
            self._notice(ActionCode.ACCEPTED, "Đã phá án! Mọi ô đều được chứng minh bằng suy luận.")
        elif self.state.is_auto_solving:
            # The reveal lasts 380 ms; a short reading beat yields ~450 ms/step
            # plus actual solver time, without blocking the Qt event loop.
            elapsed = int((perf_counter() - self._reveal_started) * 1000)
            self._timer.start(max(1, self._auto_interval_ms - elapsed))

    def inspect_contradiction(self):
        self.screen.focus_evidence(self._evidence.clue_ids, self._evidence.cell_ids)

    def _stats(self):
        if self.session:
            engine = self.session.engine
            self.screen.action_bar.set_session_stats(len(engine.get_proved_verdicts()), engine.grid_size ** 2,
                                                     self.state.hint_count, self.state.mistake_count, self._steps)

    def _ready(self):
        if self.session:
            self.screen.set_game_status(GameState.SOLVED if self.session.engine.is_solved() else GameState.READY)
            if self.state.is_auto_solving:
                self.screen.set_board_interactive(False)
            self._stats()

    def _notice(self, code, message, cell_id=None):
        self.window.show_notification(ActionResult(code, message, cell_id=cell_id))
