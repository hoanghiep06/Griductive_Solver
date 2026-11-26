"""Exercise actual spotlight hit testing, lifecycle and main-game isolation."""

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QEventPoint, QInputDevice, QTouchEvent
from PySide6.QtWidgets import QApplication

from src.controller.gameplay_session import GameplaySession
from src.controller.play_controller import PlayController
from src.gui.app import build_main_window
from src.gui.navigation.screen_router import ScreenId
from src.gui.tutorial_dialog import TutorialDialog
from src.gui.view_models import GameState
from src.tutorial.data import TUTORIAL_STEPS


@pytest.fixture
def tutorial(qtbot):
    view = TutorialDialog(reduced_motion=True)
    qtbot.addWidget(view)
    view.resize(1100, 760)
    view.show()
    qtbot.waitExposed(view)
    qtbot.waitUntil(lambda: view.overlay.panel.geometry().height() > 200)
    return view


def first_move(view):
    view.overlay.next_button.click()
    view.overlay.next_button.click()
    assert view.controller.model.step.target == "B1"


def tap_cell(qtbot, view, cell_id):
    qtbot.mouseClick(view.overlay, Qt.MouseButton.LeftButton, pos=view.cell_rect(cell_id).center().toPoint())


def tap_verdict(qtbot, view, verdict):
    button = view.criminal_button if verdict == "CRIMINAL" else view.innocent_button
    qtbot.mouseClick(view.overlay, Qt.MouseButton.LeftButton, pos=view.widget_rect(button).center().toPoint())


def test_required_move_blocks_advance_and_wrong_actions(tutorial, qtbot):
    view = tutorial
    first_move(view)
    model = view.controller.model
    assert not view.overlay.next_button.isEnabled()
    tap_cell(qtbot, view, "C1")
    qtbot.mouseClick(view.overlay, Qt.MouseButton.LeftButton, pos=QPoint(3, 3))
    view.controller.advance()
    assert model.index == 2 and not view.selected
    assert not view.criminal_button.isEnabled()
    tap_verdict(qtbot, view, "CRIMINAL")
    assert set(model.game.engine.get_proved_verdicts()) == {"A1"}
    tap_cell(qtbot, view, "B1")
    assert view.board.selected_cell_id == "B1"
    assert view.criminal_button.isEnabled()
    before = model.game.engine.public_kb_version
    tap_verdict(qtbot, view, "INNOCENT")
    assert "Chưa đúng" in view.overlay.feedback_label.text()
    assert model.game.engine.public_kb_version == before
    tap_verdict(qtbot, view, "CRIMINAL")
    assert not view.overlay.next_button.isEnabled()  # Wait for animation, even with reduced motion.
    qtbot.waitUntil(lambda: view.controller._pending is None)
    assert view.board.cards_by_id["B1"].is_revealed
    assert view.overlay.next_button.isEnabled()
    view.overlay.next_button.click()
    assert model.step.target == "C1"
    assert view.clues.clues[0].clue_id == "t_B1"


def test_full_walkthrough_uses_real_clicks_and_returns_completion(tutorial, qtbot):
    view = tutorial
    first_move(view)
    model = view.controller.model
    while model.step.target:
        step = model.step
        assert view.clues.clues[0].clue_id == step.clue_id
        tap_cell(qtbot, view, step.target)
        tap_verdict(qtbot, view, step.verdict)
        qtbot.waitUntil(lambda: view.controller._pending is None)
        assert step.target in model.game.engine.get_proved_verdicts()
        view.overlay.next_button.click()
    assert model.index == len(TUTORIAL_STEPS) - 1
    assert model.game.engine.is_solved()
    assert "16/16" in view.board_caption.text()
    assert view.overlay.next_button.text() == "Hoàn thành ✓"
    view.overlay.next_button.click()
    assert view.result() == TutorialDialog.DialogCode.Accepted
    assert not view.overlay._timer.isActive()


@pytest.mark.parametrize("size", [(760, 560), (960, 640), (1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
def test_live_spotlight_mapping_survives_resize_and_window_move(tutorial, qtbot, size):
    view = tutorial
    first_move(view)
    view.resize(*size)
    view.move(73, 61)
    qtbot.waitUntil(lambda: view.overlay.geometry() == view.rect())
    qtbot.wait(30)  # Let the layout's queued refresh settle in reduced-motion mode.
    rect = view.cell_rect("B1")
    card = view.board.cards_by_id["B1"]
    center = view.board.mapFromScene(card.mapToScene(card.card_rect().center()))
    expected = view.overlay.mapFromGlobal(view.board.viewport().mapToGlobal(center))
    assert (rect.center() - expected).manhattanLength() <= 2
    assert view.overlay.rect().contains(rect.toRect())
    assert view.overlay.rect().contains(view.overlay.panel.geometry())
    assert view.overlay.rect().contains(view.overlay.skip_button.geometry())
    assert not view.overlay.panel.geometry().intersects(rect.toRect())
    assert view.overlay.panel.geometry().bottom() < view.widget_rect(view.criminal_button).top()
    tap_cell(qtbot, view, "B1")
    assert view.selected
    _, actions, pointer = view.target_geometry()
    assert pointer == view.widget_rect(view.criminal_button)
    assert any(k == "verdict:INNOCENT" for k, _ in actions)
    assert all(view.board.cards_by_id[cid].has_portrait for cid in view.board.cards_by_id)


def test_menu_and_gameplay_entry_preserve_main_session_and_allow_replay(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    controller = PlayController(window)
    controller.session = GameplaySession("puzzles/sample_3x3.json")
    controller._reset_screen()
    window.set_reduced_motion(True)
    window.show()
    controller.guess("B1", "CRIMINAL")
    qtbot.waitUntil(lambda: not controller._busy and controller._pending is None)
    window.set_selection("C1")
    controller.state.hint_count = 2
    controller.state.mistake_count = 1
    session = controller.session
    before = session.board()
    steps = controller._steps
    selected = controller.screen.game_board.selected_cell_id
    window.gameplay_screen.tutorial_button.click()
    dialog = window._active_tutorial
    assert dialog is not None and dialog.isModal()
    assert dialog.controller.model.game.session_id != session.session_id
    first_move(dialog)
    dialog.overlay.select_button.click()
    dialog.criminal_button.click()
    qtbot.waitUntil(lambda: dialog.controller._pending is None)
    dialog.overlay.skip_button.click()
    assert window._active_tutorial is None
    assert window.current_screen is ScreenId.GAMEPLAY
    assert controller.session is session
    assert session.board() == before
    assert controller._steps == steps
    assert controller.state.hint_count == 2 and controller.state.mistake_count == 1
    assert controller.screen.game_board.selected_cell_id == selected
    assert controller.screen.game_state is GameState.READY
    assert controller._tutorial_started_at is None
    window.gameplay_screen.tutorial_button.click()
    qtbot.keyClick(window._active_tutorial.overlay, Qt.Key.Key_Escape)
    assert window._active_tutorial is None
    assert controller.session is session and session.board() == before
    # Start from the main menu, then Escape: the previous screen is retained.
    window.show_main_menu()
    window.main_menu_screen.tutorial_button.click()
    replay = window._active_tutorial
    assert replay.controller.model.index == 0
    assert set(replay.controller.model.game.engine.get_proved_verdicts()) == {"A1"}
    qtbot.keyClick(replay.overlay, Qt.Key.Key_Escape)
    assert window._active_tutorial is None
    assert window.current_screen is ScreenId.MAIN_MENU
    window.close()


def test_skip_during_reveal_cancels_queued_callbacks(tutorial, qtbot):
    view = tutorial
    view.set_reduced_motion(False)
    first_move(view)
    tap_cell(qtbot, view, "B1")
    tap_verdict(qtbot, view, "CRIMINAL")
    assert view.controller._pending is not None
    view.overlay.skip_button.click()
    assert view.controller._pending is None
    assert view.controller._closed
    assert not view.board.is_animating
    assert not view.overlay._timer.isActive()
    view.controller._finish_reveal("B1", ("stale", 2))
    assert view.controller.model.index == 2


def test_keyboard_navigation_and_reduced_motion_toggle(tutorial, qtbot):
    view = tutorial
    qtbot.keyClick(view.overlay, Qt.Key.Key_Space)
    qtbot.keyClick(view.overlay, Qt.Key.Key_Return)
    assert view.controller.model.index == 2
    qtbot.keyClick(view.overlay, Qt.Key.Key_Space)
    assert view.selected
    view.set_reduced_motion(False)
    assert view.overlay._timer.isActive()
    view.set_reduced_motion(True)
    assert not view.overlay._timer.isActive()
    assert view.board.reduced_motion


def test_start_tutorial_during_main_flip_keeps_accepted_main_transaction(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    controller = PlayController(window)
    controller.session = GameplaySession("puzzles/sample_3x3.json")
    controller._reset_screen()
    window.show()
    controller.guess("B1", "CRIMINAL")
    qtbot.waitUntil(lambda: controller._pending is not None)
    old_token = controller._pending[0]
    window.gameplay_screen.tutorial_button.click()
    assert controller._pending is None
    assert not controller._busy and not controller._timer.isActive()
    assert controller.screen.game_board.cards_by_id["B1"].is_revealed
    assert set(controller.session.engine.get_proved_verdicts()) == {"A1", "B1"}
    controller._finish_reveal("B1", old_token)
    assert window._active_tutorial.controller.model.index == 0
    window._active_tutorial.reject()
    assert controller.screen.game_state is GameState.READY
    window.close()


def test_touch_selects_target_and_submits_verdict(tutorial, qtbot):
    view = tutorial
    first_move(view)
    device = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)

    def touch(rect):
        # Qt Windows may ignore synthetic platform touchscreen devices. Deliver
        # real Qt touch events directly so this handler check is platform-neutral.
        pos = rect.center()
        global_pos = QPointF(view.overlay.mapToGlobal(pos.toPoint()))
        for kind, state in ((QEvent.Type.TouchBegin, QEventPoint.State.Pressed),
                            (QEvent.Type.TouchEnd, QEventPoint.State.Released)):
            point = QEventPoint(0, state, pos, global_pos)
            event = QTouchEvent(kind, device, touchPoints=[point])
            QApplication.sendEvent(view.overlay, event)

    touch(view.cell_rect("B1"))
    qtbot.waitUntil(lambda: view.selected)
    touch(view.widget_rect(view.criminal_button))
    qtbot.waitUntil(lambda: view.controller._pending is None and view.controller.model.can_advance)
    assert view.controller.model.index == 2
    assert view.board.cards_by_id["B1"].is_revealed
