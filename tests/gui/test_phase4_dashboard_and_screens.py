"""Comprehensive automated Phase 4 tests for Dashboard, Evidence & Supporting Screens.

Covers all 47+ test requirements from Phase 4 Section 18 (18.1 – 18.7):
    - 18.1 CluePanel (1–14)
    - 18.2 DeductionPanel & HintBox (15–22)
    - 18.3 ActionBar & GameState enablement (23–32)
    - 18.4 ProgressPanel & GameStatus (33–39)
    - 18.5 Supporting Screens: MainMenu, LevelSelection (15 cases + A06), Results (A07) (40–47)
    - 18.6 Responsive & GĐ3 Regression across 1280×720, 1366×768, 1600×900, 1920×1080 × 3×3/4×4/5×5
    - 18.7 Architecture & Domain/Privacy Isolation (fresh Python subprocess)

Run headlessly with:
    QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyside6 .venv/bin/python -m pytest tests/gui/test_phase4_dashboard_and_screens.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.app import build_main_window
from src.gui.components import (
    ActionBar,
    CluePanel,
    DeductionPanel,
    NotificationBanner,
    NotificationDialog,
    ProgressPanel,
)
from src.gui.demo_fixtures import (
    build_demo_3x3_snapshot,
    build_demo_4x4_snapshot,
    build_demo_5x5_snapshot,
    build_demo_hint,
    build_demo_level_catalog,
    build_demo_notification,
    build_demo_results_view,
    build_demo_snapshot,
    build_demo_trace,
)
from src.gui.navigation.screen_router import ScreenId
from src.gui.view_models import (
    ActionCode,
    ActionResult,
    CardVisibility,
    DeductionStepView,
    GameState,
    HintView,
    LevelSummary,
    NotificationSeverity,
    PublicBoardSnapshot,
    PublicCharacterView,
    PublicClueView,
    ResultsView,
)


# ---------------------------------------------------------------------------
# 18.1. CLUE PANEL (Criteria 1–14)
# ---------------------------------------------------------------------------


def test_clue_panel_displays_six_core_types_icons_metadata_and_plain_text(qtbot):
    panel = CluePanel()
    qtbot.addWidget(panel)
    panel.resize(360, 480)

    clues = [
        PublicClueView("C_FACT", "A1", "FACT", "<b>A1</b> là INNOCENT (hiển thị plain text)."),
        PublicClueView("C_SAME", "B1", "SAME", "B1 và C1 cùng phe."),
        PublicClueView("C_DIFF", "C1", "DIFFERENT", "C1 và A2 khác phe."),
        PublicClueView("C_EXACT", "A2", "EXACTLY", "Hàng 2 có đúng 1 CRIMINAL."),
        PublicClueView("C_LEAST", "B2", "AT_LEAST", "Cột B có ít nhất 1 CRIMINAL."),
        PublicClueView("C_MOST", "C2", "AT_MOST", "Vùng lân cận có nhiều nhất 2 CRIMINAL."),
    ]
    panel.set_clues(clues)
    panel.show()
    qtbot.waitExposed(panel)

    assert not panel.is_empty
    assert len(panel.clues) == 6
    assert set(panel.clue_cards.keys()) == {c.clue_id for c in clues}

    for c in clues:
        card = panel.clue_cards[c.clue_id]
        assert card.clue.clue_id == c.clue_id
        assert card.clue.owner_id == c.owner_id
        assert card.text_label.text() == c.text
        assert card.text_label.textFormat() == Qt.TextFormat.PlainText
        assert card.text_label.wordWrap() is True
        assert card.used_fallback_icon is False
        assert card.icon_label.pixmap() is not None and not card.icon_label.pixmap().isNull()


def test_clue_panel_unknown_clue_type_fallback_and_long_text_scrolling(qtbot):
    panel = CluePanel()
    qtbot.addWidget(panel)
    panel.resize(340, 220)

    long_clues = [
        PublicClueView(
            f"CLUE_{i:02d}",
            f"A{(i % 5) + 1}",
            "CUSTOM_FUTURE_TYPE" if i == 0 else "EXACTLY",
            f"Manh mối mở rộng số {i:02d} với nội dung giải thích rất dài để đảm bảo word-wrap và thanh cuộn dọc hoạt động mượt mà không bị cắt chữ.",
        )
        for i in range(10)
    ]
    panel.set_clues(long_clues)
    panel.show()
    qtbot.waitExposed(panel)
    QApplication.processEvents()

    # Unknown clue type uses safe Qt-native fallback badge without crashing
    unknown_card = panel.clue_cards["CLUE_00"]
    assert unknown_card.used_fallback_icon is True
    assert unknown_card.icon_label.text() == "CUST"

    # Scrollable when many clues overflow panel height
    bar = panel.scroll_area.verticalScrollBar()
    assert bar.maximum() > 0


def test_clue_panel_selection_signal_update_empty_and_privacy_rejection(qtbot):
    panel = CluePanel()
    qtbot.addWidget(panel)
    assert panel.is_empty

    c1 = PublicClueView("CLUE_A1", "A1", "FACT", "A1 là INNOCENT.")
    c2 = PublicClueView("CLUE_B1", "B1", "SAME", "B1 cùng phe C1.")
    panel.set_clues([c1])
    assert len(panel.clues) == 1

    # Add newly revealed clue dynamically
    panel.add_or_update_clue(c2)
    assert len(panel.clues) == 2

    received: list[str] = []
    panel.clue_selected.connect(received.append)

    # User click emits clue_selected once and marks card selected
    panel.clue_cards["CLUE_B1"].clicked.emit("CLUE_B1")
    assert panel.selected_clue_id == "CLUE_B1"
    assert panel.clue_cards["CLUE_B1"].is_selected is True
    assert panel.clue_cards["CLUE_A1"].is_selected is False
    assert received == ["CLUE_B1"]

    # Programmatic selection does NOT re-emit signal
    assert panel.set_selected_clue("CLUE_A1") is True
    assert panel.selected_clue_id == "CLUE_A1"
    assert received == ["CLUE_B1"]

    # Locking interaction prevents user click selection
    panel.set_interactive(False)
    panel.clue_cards["CLUE_B1"].clicked.emit("CLUE_B1")
    assert panel.selected_clue_id == "CLUE_A1"
    assert received == ["CLUE_B1"]

    # Clear restores empty state
    panel.clear()
    assert panel.is_empty
    assert panel.selected_clue_id is None

    # Privacy boundary: unrevealed or raw domain clue with parameters MUST be rejected
    @dataclass
    class _PrivateClueStub:
        clue_id: str = "SECRET_1"
        owner_id: str = "C1"
        clue_type: str = "FACT"
        text: str = "Hidden secret"
        is_revealed: bool = False

    @dataclass
    class _RawDomainClueStub:
        clue_id: str = "RAW_1"
        owner_id: str = "A1"
        clue_type: str = "EXACTLY"
        text: str = "Raw"
        parameters: dict = None  # type: ignore[assignment]

    with pytest.raises(ValueError):
        panel.set_clues([_PrivateClueStub()])

    with pytest.raises(ValueError):
        panel.set_clues([_RawDomainClueStub(parameters={"count": 1})])

    # Snapshot privacy boundary: clue belonging to HIDDEN character is rejected
    snap3 = build_demo_3x3_snapshot()
    leaked_clue = PublicClueView("CLUE_C1", "C1", "FACT", "Leak from hidden C1")
    with pytest.raises(ValueError, match="Privacy violation"):
        PublicBoardSnapshot(
            session_id="s-leak",
            puzzle_id="P_LEAK",
            grid_size=3,
            kb_version=1,
            characters=snap3.characters,
            clues=(leaked_clue,),
        )


# ---------------------------------------------------------------------------
# 18.2. DEDUCTION PANEL & HINT BOX (Criteria 15–22)
# ---------------------------------------------------------------------------


def test_deduction_panel_append_idempotency_replace_clear_verdict_colors_and_hint(qtbot):
    panel = DeductionPanel()
    qtbot.addWidget(panel)
    panel.resize(360, 260)
    panel.show()
    qtbot.waitExposed(panel)

    assert panel.is_empty
    assert panel.step_count == 0
    assert not panel.hint_box.isVisible()

    s1 = DeductionStepView("sess-1", 1, 1, "B1", "CRIMINAL", "B1 bắt buộc là CRIMINAL.", ("CLUE_A1",), sat_calls=3)
    s2 = DeductionStepView("sess-1", 2, 2, "C1", "INNOCENT", "C1 bắt buộc là INNOCENT.", ("CLUE_A1", "CLUE_B1"), sat_calls=2)
    s3 = DeductionStepView("sess-1", 3, 2, "A2", "UNKNOWN", "Chưa đủ dữ kiện để kết luận.", ())

    assert panel.append_step(s1) is True
    # Duplicate (session_id, request_id, cell_id) is idempotently ignored
    assert panel.append_step(s1) is False
    assert panel.append_step(s2) is True
    assert panel.append_step(s3) is True
    assert panel.step_count == 3

    # Verify ordering and semantic verdict badge tones (Crimson / Teal / Neutral)
    entries = panel.entry_widgets
    assert [e.step.cell_id for e in entries] == ["B1", "C1", "A2"]
    assert entries[0].verdict_badge.tone == "danger"
    assert entries[1].verdict_badge.tone == "success"
    assert entries[2].verdict_badge.tone == "neutral"

    # Separate HintBox does NOT pollute accepted trace count
    hint = build_demo_hint(session_id="sess-1", cell_id="C2")
    panel.show_hint(hint)
    assert panel.hint_box.isVisible()
    assert panel.current_hint == hint
    assert panel.step_count == 3

    panel.clear_hint()
    assert not panel.hint_box.isVisible()
    assert panel.current_hint is None

    # Replace trace with long list to verify scrolling
    many_steps = [
        DeductionStepView(
            "sess-2",
            i,
            i,
            f"A{(i % 5) + 1}",
            "CRIMINAL" if i % 2 else "INNOCENT",
            f"Bước suy luận #{i:02d} giải thích chi tiết bằng public KB.",
            ("CLUE_A1",),
        )
        for i in range(1, 13)
    ]
    panel.set_steps(many_steps)
    assert panel.step_count == 12
    qtbot.waitUntil(lambda: panel.scroll_area.verticalScrollBar().maximum() > 0, timeout=2000)

    # Smart auto-scroll: if user scrolls up to read older steps, appending does NOT hijack scroll
    bar = panel.scroll_area.verticalScrollBar()
    bar.setValue(0)
    assert bar.value() == 0
    extra = DeductionStepView("sess-2", 99, 99, "E5", "CRIMINAL", "Bước đọc bổ sung.", ("CLUE_A1",))
    assert panel.append_step(extra) is True
    QApplication.processEvents()
    assert bar.value() == 0

    # Clear removes all entries and shows empty state
    panel.clear()
    assert panel.is_empty
    assert panel.step_count == 0


# ---------------------------------------------------------------------------
# 18.3. ACTION BAR & CONTROLLER BOUNDARY (Criteria 23–32)
# ---------------------------------------------------------------------------


def test_action_bar_signals_enablement_matrix_and_zero_auto_flip(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    snap = build_demo_3x3_snapshot()
    window.show_gameplay(snap)

    bar: ActionBar = window.gameplay_screen.action_bar

    # Initially NO_PUZZLE -> verdict, hint, auto_solve, restart disabled
    window.set_busy(GameState.NO_PUZZLE)
    assert not bar.criminal_button.isEnabled()
    assert not bar.innocent_button.isEnabled()
    assert not bar.hint_button.isEnabled()
    assert not bar.auto_solve_button.isEnabled()
    assert not bar.restart_button.isEnabled()
    assert bar.load_button.isEnabled()
    assert bar.back_button.isEnabled()

    # READY with NO selection -> verdict disabled; hint/auto/restart/load enabled
    window.set_busy(GameState.READY)
    assert not bar.criminal_button.isEnabled()
    assert not bar.innocent_button.isEnabled()
    assert bar.hint_button.isEnabled()
    assert bar.auto_solve_button.isEnabled()
    assert bar.restart_button.isEnabled()

    # Select REVEALED card (A1) -> verdict stays disabled
    window.set_selection("A1")
    assert not bar.criminal_button.isEnabled()
    assert not bar.innocent_button.isEnabled()

    # Select HIDDEN card (C1) -> verdict buttons enabled
    window.set_selection("C1")
    assert bar.criminal_button.isEnabled()
    assert bar.innocent_button.isEnabled()

    # Clicking CRIMINAL emits verdict_requested("C1", "CRIMINAL") and MUST NOT flip C1
    verdicts: list[tuple[str, object]] = []
    window.verdict_requested.connect(lambda cid, v: verdicts.append((cid, v)))

    bar.criminal_button.click()
    bar.innocent_button.click()
    assert verdicts == [("C1", "CRIMINAL"), ("C1", "INNOCENT")]
    # Card C1 remains strictly HIDDEN with verdict=None (GUI never mutates domain!)
    c1_card = window.gameplay_screen.game_board.cards_by_id["C1"]
    assert c1_card.is_revealed is False
    assert c1_card.public_data.verdict is None

    # All game action signals emit properly through MainWindow facade
    with qtbot.waitSignal(window.hint_requested, timeout=1000):
        bar.hint_button.click()
    with qtbot.waitSignal(window.auto_solve_requested, timeout=1000):
        bar.auto_solve_button.click()
    with qtbot.waitSignal(window.restart_requested, timeout=1000):
        bar.restart_button.click()
    with qtbot.waitSignal(window.level_selection_requested, timeout=1000):
        bar.load_button.click()
    with qtbot.waitSignal(window.back_requested, timeout=1000):
        bar.back_button.click()

    # PROCESSING & ANIMATING lock verdict, hint, auto_solve, board & clues; keep load/restart/back
    for busy_state in (GameState.PROCESSING, GameState.ANIMATING):
        window.set_busy(busy_state)
        assert not bar.criminal_button.isEnabled()
        assert not bar.innocent_button.isEnabled()
        assert not bar.hint_button.isEnabled()
        assert not bar.auto_solve_button.isEnabled()
        assert bar.restart_button.isEnabled()
        assert bar.load_button.isEnabled()
        assert bar.back_button.isEnabled()
        assert window.gameplay_screen.clue_panel.is_interactive is False

    # SOLVED disables verdict/hint/auto_solve
    window.set_busy(GameState.SOLVED)
    assert not bar.criminal_button.isEnabled()
    assert not bar.innocent_button.isEnabled()
    assert not bar.hint_button.isEnabled()
    assert not bar.auto_solve_button.isEnabled()

    # ERROR disables verdict/hint/auto_solve while allowing recovery via Load/Restart/Back
    window.set_busy(GameState.ERROR)
    assert not bar.criminal_button.isEnabled()
    assert not bar.hint_button.isEnabled()
    assert bar.restart_button.isEnabled()
    assert bar.load_button.isEnabled()
    window.close()


# ---------------------------------------------------------------------------
# 18.4. PROGRESS PANEL, GAME STATUS & NOTIFICATIONS (Criteria 33–39)
# ---------------------------------------------------------------------------


def test_progress_panel_counts_percentage_zero_safe_and_all_seven_states(qtbot):
    panel = ProgressPanel()
    qtbot.addWidget(panel)

    panel.set_case_info("CASE_4x4_03", 4)
    panel.set_progress(6, 16)
    assert panel.revealed_count == 6
    assert panel.total_count == 16
    assert panel.remaining_count == 10
    assert panel.progress_percent == pytest.approx(37.5)
    assert "6 / 16" in panel.revealed_label.text()
    assert "10" in panel.remaining_label.text()
    assert panel.progress_bar.text() == "37.5%"

    # Zero / negative / out-of-range totals handled safely without crash
    panel.set_progress(0, 0)
    assert panel.progress_percent == 0.0
    assert panel.remaining_count == 0
    panel.set_progress(5, -10)
    assert panel.total_count == 0 and panel.revealed_count == 0
    panel.set_progress(99, 9)
    assert panel.revealed_count == 9 and panel.remaining_count == 0

    # All 7 GameState values update cleanly; only ERROR uses danger (red) tone
    for state in GameState:
        panel.set_game_status(state)
        assert panel.game_state is state
        if state is GameState.ERROR:
            assert panel.status_badge.tone == "danger"
        else:
            assert panel.status_badge.tone != "danger"


def test_notification_banner_and_dialog_distinguish_controller_outcomes(qtbot):
    banner = NotificationBanner()
    qtbot.addWidget(banner)
    assert not banner.isVisible()

    for code, expected_sev in (
        (ActionCode.ACCEPTED, NotificationSeverity.SUCCESS),
        (ActionCode.NOT_PROVABLE, NotificationSeverity.WARNING),
        (ActionCode.CONTRADICTED, NotificationSeverity.ERROR),
        (ActionCode.INCONSISTENT, NotificationSeverity.ERROR),
        (ActionCode.CANCELLED, NotificationSeverity.INFO),
    ):
        res = build_demo_notification(code, cell_id="B2")
        applied = banner.show_result(res)
        assert applied.severity is expected_sev
        assert banner.isVisible()
        assert code.value in banner.title_label.text()
        assert res.message == banner.message_label.text()

    banner.close_button.click()
    assert not banner.isVisible()

    # Modal NotificationDialog renders plain text cleanly
    dlg = NotificationDialog(ActionResult(ActionCode.LOAD_FAILED, "<b>Lỗi nạp file</b>"))
    qtbot.addWidget(dlg)
    assert dlg.message_label.textFormat() == Qt.TextFormat.PlainText
    assert dlg.message_label.text() == "<b>Lỗi nạp file</b>"


# ---------------------------------------------------------------------------
# 18.5. SUPPORTING SCREENS: MAIN MENU, LEVEL SELECTION, RESULTS (Criteria 40–47)
# ---------------------------------------------------------------------------


def test_supporting_screens_assets_15_case_archive_and_results_view(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    window.show()

    # 1. Main Menu displays A04 wide logo + cartoon A04 app emblem
    assert window.current_screen is ScreenId.MAIN_MENU
    assert not window.main_menu_screen.logo_view.is_missing
    assert not window.main_menu_screen.emblem_view.is_missing

    # 2. Level Selection shows 3 A06 covers and renders all 15 public LevelSummary tiles
    catalog = build_demo_level_catalog()
    assert len(catalog) == 15
    window.show_level_selection(catalog)
    assert window.current_screen is ScreenId.LEVEL_SELECTION

    ls = window.level_selection_screen
    for key in ("3x3", "4x4", "5x5"):
        assert key in ls.cover_views
        assert not ls.cover_views[key].is_missing
    assert len(ls.case_tiles) == 15
    assert not ls.open_case_button.isEnabled()

    # Selecting a case tile enables Open button and emits load_requested(puzzle_id)
    target_id = "MOCK_4x4_03"
    ls.case_tiles[target_id].case_selected.emit(target_id)
    assert ls.selected_puzzle_id == target_id
    assert ls.open_case_button.isEnabled()

    loaded_ids: list[str] = []
    window.load_requested.connect(loaded_ids.append)
    ls.open_case_button.click()
    assert loaded_ids == [target_id]
    # Controller mode does NOT auto-open gameplay on its own
    assert window.current_screen is ScreenId.LEVEL_SELECTION

    # 3. Results Screen displays A07 emblem, confirmed ResultsView stats & Next Puzzle signal
    results = ResultsView(
        session_id="sess-99",
        puzzle_id="4x4_03",
        revealed=16,
        total=16,
        accepted_steps=12,
        hint_requests=2,
        elapsed_ms=65400.0,
        sat_calls=48,
        next_puzzle_id="4x4_04",
    )
    window.show_results(results)
    assert window.current_screen is ScreenId.RESULTS
    rs = window.results_screen
    assert not rs.emblem_view.is_missing
    assert rs.value_labels["puzzle_id"].text() == "4x4_03"
    assert rs.value_labels["grid_size"].text() == "4×4"
    assert rs.value_labels["revealed"].text() == "16 / 16"
    assert rs.value_labels["accepted_steps"].text() == "12"
    assert rs.value_labels["hint_requests"].text() == "2"
    assert rs.value_labels["sat_calls"].text() == "48"
    assert rs.next_puzzle_button.isEnabled()

    rs.next_puzzle_button.click()
    assert loaded_ids == [target_id, "4x4_04"]

    # When next_puzzle_id is None, Next button is disabled and preview notice distinguishes demo
    preview = build_demo_results_view(puzzle_id="MOCK_5x5_05", grid_size=5)
    window.show_results(preview)
    assert not rs.next_puzzle_button.isEnabled()
    assert "PREVIEW" in rs.notice_label.text().upper()
    assert rs.value_labels["sat_calls"].text() == "—"
    window.close()


# ---------------------------------------------------------------------------
# 18.6. RESPONSIVE MATRIX & GĐ3 REGRESSION (1280×720 .. 1920×1080 × 3/4/5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("grid_size", [3, 4, 5])
@pytest.mark.parametrize(
    "width,height",
    [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)],
)
def test_phase4_responsive_dashboard_and_gd3_board_regression(qtbot, grid_size, width, height):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.resize(width, height)

    snap = build_demo_snapshot(grid_size)
    window.show_gameplay(snap)
    window.set_deduction_trace(build_demo_trace(grid_size, session_id=snap.session_id))
    window.set_busy(GameState.READY)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()

    gs = window.gameplay_screen
    # Board remains dominant and spacious; ActionBar stays fully visible inside window
    assert gs.board_container.width() > gs.clue_panel.width()
    assert gs.game_board.card_count == grid_size * grid_size
    assert gs.action_bar.isVisible()
    assert gs.action_bar.height() >= 88
    assert gs.clue_panel.isVisible()
    assert gs.deduction_panel.isVisible()
    assert gs.progress_panel.isVisible()

    # GĐ3 single selection still works smoothly inside full GĐ4 dashboard
    first_hidden = next(c.cell_id for c in snap.characters if c.visibility is CardVisibility.HIDDEN)
    gs.game_board.cards_by_id[first_hidden].card_selected.emit(first_hidden)
    assert gs.game_board.selected_cell_id == first_hidden
    assert gs.action_bar.criminal_button.isEnabled()
    assert gs.action_bar.innocent_button.isEnabled()

    window.close()


# ---------------------------------------------------------------------------
# 18.7. ARCHITECTURE & ISOLATION CHECK (Fresh Python Subprocess)
# ---------------------------------------------------------------------------


def test_phase4_gui_has_zero_domain_solver_or_controller_imports():
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = "\n".join(
        [
            "import sys",
            "from src.gui.app import create_application, build_main_window",
            "from src.gui.demo_fixtures import (",
            "    build_demo_snapshot, build_demo_trace, build_demo_hint,",
            "    build_demo_level_catalog, build_demo_results_view, build_demo_notification",
            ")",
            "from src.gui.view_models import ActionCode, GameState",
            "app, tm = create_application([])",
            "win = build_main_window(theme_manager=tm, demo_navigation=True)",
            "win.show_level_selection(build_demo_level_catalog())",
            "for n in (3, 4, 5):",
            "    snap = build_demo_snapshot(n)",
            "    win.show_gameplay(snap)",
            "    win.set_deduction_trace(build_demo_trace(n, session_id=snap.session_id))",
            "    win.show_hint(build_demo_hint())",
            "    win.show_notification(build_demo_notification(ActionCode.NOT_PROVABLE))",
            "    win.set_busy(GameState.READY)",
            "win.show_results(build_demo_results_view())",
            "win.close()",
            "forbidden = [m for m in sys.modules if m.startswith(('src.solvers', 'src.encoder', 'src.agent', 'src.core', 'src.controller'))]",
            "assert not forbidden, f'Forbidden domain imports: {forbidden}'",
            "print('PHASE4_ISOLATION_OK')",
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
    assert "PHASE4_ISOLATION_OK" in proc.stdout
