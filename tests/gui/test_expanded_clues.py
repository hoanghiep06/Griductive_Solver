"""Production public projection, pinned totals and transient scope previews."""

from dataclasses import replace

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from src.agent.entailment import EntailmentChecker, Verdict
from src.controller.gameplay_session import GameplaySession
from src.core.game_engine import VerdictResponse
from src.gui.screens.gameplay_screen import GameplayScreen
from src.gui.view_models import GameState, PublicClueView
from src.solvers.dpll import DPLLSolver
from tools.validate_puzzles import ROOT, prove_progressive
from src.core.puzzle_loader import PuzzleLoader


def session_after_reveals(pid):
    """Replay the certificate using real engine transactions, never fake proofs."""
    path = ROOT / f"puzzles/{pid}.json"
    session = GameplaySession(path)
    trace = prove_progressive(PuzzleLoader().load(path))
    for step in trace:
        snapshot = session.engine.get_public_snapshot()
        encoder = session._encoder()
        cnf = encoder.encode_public_kb(snapshot).clauses
        result = EntailmentChecker(DPLLSolver(), variable_map=encoder.var_map).classify(
            cnf, encoder.var_map.get_var(step["character_id"]),
        )
        response, _ = session.engine.submit_verdict(
            step["character_id"], result.verdict is Verdict.CRIMINAL,
            result.to_engine_result(step["character_id"], snapshot.version),
        )
        assert response is VerdictResponse.ACCEPTED
        session.board()  # Every newly revealed kind must project without an exception.
    return session


def test_real_projection_of_profession_global_and_conditional_rules():
    groups = session_after_reveals("5x5_03")
    profession = next(c for c in groups.board().clues if c.scope == "PROFESSION")
    assert profession.scope_label
    raw = next(c for c in groups.engine.get_revealed_clues() if c.clue_id == profession.clue_id)
    expected = {c.id for c in groups.engine.characters if c.profession.casefold() == raw.parameters["profession"].casefold()}
    assert set(profession.referenced_cells) == expected
    conditionals = session_after_reveals("4x4_05")
    clue = next(c for c in conditionals.board().clues if c.clue_type == "IMPLIES")
    assert clue.text.startswith("Nếu ") and " thì " in clue.text
    assert len(clue.primary_cells) == len(clue.secondary_cells) == 1
    assert clue.referenced_cells == clue.primary_cells + clue.secondary_cells


def test_pinned_global_card_uses_only_revealed_counts_and_survives_scroll(qtbot):
    session = GameplaySession(ROOT / "puzzles/4x4_02.json")
    screen = GameplayScreen(demo_mode=False)
    qtbot.addWidget(screen)
    screen.set_reduced_motion(True)
    screen.resize(960, 640)
    screen.set_board(session.board())
    screen.set_game_status(GameState.READY)
    screen.show()
    card = screen.clue_panel.global_card
    assert card.isVisible()
    assert "Toàn bộ bàn cờ" in card.text_label.text()
    known = session.engine.get_proved_verdicts()
    assert f"{sum(known.values())} tội phạm" in card.count_label.text()
    assert f"{16 - len(known)} chưa rõ" in card.count_label.text()
    screen.clue_panel.scroll_area.verticalScrollBar().setValue(10000)
    assert card.isVisible()
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    assert set(screen.game_board.highlighted_cell_ids) == set(screen.game_board.cards_by_id)
    assert screen.ui_state.selected_clue_id == card._clue_id
    assert screen.game_board._rule_fx._items  # Global rule effects are actually connected.
    screen.set_game_status(GameState.PROCESSING)
    before = screen.ui_state.selected_clue_id
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    assert screen.ui_state.selected_clue_id == before


def test_hover_previews_scope_and_restores_persistent_selection(qtbot):
    session = GameplaySession(ROOT / "puzzles/4x4_02.json")
    screen = GameplayScreen(demo_mode=False)
    qtbot.addWidget(screen)
    screen.set_reduced_motion(True)
    screen.resize(1100, 760)
    screen.set_board(session.board())
    screen.set_game_status(GameState.READY)
    screen.show()
    local = next(c for c in screen.clue_panel.clues if c.scope != "ALL")
    screen.clue_panel._on_card_clicked(local.clue_id)
    selected = screen.ui_state.selected_clue_id
    original_targets = screen.game_board.highlighted_cell_ids
    global_card = screen.clue_panel.global_card
    QApplication.sendEvent(global_card, QEvent(QEvent.Type.Enter))
    assert set(screen.game_board.highlighted_cell_ids) == set(screen.game_board.cards_by_id)
    assert screen.ui_state.selected_clue_id == selected
    QApplication.sendEvent(global_card, QEvent(QEvent.Type.Leave))
    assert screen.ui_state.selected_clue_id == selected
    assert screen.game_board.highlighted_cell_ids == original_targets
    assert session.board().kb_version == session.engine.public_kb_version


def test_compare_keeps_shared_cell_in_both_visual_groups(qtbot):
    session = GameplaySession(ROOT / "puzzles/3x3_01.json")
    snapshot = session.board()
    owner = next(c.cell_id for c in snapshot.characters if c.is_revealed)
    clue = PublicClueView("overlap", owner, "COUNT_COMPARE", "Hàng 1 > cột C",
                          ("A1", "B1", "C1", "C2", "C3"),
                          ("A1", "B1", "C1"), ("C1", "C2", "C3"), scope_label=">")
    screen = GameplayScreen(demo_mode=False)
    qtbot.addWidget(screen)
    screen.set_reduced_motion(True)
    screen.set_board(replace(snapshot, clues=(clue,)))
    screen._on_clue_selected(clue.clue_id)
    labels = [getattr(item, "_text", "") for item in screen.game_board._rule_fx._items]
    assert "NHÓM A · 3 Ô" in labels
    assert "NHÓM B · 3 Ô" in labels
    assert {"A1", "B1", "C1", "C2", "C3"} <= set(screen.game_board.highlighted_cell_ids)
