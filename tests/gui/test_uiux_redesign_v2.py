"""Automated QA suite for GRIDUCTIVE Design System V2 — Detective Editorial Redesign.

Verifies:
1. All V2 Warm Paper / Deep Ink / Brick Red / Antique Brass contrast pairs meet WCAG AA (>= 4.5:1).
2. ThemeManager resolves the triple-stack Vietnamese typography system and compiles QSS cleanly.
3. Warm Paper editorial surfaces & accent bars are wired across About, Level Selection,
   Gameplay Dossier Sidebar (CluePanel / DeductionPanel), and Results screens.
4. True 3-tier button visual hierarchy on MainMenuScreen and ActionBar.
5. Responsive geometry across 1280x720, 1366x768, 1600x900, and 1920x1080 across all 5 screens
   including Gameplay 5x5 without regressions to GameBoard, 3D CardFlipAnimation, or Evidence Glow.
6. Architectural isolation: zero forbidden imports from src.core / src.solvers / src.encoder / src.agent.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.app_window import MainWindow
from src.gui.demo_fixtures import (
    build_demo_hint,
    build_demo_results_view,
    build_demo_snapshot,
    build_demo_trace,
)
from src.gui.navigation.screen_router import ScreenId
from src.gui.styles.theme_manager import ThemeManager, render_stylesheet
from src.gui.styles.tokens import COLORS, SPACING, TYPOGRAPHY
from src.gui.view_models import CardVisibility, GameState, PublicCharacterView


def _srgb_channel(c: int) -> float:
    x = c / 255.0
    return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _srgb_channel(r) + 0.7152 * _srgb_channel(g) + 0.0722 * _srgb_channel(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# 1. Design System V2 Token Contrast & Typography Contracts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pair_name", "fg", "bg"),
    [
        ("ink_primary on paper_canvas", COLORS.ink_primary, COLORS.paper_canvas),
        ("ink_primary on paper_sheet", COLORS.ink_primary, COLORS.paper_sheet),
        ("ink_primary on paper_linen", COLORS.ink_primary, COLORS.paper_linen),
        ("ink_secondary on paper_canvas", COLORS.ink_secondary, COLORS.paper_canvas),
        ("ink_secondary on paper_sheet", COLORS.ink_secondary, COLORS.paper_sheet),
        ("brass_ink on paper_sheet", COLORS.brass_ink, COLORS.paper_sheet),
        ("brass_ink on paper_canvas", COLORS.brass_ink, COLORS.paper_canvas),
        ("brick_accent on paper_sheet", COLORS.brick_accent, COLORS.paper_sheet),
        ("paper_sheet on brick_accent", COLORS.paper_sheet, COLORS.brick_accent),
        ("paper_innocent on paper_sheet", COLORS.paper_innocent, COLORS.paper_sheet),
        ("paper_clue on paper_sheet", COLORS.paper_clue, COLORS.paper_sheet),
        ("paper_sheet on ink_primary (inkPrimary btn)", COLORS.paper_sheet, COLORS.ink_primary),
        ("text_on_gold on accent_primary", COLORS.text_on_gold, COLORS.accent_primary),
    ],
)
def test_v2_editorial_color_pairs_meet_wcag_aa(pair_name: str, fg: str, bg: str) -> None:
    ratio = _contrast_ratio(fg, bg)
    assert ratio >= 4.5, f"WCAG AA contrast failed for {pair_name} ({fg} on {bg}): {ratio:.2f}:1"


def test_v2_spacing_and_typography_tokens_complete() -> None:
    assert SPACING.space_1 == 4
    assert SPACING.space_2 == 8
    assert SPACING.space_3 == 12
    assert SPACING.space_4 == 16
    assert SPACING.space_5 == 24
    assert SPACING.space_6 == 32
    assert SPACING.space_7 == 48

    assert len(TYPOGRAPHY.font_family_display) >= 3
    assert len(TYPOGRAPHY.font_family_ui) >= 3
    assert len(TYPOGRAPHY.font_family_mono) >= 3
    assert TYPOGRAPHY.size_display > TYPOGRAPHY.size_title > TYPOGRAPHY.size_heading > TYPOGRAPHY.size_body


def test_theme_manager_resolves_triple_stack_and_compiles_clean_qss(qtbot) -> None:
    app = QApplication.instance()
    assert app is not None
    tm = ThemeManager()
    qss = render_stylesheet()

    # Zero unresolved mustache placeholders
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", qss)
    assert unresolved == [], f"Unresolved QSS tokens: {unresolved}"

    # Triple-stack font families resolved and injected into QSS
    disp = tm.resolve_display_font_family()
    ui = tm.resolve_ui_font_family()
    mono = tm.resolve_mono_font_family()
    assert disp and ui and mono
    assert disp in qss
    assert ui in qss
    assert mono in qss

    # Editorial V2 color tokens injected into compiled QSS
    assert COLORS.paper_canvas in qss
    assert COLORS.paper_sheet in qss
    assert COLORS.ink_primary in qss
    assert COLORS.brick_accent in qss


# ---------------------------------------------------------------------------
# 2. Editorial Surfaces & True 3-Tier Button Hierarchy
# ---------------------------------------------------------------------------


def test_editorial_surfaces_and_button_hierarchy(qtbot) -> None:
    tm = ThemeManager()
    app = QApplication.instance()
    assert app is not None
    tm.apply_to_application(app)

    win = MainWindow(theme_manager=tm, demo_navigation=True)
    qtbot.addWidget(win)

    # Main Menu: 3-tier hierarchy (primary / secondary / tertiary) & preserved geometry
    menu = win.main_menu_screen
    assert menu.play_button.variant == "primary"
    assert menu.about_button.variant == "secondary"
    assert menu.exit_button.variant == "tertiary"
    assert menu.play_button.minimumWidth() == menu.about_button.minimumWidth() == menu.exit_button.minimumWidth() == 300

    # About Screen: Warm Paper editorial canvas
    assert win.about_screen.property("surface") == "paperCanvas"
    assert win.about_screen.github_button.variant == "inkPrimary"
    assert win.about_screen.youtube_button.variant == "paperSecondary"

    # Level Selection: Warm Paper archive canvas
    assert win.level_selection_screen.property("surface") == "paperCanvas"
    assert win.level_selection_screen.open_case_button.variant == "primary"

    # Gameplay Screen: Unified Cream Editorial Dossier Sidebar + 3-tier ActionBar
    gp = win.gameplay_screen
    assert gp.clue_panel.property("variant") == "paper"
    assert gp.deduction_panel.property("variant") == "paper"
    assert gp.progress_panel.property("variant") == "dossier"
    assert gp.action_bar.verdict_panel.property("variant") == "dossier"
    assert gp.action_bar.controls_panel.property("variant") == "paper"
    assert gp.action_bar.auto_solve_button.variant == "primary"
    assert gp.action_bar.hint_button.variant == "secondary"
    assert gp.action_bar.load_button.variant == "ghost"
    assert gp.action_bar.restart_button.variant == "ghost"
    assert gp.action_bar.back_button.variant == "ghost"

    # Results Screen: Pale Ivory dossier action hierarchy
    rs = win.results_screen
    assert rs.next_puzzle_button.variant == "inkPrimary"
    assert rs.restart_button.variant == "paperSecondary"
    assert rs.levels_button.variant == "paperSecondary"
    assert rs.menu_button.variant == "paperGhost"

    win.close()


# ---------------------------------------------------------------------------
# 3. Multi-Resolution Responsive Matrix + Animation/Highlight Preservation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (1280, 720),
        (1366, 768),
        (1600, 900),
        (1920, 1080),
    ],
)
def test_all_five_screens_and_5x5_board_responsive_across_target_resolutions(
    qtbot, width: int, height: int
) -> None:
    tm = ThemeManager()
    app = QApplication.instance()
    assert app is not None
    tm.apply_to_application(app)

    win = MainWindow(theme_manager=tm, demo_navigation=True)
    qtbot.addWidget(win)
    win.resize(width, height)
    win.show()
    qtbot.waitExposed(win)

    # 1. Main Menu
    win.show_main_menu()
    app.processEvents()
    assert win.current_screen is ScreenId.MAIN_MENU
    assert win.main_menu_screen.play_button.isVisible()
    assert win.main_menu_screen.about_button.isVisible()
    assert win.main_menu_screen.exit_button.isVisible()

    # 2. About
    win.show_about()
    app.processEvents()
    assert win.current_screen is ScreenId.ABOUT
    assert win.about_screen.github_button.width() >= 120
    assert win.about_screen.youtube_button.width() >= 180

    # 3. Level Selection
    win.show_level_selection()
    app.processEvents()
    assert win.current_screen is ScreenId.LEVEL_SELECTION
    assert win.level_selection_screen.open_case_button.isVisible()

    # 4. Gameplay 5x5 (stress test board dominance + readability)
    win.show_gameplay()
    snap5 = build_demo_snapshot(5, puzzle_id="HARD_5x5_01")
    win.set_board(snap5)
    win.set_game_status(GameState.READY)
    win.set_deduction_trace(build_demo_trace(5))
    win.show_hint(build_demo_hint(cell_id="C3"))
    app.processEvents()
    assert win.gameplay_screen.game_board.card_count == 25
    assert win.gameplay_screen.board_container.width() > win.gameplay_screen.clue_panel.width()
    assert win.gameplay_screen.board_container.height() >= 360

    # 5. Results
    win.show_results(build_demo_results_view(puzzle_id="HARD_5x5_01", grid_size=5))
    app.processEvents()
    assert win.current_screen is ScreenId.RESULTS
    assert win.results_screen.next_puzzle_button.isVisible()

    win.close()


def test_redesign_preserves_phase5_3d_card_flip_and_evidence_glow(qtbot) -> None:
    tm = ThemeManager()
    app = QApplication.instance()
    assert app is not None
    tm.apply_to_application(app)

    win = MainWindow(theme_manager=tm, demo_navigation=True)
    qtbot.addWidget(win)
    win.resize(1366, 768)
    win.show()
    qtbot.waitExposed(win)

    snap3 = build_demo_snapshot(3, puzzle_id="EASY_3x3_01")
    win.show_gameplay()
    win.set_board(snap3)
    win.set_game_status(GameState.READY)

    # Evidence highlight glow
    highlighted = win.highlight_cells(["A1", "B1", "C1"])
    assert set(highlighted) == {"A1", "B1", "C1"}
    win.clear_highlights()

    # 3D Card flip reveal with animation_finished handshake
    finished_events: list[tuple[str, object]] = []
    win.animation_finished.connect(lambda cid, tok: finished_events.append((cid, tok)))

    c1_revealed = PublicCharacterView(
        cell_id="C1",
        row=0,
        col=2,
        name="Clara",
        profession="Nhà báo",
        visibility=CardVisibility.REVEALED,
        verdict="INNOCENT",
    )
    started = win.reveal_card("C1", c1_revealed, token="redesign-tok-1")
    assert started is True

    qtbot.waitUntil(lambda: len(finished_events) == 1, timeout=2500)
    assert finished_events == [("C1", "redesign-tok-1")]
    assert win.gameplay_screen.game_board.cards_by_id["C1"].public_data.visibility is CardVisibility.REVEALED

    win.close()


# ---------------------------------------------------------------------------
# 4. Architectural Isolation Guard (GUI never imports domain/solver/engine)
# ---------------------------------------------------------------------------


def test_gui_package_remains_strictly_isolated_from_domain_modules() -> None:
    forbidden_prefixes = ("src.core", "src.solvers", "src.encoder", "src.agent")
    gui_root = Path(__file__).resolve().parents[2] / "src" / "gui"
    py_files = sorted(gui_root.rglob("*.py"))
    assert py_files, "Expected Python modules under src/gui"

    violations: list[str] = []
    for py_path in py_files:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden_prefixes):
                        violations.append(f"{py_path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(forbidden_prefixes):
                    violations.append(f"{py_path}: from {node.module} import ...")

    assert violations == [], f"Forbidden domain imports found in src/gui: {violations}"
