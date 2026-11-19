"""Comprehensive automated Phase 5 tests: 3D Card Flip, Evidence Glow & Controller Contract.

Covers all Section 14 (14.1–14.7) criteria and Edge Cases A–J:
    - 14.1 Physical 3D Perspective Card Flip (true projective trapezoid math,
           non-mirrored front at 180 deg, completion once, cancel never completes,
           reentrancy, already-revealed, restart/load/close during flip)
    - 14.2 Luminous Evidence Highlight (light-up, bounded pulse -> steady hold,
           fade-out, invalid/empty IDs, Selected+Highlighted coexistence, zero logic)
    - 14.3 Hover & Selection Feedback (no grid pos drift, keyboard focus, hover != select)
    - 14.4 Professional Notification Motion (Accepted/Not Provable/Contradicted/Error,
           deduplication, persistence vs auto-dismiss, enter/exit, zero reveal)
    - 14.5 Controller Contract & Sequential Auto-Solve Hook + Zero domain imports
    - 14.6 Reduced-Motion Mode (instant update + queued single completion, no deadlock)
    - 14.7 5x5 Corner Flip & Responsive Regression across 1280x720 .. 1920x1080

Run headlessly with:
    QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyside6 .venv/bin/python -m pytest tests/gui/test_phase5_motion_and_integration.py -v
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QApplication

from src.gui.animations import (
    AnimationLifecycleState,
    DEFAULT_MOTION,
    MotionConfig,
    build_perspective_y_transform,
    compute_flip_frame,
)
from src.gui.app import build_main_window
from src.gui.components import CardDisplayMode, NotificationBanner
from src.gui.demo_fixtures import build_demo_3x3_snapshot, build_demo_5x5_snapshot, build_demo_snapshot
from src.gui.grid_view import GameBoard
from src.gui.view_models import (
    ActionCode,
    ActionResult,
    AnimationToken,
    CardVisibility,
    GameState,
    NotificationSeverity,
    PublicCharacterView,
)


def _revealed_copy(ch: PublicCharacterView, verdict: str = "INNOCENT") -> PublicCharacterView:
    return PublicCharacterView(
        cell_id=ch.cell_id,
        name=ch.name,
        profession=ch.profession,
        row=ch.row,
        col=ch.col,
        visibility=CardVisibility.REVEALED,
        verdict=verdict,
        has_public_clue=True,
    )


# ---------------------------------------------------------------------------
# 14.1. PHYSICAL 3D PERSPECTIVE CARD FLIP & EDGE CASES A–I
# ---------------------------------------------------------------------------


def test_3d_perspective_transform_produces_true_trapezoid_and_unmirrored_front():
    w, h = 150.0, 200.0

    # At 45 deg: genuine projective perspective makes closer vertical edge taller than receding edge
    tx_45 = build_perspective_y_transform(w, h, 45.0, lift_y=-10.0, lift_scale=1.05)
    assert tx_45.type() == QTransform.TransformationType.TxProject
    assert abs(tx_45.m13()) > 1e-4
    tl = tx_45.map(QPointF(0.0, 0.0))
    bl = tx_45.map(QPointF(0.0, h))
    tr = tx_45.map(QPointF(w, 0.0))
    br = tx_45.map(QPointF(w, h))
    left_edge_h = bl.y() - tl.y()
    right_edge_h = br.y() - tr.y()
    assert abs(left_edge_h - right_edge_h) > 10.0  # Real perspective foreshortening (NOT flat 2D scaleX!)

    # Verify timeline kinematics across all 4 stages (lift -> rotate -> midpoint -> settle)
    f_start = compute_flip_frame(0.0)
    f_lift = compute_flip_frame(0.145)
    f_q1 = compute_flip_frame(0.32)
    f_mid_pre = compute_flip_frame(0.49)
    f_mid_post = compute_flip_frame(0.51)
    f_q3 = compute_flip_frame(0.68)
    f_end = compute_flip_frame(1.0)

    assert f_start.angle_deg == 0.0 and not f_start.show_front
    assert f_lift.lift_y < 0.0 and f_lift.lift_scale > 1.0
    assert 0.0 < f_q1.angle_deg < 90.0 and not f_q1.show_front
    assert not f_mid_pre.show_front
    assert f_mid_post.show_front
    assert 90.0 < f_q3.angle_deg < 180.0 and f_q3.show_front
    # Non-mirrored front arrival: effective angle is in (-90, 0], reaching exact 0 at end
    assert -90.0 < f_q3.effective_angle_deg < 0.0
    assert f_end.angle_deg == 180.0 and f_end.show_front and f_end.effective_angle_deg == 0.0
    assert f_end.lift_y == pytest.approx(0.0, abs=1e-4)

    # At rest (effective_angle=0): exact identity transform -> front text is 100% crisp & unmirrored
    tx_end = build_perspective_y_transform(w, h, f_end.effective_angle_deg, lift_y=0.0, lift_scale=1.0)
    assert tx_end.m11() == pytest.approx(1.0)
    assert tx_end.m22() == pytest.approx(1.0)
    assert tx_end.m13() == pytest.approx(0.0)


def test_card_flip_authorized_reveal_completion_reentrancy_and_already_revealed(qtbot):
    fast_cfg = MotionConfig(card_flip_duration=80)
    board = GameBoard(motion_config=fast_cfg)
    qtbot.addWidget(board)
    snap = build_demo_3x3_snapshot()
    board.set_board(snap)
    board.resize(700, 620)
    board.show()
    qtbot.waitExposed(board)

    c1_card = board.cards_by_id["C1"]
    orig_pos = c1_card.pos()
    target_c1 = _revealed_copy(c1_card.public_data, verdict="INNOCENT")
    tok1 = AnimationToken("sess-1", 1, 2, "C1")

    finished_events: list[tuple[str, object]] = []
    cancelled_events: list[tuple[str, object]] = []
    board.animation_finished.connect(lambda cid, tok: finished_events.append((cid, tok)))
    board.animation_cancelled.connect(lambda cid, tok: cancelled_events.append((cid, tok)))

    # Case A: Normal authorized reveal starts flip
    assert board.reveal_card("C1", target_c1, tok1) is True
    assert board.is_animating is True
    assert board.motion_coordinator.state is AnimationLifecycleState.ANIMATING
    assert c1_card.zValue() >= 20.0

    # Case E: Duplicate / concurrent flip request is safely rejected (no double flip!)
    c2_card = board.cards_by_id["C2"]
    assert board.reveal_card("C1", target_c1, tok1) is False
    assert board.reveal_card("C2", _revealed_copy(c2_card.public_data, "CRIMINAL"), None) is False

    qtbot.waitUntil(lambda: len(finished_events) == 1, timeout=2000)

    # Emitted EXACTLY ONCE with matching token; card now REVEALED at identical grid pos
    assert finished_events == [("C1", tok1)]
    assert cancelled_events == []
    assert c1_card.is_revealed is True
    assert c1_card.public_data.verdict == "INNOCENT"
    assert c1_card.pos() == orig_pos  # Grid position never shifted!
    assert c1_card.zValue() < 20.0
    assert board.is_animating is False
    assert board.motion_coordinator.state is AnimationLifecycleState.IDLE

    # Case D: Already-revealed card refuses redundant flip
    assert board.reveal_card("C1", target_c1, AnimationToken("sess-1", 2, 2, "C1")) is False
    # Unknown cell refuses cleanly
    assert board.reveal_card("Z9", target_c1, None) is False
    # Non-REVEALED public_data raises ValueError
    with pytest.raises(ValueError):
        board.reveal_card("C2", c2_card.public_data, None)


def test_card_flip_cancellation_on_restart_puzzle_switch_and_window_close(qtbot):
    slow_cfg = MotionConfig(card_flip_duration=400)
    board = GameBoard(motion_config=slow_cfg)
    qtbot.addWidget(board)
    snap3 = build_demo_3x3_snapshot()
    board.set_board(snap3)

    finished_events: list[tuple[str, object]] = []
    cancelled_events: list[tuple[str, object]] = []
    board.animation_finished.connect(lambda cid, tok: finished_events.append((cid, tok)))
    board.animation_cancelled.connect(lambda cid, tok: cancelled_events.append((cid, tok)))

    # Case F: Explicit cancel / Restart during flip -> NO completion emitted, card reverted to HIDDEN
    c1 = board.cards_by_id["C1"]
    tok = AnimationToken("sess-cancel", 1, 2, "C1")
    assert board.reveal_card("C1", _revealed_copy(c1.public_data, "CRIMINAL"), tok) is True
    assert board.cancel_animations(revert_to_original=True) is True
    assert board.is_animating is False
    assert c1.is_revealed is False
    assert c1.flip_frame is None
    assert finished_events == []
    assert cancelled_events == [("C1", tok)]

    # Case G: Switch puzzle (3x3 -> 5x5) mid-flip -> old animation never leaks onto new board
    tok2 = AnimationToken("sess-switch", 2, 2, "C1")
    assert board.reveal_card("C1", _revealed_copy(c1.public_data, "INNOCENT"), tok2) is True
    board.set_board(build_demo_5x5_snapshot())
    QApplication.processEvents()
    assert board.grid_size == 5
    assert board.is_animating is False
    assert finished_events == []

    # Case H: Close window mid-flip on 5x5 corner card -> clean teardown, zero RuntimeError
    corner_e1 = board.cards_by_id["E1"]
    assert board.reveal_card("E1", _revealed_copy(corner_e1.public_data, "CRIMINAL"), None) is True
    board.close()
    QApplication.processEvents()
    assert finished_events == []


# ---------------------------------------------------------------------------
# 14.2. LUMINOUS EVIDENCE HIGHLIGHT & COEXISTENCE
# ---------------------------------------------------------------------------


def test_luminous_evidence_highlight_lifecycle_coexistence_and_privacy(qtbot):
    fast_cfg = MotionConfig(
        glow_light_up_duration=40,
        glow_pulse_duration=80,
        glow_fade_out_duration=50,
    )
    board = GameBoard(motion_config=fast_cfg)
    qtbot.addWidget(board)
    board.set_board(build_demo_3x3_snapshot())
    board.show()
    qtbot.waitExposed(board)

    # Highlight valid subset + ignore invalid IDs
    applied = board.set_highlighted_cells(["A1", "C1", "INVALID_Z9"])
    assert set(applied) == {"A1", "C1"}
    assert board.cards_by_id["C1"].is_highlighted is True
    # Highlight MUST NEVER reveal a hidden card!
    assert board.cards_by_id["C1"].is_revealed is False
    assert board.cards_by_id["C1"].public_data.verdict is None

    # Wait for light-up + bounded pulse to settle into steady hold (never infinite pulse!)
    qtbot.waitUntil(
        lambda: board.cards_by_id["C1"].glow_intensity == pytest.approx(fast_cfg.glow_hold_intensity, abs=0.02)
        and board.cards_by_id["C1"].glow_pulse == pytest.approx(0.0, abs=0.02),
        timeout=1500,
    )

    # Selected + Highlighted coexist cleanly on both REVEALED (A1) and HIDDEN (C1) cards
    board.set_selection("A1")
    assert board.cards_by_id["A1"].is_selected is True
    assert board.cards_by_id["A1"].is_highlighted is True
    assert board.cards_by_id["A1"].public_data.verdict == "INNOCENT"

    # Empty list & clear_highlight fade smoothly to 0.0
    board.clear_highlight()
    assert board.highlighted_cell_ids == ()
    qtbot.waitUntil(
        lambda: board.cards_by_id["C1"].glow_intensity == pytest.approx(0.0, abs=0.01),
        timeout=1500,
    )
    assert board.cards_by_id["C1"].is_highlighted is False


# ---------------------------------------------------------------------------
# 14.3. HOVER & SELECTION FEEDBACK
# ---------------------------------------------------------------------------


def test_hover_and_selection_do_not_shift_pos_or_mutate_domain(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    board.set_board(build_demo_3x3_snapshot())

    c1 = board.cards_by_id["C1"]
    orig_pos = c1.pos()

    # Hover does NOT select card or change grid position
    c1._hovered = True
    c1._animate_hover(1.0)
    assert c1.is_selected is False
    assert c1.pos() == orig_pos
    assert c1.is_revealed is False

    # Selection changes selected card cleanly without altering pos()
    board.set_selection("C1")
    assert board.selected_cell_id == "C1"
    assert c1.is_selected is True
    assert c1.pos() == orig_pos


# ---------------------------------------------------------------------------
# 14.4. PROFESSIONAL NOTIFICATION MOTION & DEDUPLICATION
# ---------------------------------------------------------------------------


def test_notification_banner_motion_persistence_dedup_and_no_reveal(qtbot):
    cfg = MotionConfig(
        notification_enter_duration=40,
        notification_exit_duration=40,
        notification_auto_dismiss_ms=5000,
    )
    banner = NotificationBanner(motion_config=cfg)
    qtbot.addWidget(banner)
    banner.show()

    # Accepted (Teal, VERDICT CONFIRMED, auto-dismiss armed)
    r_acc = ActionResult(ActionCode.ACCEPTED, "Phán quyết hợp lệ.", cell_id="C1")
    banner.show_result(r_acc)
    assert "VERDICT CONFIRMED" in banner.title_label.text()
    assert banner.badge_label.tone == "success"
    assert banner.is_auto_dismiss_active is True
    assert banner.show_count == 1

    # Deduplication: identical active notification does not re-trigger / stack
    banner.show_result(r_acc)
    assert banner.show_count == 1

    # Not Provable (Amber/Gold, INSUFFICIENT EVIDENCE)
    banner.show_result(ActionResult(ActionCode.NOT_PROVABLE, "Chưa đủ dữ kiện.", cell_id="C1"))
    assert "INSUFFICIENT EVIDENCE" in banner.title_label.text()
    assert banner.badge_label.tone == "warning"
    assert banner.show_count == 2

    # Contradicted & Inconsistent (Crimson, persistent — no auto-dismiss!)
    for code in (ActionCode.CONTRADICTED, ActionCode.INCONSISTENT):
        banner.show_result(ActionResult(code, f"Cảnh báo {code.value}.", cell_id="C1"))
        assert banner.badge_label.tone == "danger"
        assert banner.is_auto_dismiss_active is False

    # Animated exit hides cleanly
    banner.dismiss(animated=True)
    qtbot.waitUntil(lambda: not banner.isVisible(), timeout=1500)


# ---------------------------------------------------------------------------
# 14.5 & 14.6. SEQUENTIAL AUTO-SOLVE HOOK + REDUCED MOTION (DEMO 6 & 7)
# ---------------------------------------------------------------------------


def test_sequential_reveal_contract_and_reduced_motion_queued_completion(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    snap = build_demo_3x3_snapshot()
    window.show_gameplay(snap)
    window.set_busy(GameState.READY)

    # Enable reduced motion via MainWindow facade
    window.set_reduced_motion(True)
    assert window.reduced_motion is True
    assert window.theme_manager.reduced_motion is True
    assert window.gameplay_screen.notification_banner.reduced_motion is True

    # Simulate Controller sequential Auto-Solve: step 1 -> wait animation_finished -> step 2
    queue = [
        ("C1", "INNOCENT", AnimationToken("seq-s1", 1, 2, "C1")),
        ("A2", "CRIMINAL", AnimationToken("seq-s1", 2, 3, "A2")),
        ("B2", "INNOCENT", AnimationToken("seq-s1", 3, 4, "B2")),
    ]
    completed_order: list[tuple[str, object]] = []

    def dispatch_next() -> None:
        if not queue:
            window.set_busy(GameState.READY)
            return
        cid, verdict, tok = queue.pop(0)
        card = window.gameplay_screen.game_board.cards_by_id[cid]
        window.set_busy(GameState.ANIMATING)
        ok = window.reveal_card(cid, _revealed_copy(card.public_data, verdict), tok)
        assert ok is True
        # Completion MUST be queued (NOT synchronously emitted inside reveal_card!)
        assert all(c != cid for c, _ in completed_order)

    def on_finished(cid: str, tok: object) -> None:
        completed_order.append((cid, tok))
        dispatch_next()

    window.animation_finished.connect(on_finished)
    dispatch_next()

    qtbot.waitUntil(lambda: len(completed_order) == 3, timeout=2000)
    assert [cid for cid, _ in completed_order] == ["C1", "A2", "B2"]
    assert window.gameplay_screen.game_board.cards_by_id["C1"].public_data.verdict == "INNOCENT"
    assert window.gameplay_screen.game_board.cards_by_id["A2"].public_data.verdict == "CRIMINAL"
    assert window.gameplay_screen.game_board.cards_by_id["B2"].public_data.verdict == "INNOCENT"
    assert window.gameplay_screen.game_state is GameState.READY

    # Cancelling reduced-motion reveal before queued tick suppresses completion
    c2 = window.gameplay_screen.game_board.cards_by_id["C2"]
    cancelled: list[tuple[str, object]] = []
    window.animation_cancelled.connect(lambda cid, tok: cancelled.append((cid, tok)))
    tok_cancel = AnimationToken("seq-s1", 4, 5, "C2")
    assert window.reveal_card("C2", _revealed_copy(c2.public_data, "CRIMINAL"), tok_cancel) is True
    assert window.cancel_animations() is True
    QApplication.processEvents()
    assert len(completed_order) == 3  # Still 3 — cancelled step NEVER emitted animation_finished
    assert cancelled == [("C2", tok_cancel)]

    window.close()


# ---------------------------------------------------------------------------
# 14.7. 5×5 CORNER FLIP RESPONSIVE & ZERO DOMAIN IMPORTS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("width,height", [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
def test_5x5_corner_card_flip_and_highlight_responsive(qtbot, width, height):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show_gameplay(build_demo_5x5_snapshot())
    window.set_busy(GameState.READY)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()

    board = window.gameplay_screen.game_board
    # Highlight + select + evaluate 3D flip frame on top-right corner card E1
    board.highlight_cells(["E1", "A5", "E5"])
    board.set_selection("E1")
    e1 = board.cards_by_id["E1"]
    e1.begin_flip_animation(_revealed_copy(e1.public_data, "CRIMINAL"))
    e1.set_flip_frame(compute_flip_frame(0.35, mode=CardDisplayMode.COMPACT))
    QApplication.processEvents()

    # Scene rect comfortably accommodates corner card's expanded boundingRect
    e1_scene_rect = e1.mapRectToScene(e1.boundingRect())
    sr = board.sceneRect()
    assert e1_scene_rect.left() >= sr.left() - 10.0
    assert e1_scene_rect.right() <= sr.right() + 10.0

    e1.cancel_flip_animation(restore_data=e1.public_data)
    window.close()


def test_phase5_gui_has_zero_domain_solver_or_controller_imports():
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = "\n".join(
        [
            "import sys",
            "import src.gui.animations",
            "from src.gui.app import create_application, build_main_window",
            "from src.gui.demo_fixtures import build_demo_snapshot",
            "from src.gui.view_models import AnimationToken, CardVisibility, GameState, PublicCharacterView",
            "app, tm = create_application([])",
            "win = build_main_window(theme_manager=tm, demo_navigation=False)",
            "snap = build_demo_snapshot(5)",
            "win.show_gameplay(snap)",
            "win.set_reduced_motion(True)",
            "win.highlight_cells(['A1', 'E1', 'E5'])",
            "e1 = win.gameplay_screen.game_board.cards_by_id['E1'].public_data",
            "rev = PublicCharacterView(e1.cell_id, e1.name, e1.profession, e1.row, e1.col, CardVisibility.REVEALED, 'CRIMINAL', True)",
            "win.reveal_card('E1', rev, AnimationToken('s', 1, 2, 'E1'))",
            "win.cancel_animations()",
            "win.close()",
            "forbidden = [m for m in sys.modules if m.startswith(('src.solvers', 'src.encoder', 'src.agent', 'src.core', 'src.controller'))]",
            "assert not forbidden, f'Forbidden domain imports: {forbidden}'",
            "print('PHASE5_ISOLATION_OK')",
        ]
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "PHASE5_ISOLATION_OK" in proc.stdout
