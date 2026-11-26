"""Readable public clues without changing the investigation or personal notes."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QPoint, Qt

from src.controller.gameplay_session import GameplaySession
from src.gui.app import build_main_window
from src.gui.demo_fixtures import build_demo_3x3_snapshot, build_demo_hint, build_demo_trace
from src.gui.view_models import GameState


@pytest.fixture
def desk(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    session = GameplaySession("puzzles/4x4_02.json")
    window.set_reduced_motion(True)
    window.resize(1280, 720)
    window.show_gameplay(session.board())
    window.set_game_status(GameState.READY)
    window.show()
    qtbot.waitExposed(window)
    return window, session


def test_full_clue_reader_tracks_hover_and_restores_pinned_clue(desk):
    window, session = desk
    screen = window.gameplay_screen
    public = session.board().clues
    first, second = public[:2]
    screen.scratchpad_panel.set_text("Giữ ghi chú cá nhân")
    before = session.board()
    screen.game_board.cards_by_id[first.owner_id].clue_clicked.emit(first.clue_id)
    assert screen.clue_reader.clues == (first,)
    screen.game_board.cards_by_id[second.owner_id].clue_hovered.emit(second.clue_id)
    assert screen.clue_reader.body_label.text() == second.text
    assert screen.ui_state.selected_clue_id == first.clue_id
    screen.game_board.cards_by_id[second.owner_id].clue_hover_left.emit(second.clue_id)
    assert screen.clue_reader.body_label.text() == first.text
    assert screen.scratchpad_panel.text() == "Giữ ghi chú cá nhân"
    assert session.board() == before


def test_long_public_clue_is_not_truncated_in_reading_surface(desk, qtbot):
    window, session = desk
    screen = window.gameplay_screen
    clue = session.board().clues[0]
    long_clue = replace(clue, text="Quan sát các ô đã được chứng minh để suy luận. " * 35)
    screen.set_clues((long_clue,))
    assert screen.clue_reader.body_label.text() == long_clue.text
    qtbot.waitUntil(lambda: screen.clue_reader.scroll_area.verticalScrollBar().maximum() > 0)
    screen.set_clues(())
    assert not screen.clue_reader.clues
    assert "Di chuột" in screen.clue_reader.body_label.text()


def test_notes_and_draft_marks_survive_tab_changes_but_reset_for_new_case(desk):
    window, _ = desk
    screen = window.gameplay_screen
    hidden = next(card for card in screen.game_board.cards_by_id.values() if not card.is_revealed)
    hidden.cycle_draft_mark()
    screen.scratchpad_panel.set_text("Đối chiếu hai nhóm trước khi kết luận")
    trace = build_demo_trace(3)
    assert screen.append_deduction_step(trace[0])
    assert screen._sidebar_tabs.currentWidget() is screen.deduction_panel
    screen._sidebar_tabs.setCurrentWidget(screen.scratchpad_panel)
    assert screen.scratchpad_panel.text() == "Đối chiếu hai nhóm trước khi kết luận"
    assert hidden.cell_id in screen.game_board.draft_marks
    screen.show_hint(build_demo_hint(cell_id=hidden.cell_id))
    assert screen._sidebar_tabs.currentWidget() is screen.deduction_panel
    screen.reset_for_new_case(build_demo_3x3_snapshot())
    assert not screen.scratchpad_panel.text()
    assert not screen.game_board.draft_marks
    assert screen._sidebar_tabs.currentWidget() is screen.scratchpad_panel


@pytest.mark.parametrize("size", [(960, 640), (1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
def test_reading_surface_and_tabs_fit_the_supported_window(desk, qtbot, size):
    window, _ = desk
    window.resize(*size)
    screen = window.gameplay_screen
    qtbot.wait(30)
    reader = screen.clue_reader
    origin = window.mapFromGlobal(reader.mapToGlobal(QPoint()))
    assert origin.x() >= 0 and origin.y() >= 0
    assert origin.x() + reader.width() <= window.width()
    assert origin.y() + reader.height() <= window.height()
    assert reader.width() >= 270
    assert screen._sidebar_tabs.tabBar().isVisible()
    header, plaque = screen._top_bar, screen._brand_plaque
    if plaque.isVisible():
        center = plaque.mapTo(header, plaque.rect().center()).x()
        assert abs(center - header.width() / 2) <= 2
        title_right = screen._case_label.mapTo(header, QPoint()).x() + screen._case_label.width()
        assert title_right < plaque.x()
        assert plaque.geometry().right() < header.right.geometry().left()
    else:
        required = 2 * header.controls.sizeHint().width() + plaque.width() + 24
        margins = header.layout().contentsMargins()
        assert header.width() < max(1450, required + margins.left() + margins.right())
    board = screen.game_board
    last = board.cards_by_id["D4"]
    mapped = board.mapFromScene(last.mapRectToScene(last.card_rect())).boundingRect()
    assert board.viewport().rect().contains(mapped)


def test_tutorial_uses_the_same_clue_reader_and_under_card_notes(desk, qtbot):
    window, session = desk
    before = session.board()
    window.show_tutorial()
    dialog = window._active_tutorial
    dialog.controller.advance()
    dialog.controller.advance()
    qtbot.wait(20)
    assert type(dialog.clues) is type(window.gameplay_screen.clue_reader)
    step = dialog.controller.model.step
    source = dialog.clues.clues[0]
    note = dialog.board.cards_by_id[source.owner_id].clue_note
    assert note.clue_id == step.clue_id and note.selected
    assert dialog.note_rect(source.owner_id).isValid()
    highlights, _, _ = dialog.target_geometry()
    assert dialog.note_rect(source.owner_id) in highlights
    assert dialog.clues.body_label.text() == note.text
    qtbot.keyClick(dialog.overlay, Qt.Key.Key_Escape)
    assert window._active_tutorial is None
    assert session.board() == before
