"""Clue strips under cards, spent-clue collapsing, and Nháp (scratchpad + draft marks)."""

from __future__ import annotations

from src.gui.app import build_main_window
from src.gui.demo_fixtures import build_demo_3x3_snapshot
from src.gui.view_models import GameState, PublicClueView


def _screen(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    window.show_gameplay(build_demo_3x3_snapshot())
    window.set_busy(GameState.READY)
    return window.gameplay_screen


def test_clue_strip_lives_under_revealed_card_and_collapses_when_spent(qtbot):
    gs = _screen(qtbot)
    # A1 is revealed, C1 is hidden in the 3x3 demo snapshot.
    gs.set_clues([PublicClueView("CLUE_A1", "A1", "FACT", "C1 là vô tội.", referenced_cells=("C1",))])
    card = gs.game_board.cards_by_id["A1"]
    assert card.clue_note is not None
    assert card.clue_note.state == "normal"  # C1 still hidden -> still useful

    # Every referenced cell already revealed -> spent (collapsed chip)
    gs.set_clues([PublicClueView("CLUE_A1", "A1", "FACT", "A1 là vô tội.", referenced_cells=("A1",))])
    assert card.clue_note.state == "spent"

    # "Hiện tất cả manh mối" re-expands it
    gs.set_show_all_clues(True)
    assert card.clue_note.state == "normal"


def test_clicking_clue_strip_focuses_and_second_click_releases(qtbot):
    gs = _screen(qtbot)
    gs.set_clues([PublicClueView("CLUE_A1", "A1", "FACT", "C1 là vô tội.", referenced_cells=("C1",))])
    card = gs.game_board.cards_by_id["A1"]

    card.clue_clicked.emit("CLUE_A1")
    assert gs.ui_state.selected_clue_id == "CLUE_A1"
    assert card.clue_note.selected is True

    card.clue_clicked.emit("CLUE_A1")
    assert gs.ui_state.selected_clue_id is None
    assert card.clue_note.selected is False


def test_double_click_marks_clue_used_and_collapses_it(qtbot):
    gs = _screen(qtbot)
    gs.set_clues([PublicClueView("CLUE_A1", "A1", "FACT", "C1 là vô tội.", referenced_cells=("C1",))])
    card = gs.game_board.cards_by_id["A1"]
    card.clue_used_toggled.emit("CLUE_A1")
    assert card.clue_note.state == "spent"
    card.clue_used_toggled.emit("CLUE_A1")
    assert card.clue_note.state == "normal"


def test_draft_marks_cycle_only_on_hidden_cards_and_reset_with_case(qtbot):
    gs = _screen(qtbot)
    board = gs.game_board
    hidden, revealed = board.cards_by_id["C1"], board.cards_by_id["A1"]

    hidden.cycle_draft_mark()
    assert board.draft_marks == {"C1": "?"}
    hidden.cycle_draft_mark()
    hidden.cycle_draft_mark()
    assert board.draft_marks == {"C1": "INNOCENT"}
    hidden.cycle_draft_mark()
    assert board.draft_marks == {}

    revealed.cycle_draft_mark()  # revealed cards never carry a draft mark
    assert "A1" not in board.draft_marks

    hidden.cycle_draft_mark()
    gs.scratchpad_panel.set_text("C1 có vẻ đáng ngờ")
    gs.reset_for_new_case(build_demo_3x3_snapshot())
    assert gs.scratchpad_panel.text() == ""
    assert gs.game_board.draft_marks == {}