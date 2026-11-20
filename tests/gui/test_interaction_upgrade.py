"""Real-solver interaction regressions, including cancellation across Qt jobs."""

from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import Qt

from src.gui.app import build_main_window
from src.controller.gameplay_session import GameplaySession
from src.controller.play_controller import PlayController
from src.gui.view_models import ActionCode, GameState

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def game(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    controller = PlayController(window)
    controller._paths["sample"] = ROOT / "puzzles/sample_3x3.json"
    window.show()
    controller.load("sample")
    qtbot.waitUntil(lambda: controller.session is not None, timeout=5000)
    yield window.gameplay_screen, controller
    controller.stop()
    controller._pool.waitForDone(5000)


def test_focus_toggle_dim_chips_escape_and_blank_click(qtbot, game):
    screen, _ = game
    screen.set_reduced_motion(True)
    card = screen.clue_panel.clue_cards["CLUE_A1"]
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    assert screen.ui_state.selected_clue_id == "CLUE_A1"
    assert set(screen.game_board.highlighted_cell_ids) == {"A1", "B1"}
    assert screen.game_board.cards_by_id["C3"].opacity() == .42
    assert card._chips.isVisible()
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    assert not screen.game_board.highlighted_cell_ids
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    qtbot.keyClick(card, Qt.Key.Key_Escape)
    assert screen.ui_state.selected_clue_id is None
    assert all(c.opacity() == 1 for c in screen.game_board.cards_by_id.values())
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(screen.clue_panel.scroll_area.widget(), Qt.MouseButton.LeftButton)
    assert screen.ui_state.selected_clue_id is None


def test_used_notes_survive_reveal_and_reset_on_restart(qtbot, game):
    screen, controller = game
    screen.clue_panel.clue_cards["CLUE_A1"].used_button.click()
    assert screen.ui_state.solved_clues == {"CLUE_A1"}
    controller.hint()
    qtbot.waitUntil(lambda: controller._pending is None and not controller._busy, timeout=5000)
    assert screen.clue_panel.clue_cards["CLUE_A1"].text_label.font().strikeOut()
    controller.restart()
    qtbot.waitUntil(lambda: "CLUE_A1" in screen.clue_panel.clue_cards, timeout=5000)
    assert not screen.ui_state.solved_clues
    assert not screen.clue_panel.clue_cards["CLUE_A1"].used_button.isChecked()


def test_hint_reveals_only_forced_step_with_verified_source(qtbot, game):
    screen, controller = game
    controller.hint()
    qtbot.waitUntil(lambda: controller._pending is None and not controller._busy, timeout=5000)
    assert set(controller.session.engine.get_proved_verdicts()) == {"A1", "B1"}
    assert screen.game_board.cards_by_id["B1"].is_revealed
    assert screen.ui_state.hint_count == 1
    assert screen.ui_state.active_hint.source_clue_ids == ("CLUE_A1",)
    assert "bắt buộc" in screen.ui_state.active_hint.text
    assert screen.clue_panel.selected_clue_id == "CLUE_A1"
    assert "Gợi ý 1" in screen.action_bar.status_label.text()
    screen.deduction_panel.hint_box._dismiss_btn.click()
    assert screen.ui_state.active_hint is None


def test_unknown_and_contradicted_never_reveal_and_inspect_real_evidence(qtbot, game):
    screen, controller = game
    controller.guess("C3", "CRIMINAL")
    qtbot.waitUntil(lambda: not controller._busy, timeout=5000)
    assert screen.notification_banner.current_result.code is ActionCode.NOT_PROVABLE
    assert screen._feedback_dialog.isVisible()
    assert screen._feedback_dialog.panel.property("tone") == "warning"
    assert not screen.notification_banner.inspect_button.isVisible()
    assert "Cả hai khả năng" in screen.notification_banner.current_result.message
    controller.guess("B1", "INNOCENT")
    qtbot.waitUntil(lambda: not controller._busy, timeout=5000)
    assert screen.notification_banner.current_result.code is ActionCode.CONTRADICTED
    qtbot.waitUntil(screen._feedback_dialog.isVisible, timeout=1000)
    assert screen._feedback_dialog.panel.property("tone") == "danger"
    assert screen.notification_banner.inspect_button.isVisible()
    screen.notification_banner.inspect_button.click()
    assert screen.ui_state.selected_clue_id == "CLUE_A1"
    assert "B1" in screen.game_board.highlighted_cell_ids
    assert set(controller.session.engine.get_proved_verdicts()) == {"A1"}
    assert screen.ui_state.mistake_count == 2
    screen.set_selection("C3")
    screen._on_board_card_selected("C3")
    assert screen.notification_banner.current_result is None


def test_restart_inline_confirmation_and_counters(qtbot, game):
    screen, controller = game
    for _ in range(2):
        controller.hint()
        qtbot.waitUntil(lambda: not controller._busy and controller._pending is None, timeout=5000)
    before = controller.session.engine.public_kb_version
    screen.action_bar.restart_button.click()
    assert screen._restart_dialog.isVisible()
    assert controller.session.engine.public_kb_version == before
    screen._restart_dialog.cancel_button.click()
    qtbot.waitUntil(lambda: not screen._restart_dialog.isVisible(), timeout=1000)
    screen.action_bar.restart_button.click()
    screen._restart_dialog.confirm_button.click()
    qtbot.waitUntil(lambda: controller.session.engine.public_kb_version > before, timeout=1000)
    qtbot.waitUntil(lambda: "CLUE_A1" in screen.clue_panel.clue_cards, timeout=5000)
    assert controller.session.engine.public_kb_version > before
    assert len(controller.session.engine.get_proved_verdicts()) == 1
    assert screen.ui_state.hint_count == screen.ui_state.mistake_count == 0


def test_pause_discards_inflight_analysis_and_unlocks_manual_play(qtbot, game, monkeypatch):
    screen, controller = game
    gate = Event()
    original = controller.session.analyze

    def slow():
        gate.wait(3)
        return original()

    monkeypatch.setattr(controller.session, "analyze", slow)
    controller.toggle_auto()
    assert screen.ui_state.is_auto_solving
    assert screen.action_bar.auto_solve_button.isEnabled()
    assert not screen.action_bar.criminal_button.isEnabled()
    assert not screen.game_board.is_interactive
    controller.toggle_auto()
    assert not screen.ui_state.is_auto_solving
    assert screen.game_board.is_interactive
    gate.set()
    qtbot.waitUntil(lambda: controller._pool.activeThreadCount() == 0, timeout=5000)
    qtbot.wait(30)
    assert len(controller.session.engine.get_proved_verdicts()) == 1
    assert not screen.game_board.is_animating


def test_auto_completes_and_pause_during_flip_keeps_accepted_progress(qtbot, game):
    screen, controller = game
    controller.toggle_auto()
    qtbot.waitUntil(lambda: controller._pending is not None, timeout=5000)
    controller.toggle_auto()
    assert len(controller.session.engine.get_proved_verdicts()) == 2
    assert screen.game_board.cards_by_id["B1"].is_revealed
    assert not screen.game_board.is_animating
    controller.toggle_auto()
    qtbot.waitUntil(controller.session.engine.is_solved, timeout=10000)
    qtbot.waitUntil(lambda: controller._pending is None, timeout=5000)
    assert screen.game_state is GameState.SOLVED
    assert not screen.ui_state.is_auto_solving
    assert screen.ui_state.hint_count == 0


def test_auto_speed_control_updates_running_timer(qtbot, game):
    screen, controller = game
    screen.action_bar.speed_slider.setValue(900)
    assert controller._auto_interval_ms == 900
    assert "0.90" in screen.action_bar.speed_value_label.text()
    controller.toggle_auto()
    qtbot.waitUntil(lambda: controller._pending is not None, timeout=5000)
    assert screen.game_board._hint_flow is not None
    controller.toggle_auto()


def test_load_cancels_inflight_hint_and_cleans_all_ui_state(qtbot, game, monkeypatch):
    screen, controller = game
    screen.clue_panel.clue_cards["CLUE_A1"].used_button.click()
    gate = Event()
    original = controller.session.analyze

    def slow():
        gate.wait(3)
        return original()

    monkeypatch.setattr(controller.session, "analyze", slow)
    controller.hint()
    old = controller.session
    controller._paths["other"] = ROOT / "puzzles/4x4_01.json"
    controller.load("other")
    gate.set()
    qtbot.waitUntil(lambda: controller.session is not old, timeout=5000)
    assert screen.game_board.grid_size == 4
    assert screen.ui_state.hint_count == 0
    assert not screen.ui_state.solved_clues
    assert not screen.ui_state.highlighted_targets
    assert screen.ui_state.error_feedback is None
    assert screen.ui_state.active_hint is None


def test_projection_and_proofs_for_every_official_puzzle():
    import json
    entries = json.loads((ROOT / "puzzles/manifest.json").read_text())["puzzles"]
    for entry in entries:
        session = GameplaySession(ROOT / "puzzles" / entry["file"])
        while not session.engine.is_solved():
            board = session.board()
            assert all(c.owner_id in session.engine.get_proved_verdicts() for c in board.clues)
            analysis = session.analyze()
            assert analysis.classification is not None, entry["puzzle_id"]
            proof = analysis.classification.to_engine_result(analysis.cell_id, analysis.version)
            from src.core.game_engine import VerdictResponse
            response, _ = session.engine.submit_verdict(analysis.cell_id, proof.status.value == "CRIMINAL", proof)
            assert response is VerdictResponse.ACCEPTED
        assert len(session.board().clues) == session.engine.grid_size ** 2
