"""Automated tests for Animate UI Expressive Motion Tokens & Qt6 Behaviors.

Covers:
    - Animate UI spring physics (SPRING_PRESS, SPRING_POP, SPRING_CHECK_POP,
      SPRING_PROGRESS, SPRING_NUMBER) & tempo scaling invariants
    - Role-based cubic-bezier curves (EASE_OUT, EASE_SOFT, EASE_AWAY) & damped shake
    - CharacterCard tactile press (mouse + keyboard), verdict landing burst,
      hint arrival pulse, contradiction shake + flash, and reduced-motion bypass
    - ProgressPanel spring bar animation + synchronous text preservation
    - CluePanel & DeductionPanel expressive list entrance + reduced motion
    - ResultsScreen Case Closed stamp, finite particles, Counting Number roll-up,
      synchronous metric availability, and reduced-motion instant mode
    - StyledButton tactile press & ScreenRouter reduced-motion safety
    - Strict Presentation-only isolation (zero domain imports in motion_tokens)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.animations import (
    DEFAULT_MOTION,
    EASE_AWAY,
    EASE_OUT,
    EASE_SOFT,
    MotionConfig,
    SCALE_CHOICE,
    SCALE_PRESS,
    SPRING_CHECK_POP,
    SPRING_NUMBER,
    SPRING_POP,
    SPRING_PRESS,
    SPRING_PROGRESS,
    build_easing,
    clamp_tempo,
    damped_shake_keyframes,
    scale_duration_ms,
)
from src.gui.components import (
    CluePanel,
    DeductionPanel,
    ProgressPanel,
    StyledButton,
)
from src.gui.components.interaction_dialog import InteractionDialog
from src.gui.demo_fixtures import (
    build_demo_3x3_snapshot,
    build_demo_results_view,
    build_demo_trace,
)
from src.gui.grid_view import GameBoard
from src.gui.navigation.screen_router import ScreenId, ScreenRouter
from src.gui.screens.results_screen import ResultsScreen
from src.gui.view_models import CardVisibility, PublicCharacterView

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_spring_physics_and_tempo_scaling_laws():
    # Endpoints always land on exact 0.0 and 1.0
    for spec in (SPRING_PRESS, SPRING_POP, SPRING_CHECK_POP, SPRING_PROGRESS, SPRING_NUMBER):
        assert spec.evaluate(0.0) == 0.0
        assert spec.evaluate(1.0) == 1.0
        curve = build_easing(spec)
        assert curve.valueForProgress(0.0) == pytest.approx(0.0, abs=1e-4)
        assert curve.valueForProgress(1.0) == pytest.approx(1.0, abs=1e-4)

    # Underdamped checkPop overshoots naturally (~10-16%)
    samples_pop = [SPRING_CHECK_POP.evaluate(i / 100.0) for i in range(101)]
    assert max(samples_pop) > 1.08

    # Overdamped / critically damped progress & number never overshoot
    samples_prog = [SPRING_PROGRESS.evaluate(i / 100.0) for i in range(101)]
    samples_num = [SPRING_NUMBER.evaluate(i / 100.0) for i in range(101)]
    assert max(samples_prog) <= 1.01
    assert max(samples_num) <= 1.005

    # Tempo law: k / t^2, d / t, duration * t, clamped to [0.5, 2.0]
    assert clamp_tempo(0.1) == 0.5
    assert clamp_tempo(5.0) == 2.0
    slower = SPRING_POP.scaled(1.25)
    assert slower.stiffness == pytest.approx(SPRING_POP.stiffness / (1.25 ** 2))
    assert slower.damping == pytest.approx(SPRING_POP.damping / 1.25)
    assert slower.duration_ms == scale_duration_ms(SPRING_POP.duration_ms, 1.25)

    # Curves & damped shake keyframes
    for bez in (EASE_OUT, EASE_SOFT, EASE_AWAY):
        c = build_easing(bez)
        assert c.valueForProgress(0.0) == pytest.approx(0.0, abs=1e-4)
        assert c.valueForProgress(1.0) == pytest.approx(1.0, abs=1e-4)

    frames = damped_shake_keyframes(4.0)
    assert frames[0] == (0.0, 0.0)
    assert frames[-1] == (1.0, 0.0)
    assert abs(frames[1][1]) > abs(frames[3][1]) > abs(frames[5][1]) > 0.0
    assert SCALE_PRESS == pytest.approx(0.97)
    assert SCALE_CHOICE == pytest.approx(0.985)


def test_character_card_tactile_press_reveal_burst_and_reduced_motion(qtbot):
    board = GameBoard(motion_config=MotionConfig(card_flip_duration=60))
    qtbot.addWidget(board)
    board.set_board(build_demo_3x3_snapshot())
    board.resize(700, 620)
    board.show()
    qtbot.waitExposed(board)

    card = board.cards_by_id["C1"]
    orig_pos = card.pos()

    # Tactile press impulse via keyboard (Rule A2: keyboard animates like pointer)
    card._trigger_press_pulse()
    assert card._press_anim.state() == card._press_anim.State.Running
    qtbot.waitUntil(lambda: card.press_level == 0.0 and card._press_anim.state() == card._press_anim.State.Stopped, timeout=1000)
    assert card.pos() == orig_pos

    # Reveal burst triggers cleanly when 3D flip finishes
    revealed = PublicCharacterView(
        cell_id=card.public_data.cell_id,
        name=card.public_data.name,
        profession=card.public_data.profession,
        row=card.public_data.row,
        col=card.public_data.col,
        visibility=CardVisibility.REVEALED,
        verdict="CRIMINAL",
        has_public_clue=True,
    )
    assert board.reveal_card("C1", revealed, None) is True
    qtbot.waitUntil(lambda: card.is_revealed, timeout=1500)
    assert card.reveal_burst > 0.0 or card._burst_anim.state() == card._burst_anim.State.Running

    # Hint arrival pulse & contradiction shake
    card.trigger_hint_arrival_pulse()
    assert card._hint_pulse_anim.state() == card._hint_pulse_anim.State.Running
    card.shake()
    assert card._shake_anim.state() == card._shake_anim.State.Running
    assert card._error_flash_anim.state() == card._error_flash_anim.State.Running

    # Reduced motion neutralizes all transient motion immediately (Rule A1)
    board.set_reduced_motion(True)
    assert card.press_level == 0.0
    assert card.reveal_burst == 0.0
    assert card.hint_pulse == 0.0
    assert card.error_flash == 0.0
    card.shake()
    assert card._shake_anim.state() == card._shake_anim.State.Stopped


def test_progress_clue_deduction_and_styled_button_expressive_motion(qtbot):
    progress = ProgressPanel()
    qtbot.addWidget(progress)
    progress.show()
    qtbot.waitExposed(progress)
    progress.set_progress(6, 16)
    # Synchronous label/format availability preserved
    assert progress.progress_bar.text() == "37.5%"
    assert "6 / 16" in progress.revealed_label.text()
    qtbot.waitUntil(lambda: progress.progress_bar.value() == 375, timeout=1500)

    progress.set_reduced_motion(True)
    progress.set_progress(12, 16)
    assert progress.progress_bar.value() == 750

    clues = CluePanel()
    qtbot.addWidget(clues)
    clues.show()
    snap = build_demo_3x3_snapshot()
    clues.set_clues(snap.clues[:1])
    clues.set_clues(snap.clues)
    assert len(clues.clues) == len(snap.clues)
    clues.set_reduced_motion(True)
    assert clues._entry_anims == []

    deduction = DeductionPanel()
    qtbot.addWidget(deduction)
    deduction.show()
    demo_steps = list(build_demo_trace(3))[:2]
    for step in demo_steps:
        assert deduction.append_step(step) is True
    assert deduction.step_count == len(demo_steps)
    deduction.set_reduced_motion(True)
    assert deduction._entry_anims == []

    btn = StyledButton("Kiểm tra", variant="primary")
    qtbot.addWidget(btn)
    btn.show()
    qtbot.mousePress(btn, Qt.MouseButton.LeftButton)
    assert btn._press_anim.state() == btn._press_anim.State.Running
    qtbot.mouseRelease(btn, Qt.MouseButton.LeftButton)
    btn.set_reduced_motion(True)
    assert btn.press_level == 0.0


def test_results_screen_expressive_celebration_and_reduced_motion(qtbot):
    screen = ResultsScreen()
    qtbot.addWidget(screen)
    screen.resize(1280, 800)
    screen.show()
    qtbot.waitExposed(screen)

    results = build_demo_results_view(puzzle_id="4x4_03", grid_size=4)
    screen.set_results(results)

    # Synchronous assertions immediately after set_results always hold
    assert screen.value_labels["puzzle_id"].text() == "4x4_03"
    assert screen.value_labels["revealed"].text() == f"{results.revealed} / {results.total}"
    assert screen.value_labels["accepted_steps"].text() == str(results.accepted_steps)

    # Celebration starts cleanly and finishes back at exact rest values
    qtbot.waitUntil(lambda: screen._celebration_group is not None, timeout=1000)
    qtbot.waitUntil(
        lambda: screen._celebration_group is not None
        and screen._celebration_group.state() == screen._celebration_group.State.Stopped,
        timeout=2500,
    )
    assert screen.emblem_view.render_scale == pytest.approx(1.0)
    assert screen.emblem_view.burst_progress == pytest.approx(0.0)
    assert screen.value_labels["accepted_steps"].text() == str(results.accepted_steps)

    # Reduced motion skips celebration completely
    screen.set_reduced_motion(True)
    screen.set_results(results)
    QApplication.processEvents()
    assert screen._celebration_group is None
    assert screen.emblem_view.render_scale == pytest.approx(1.0)


def test_dialog_and_router_reduced_motion_and_zero_domain_imports(qtbot):
    dialog = InteractionDialog()
    qtbot.addWidget(dialog)
    dialog.set_reduced_motion(True)
    dialog.configure(
        tone="info",
        icon="i",
        kicker="TEST",
        title="Reduced Motion",
        message="Instant open/close",
        detail="",
    )
    dialog.show()
    assert dialog.windowOpacity() == pytest.approx(1.0)
    dialog.close_animated()
    assert not dialog.isVisible()

    router = ScreenRouter()
    qtbot.addWidget(router)
    router.set_reduced_motion(True)
    w1 = StyledButton("A")
    w2 = StyledButton("B")
    router.register_screen(ScreenId.MAIN_MENU, w1)
    router.register_screen(ScreenId.ABOUT, w2)
    assert router.navigate_to(ScreenId.ABOUT) is True
    assert router._transition is None

    # Strict architectural isolation: motion_tokens has ZERO domain imports
    src = (REPO_ROOT / "src/gui/animations/motion_tokens.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden = ("src.core", "src.solvers", "src.encoder", "src.agent")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(forbidden)


def test_pinnacle_3d_cursor_tilt_evidence_threads_and_results_bridge(qtbot):
    from PySide6.QtCore import QPointF
    from src.gui.animations.card_flip import build_perspective_3d_transform, compute_flip_frame
    from src.gui.app import build_main_window
    from src.gui.view_models import GameState

    # 1. Dual-axis 3D projective matrix & FlipFrameState pitch arc
    mid_frame = compute_flip_frame(0.5)
    assert mid_frame.pitch_deg < -1.0
    tx_rest = build_perspective_3d_transform(132.0, 176.0, 0.0, 0.0)
    assert tx_rest.isIdentity()
    tx_tilt = build_perspective_3d_transform(132.0, 176.0, 6.0, -5.0)
    assert not tx_tilt.isIdentity()
    assert abs(tx_tilt.m13()) > 0.0 and abs(tx_tilt.m23()) > 0.0

    # 2. CharacterCard 3D magnetic cursor tilt & GameBoard 3D detective thread arcs
    board = GameBoard()
    qtbot.addWidget(board)
    board.resize(760, 620)
    board.show()
    board.set_board(build_demo_3x3_snapshot())

    card = board.cards_by_id["B2"]
    card._update_cursor_tilt(QPointF(140.0, 10.0))
    assert card.tilt_y > 1.0 and card.tilt_x > 1.0

    board.focus_evidence(["A1"], ["B1", "C1"])
    assert len(board._evidence_threads) >= 3

    # Reduced motion clears 3D threads and zeroes cursor tilt
    board.set_reduced_motion(True)
    assert len(board._evidence_threads) == 0
    card._update_cursor_tilt(QPointF(140.0, 10.0))
    assert card.tilt_x == 0.0 and card.tilt_y == 0.0

    # 3. ActionBar reveals "Biên bản khép án →" button when GameState is SOLVED
    win = build_main_window(demo_navigation=False)
    qtbot.addWidget(win)
    win.show()
    win.show_gameplay(build_demo_3x3_snapshot())
    bar = win.gameplay_screen.action_bar
    assert bar.demo_results_button is not None
    assert not bar.demo_results_button.isVisible()
    win.gameplay_screen.set_game_status(GameState.SOLVED)
    assert bar.demo_results_button.isVisible()
    assert bar.demo_results_button.isEnabled()
    win.close()


def test_semantic_clue_role_badges_and_connectors(qtbot):
    from src.gui.grid_view import _RelationBadgeItem

    board = GameBoard()
    qtbot.addWidget(board)
    board.resize(760, 620)
    board.show()
    board.set_board(build_demo_3x3_snapshot())

    # 1. Comparative SAME clue -> distinct NGUỒN / CHÍNH / ĐỐI CHIẾU badges + arched cord + pill
    board.focus_clue_relation(
        owner_id="C2",
        primary_cells=["B3"],
        secondary_cells=["B1"],
        clue_type="SAME",
        relation_label="= CÙNG PHE",
    )
    assert board.cards_by_id["C2"].evidence_role == "source"
    assert board.cards_by_id["C2"].role_badge_text == "NGUỒN"
    assert board.cards_by_id["B3"].evidence_role == "primary"
    assert board.cards_by_id["B3"].role_badge_text == "CHÍNH"
    assert board.cards_by_id["B1"].evidence_role == "secondary"
    assert board.cards_by_id["B1"].role_badge_text == "ĐỐI CHIẾU"
    badges = [item for item in board._evidence_threads if isinstance(item, _RelationBadgeItem)]
    assert len(badges) == 1
    assert badges[0]._text == "= CÙNG PHE"

    # 2. Contiguous row EXACTLY clue -> NGUỒN · CHÍNH + VÙNG XÉT + region box + badge
    board.focus_clue_relation(
        owner_id="A1",
        primary_cells=["A1", "B1", "C1"],
        secondary_cells=[],
        clue_type="EXACTLY",
        relation_label="CHÍNH XÁC",
    )
    assert board.cards_by_id["A1"].evidence_role == "source"
    assert board.cards_by_id["A1"].role_badge_text == "NGUỒN · CHÍNH"
    assert board.cards_by_id["B1"].evidence_role == "primary"
    assert board.cards_by_id["B1"].role_badge_text == "VÙNG XÉT"
    badges = [item for item in board._evidence_threads if isinstance(item, _RelationBadgeItem)]
    assert len(badges) == 1
    assert badges[0]._text == "CHÍNH XÁC"

    # 3. Clean teardown removes all pills, roles & connectors
    board.clear_highlights()
    assert len(board._evidence_threads) == 0
    for cid in ("A1", "B1", "B3", "C1", "C2"):
        assert board.cards_by_id[cid].role_badge_text == ""
        assert board.cards_by_id[cid].evidence_role == "reference"


def test_global_stardust_overlay_shooting_stars_and_reduced_motion(qtbot):
    from PySide6.QtCore import QPointF, Qt
    from src.gui.app import build_main_window

    win = build_main_window(demo_navigation=False)
    qtbot.addWidget(win)
    win.resize(1366, 768)
    win.show()

    overlay = win.stardust_overlay
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert overlay.width() == win.centralWidget().width()
    assert overlay.height() == win.centralWidget().height()

    overlay.trigger_shooting_star()
    assert overlay.active_meteor_count == 1

    overlay.set_cursor_preview(QPointF(680.0, 360.0), spawn_trail=True)
    assert overlay.active_mist_puff_count >= 1

    win.set_reduced_motion(True)
    assert overlay.reduced_motion is True
    assert overlay.active_meteor_count == 0
    assert overlay.active_mist_puff_count == 0
    assert not overlay.isVisible()
    win.close()
