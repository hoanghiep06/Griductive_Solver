"""Automated Phase 2 UI Foundation & Application Framework tests (PySide6 + pytest-qt).

Run headlessly with:
    QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyside6 .venv/bin/python -m pytest tests/gui/test_phase2_ui_foundation.py -v
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QGraphicsView

from src.gui.app import build_main_window, create_application
from src.gui.app_window import MainWindow
from src.gui.asset_registry import AssetId, AssetRegistry, DEFAULT_REGISTRY
from src.gui.components import (
    AssetImageView,
    ImageScaleMode,
    PageHeader,
    SectionPlaceholder,
    StatusLabel,
    StyledButton,
    StyledPanel,
)
from src.gui.navigation.screen_router import ScreenId, ScreenRouter
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.styles import COLORS, GEOMETRY, SPACING, THEME, ThemeManager, render_stylesheet


def test_qapplication_and_global_stylesheet_load(qtbot):
    app, theme_manager = create_application([])
    assert isinstance(app, QApplication)
    qss = theme_manager.stylesheet()
    assert qss and "{{" not in qss and "}}" not in qss
    assert app.styleSheet() == qss
    assert THEME.colors is COLORS
    assert SPACING.space_4 == 16
    assert GEOMETRY.button_min_height >= 44


def test_main_window_creation_icon_and_four_screens(qtbot):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    assert isinstance(window, MainWindow)
    assert "GRIDUCTIVE" in window.windowTitle()
    assert not window.windowIcon().isNull()

    assert set(window.router.registered_screens) == {
        ScreenId.MAIN_MENU,
        ScreenId.ABOUT,
        ScreenId.LEVEL_SELECTION,
        ScreenId.GAMEPLAY,
        ScreenId.RESULTS,
    }
    assert window.current_screen is ScreenId.MAIN_MENU
    window.close()


def test_screen_navigation_and_invalid_route_handling(qtbot):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)

    assert window.show_screen(ScreenId.LEVEL_SELECTION) is True
    assert window.current_screen is ScreenId.LEVEL_SELECTION

    assert window.show_screen("GAMEPLAY") is True
    assert window.current_screen is ScreenId.GAMEPLAY

    assert window.show_screen(ScreenId.RESULTS) is True
    assert window.current_screen is ScreenId.RESULTS

    # Unknown or invalid routes fail gracefully without changing current screen
    assert window.show_screen("NON_EXISTENT_SCREEN") is False
    assert window.current_screen is ScreenId.RESULTS

    assert window.show_screen(ScreenId.MAIN_MENU) is True
    assert window.current_screen is ScreenId.MAIN_MENU


def test_demo_navigation_clicks_and_controller_isolation_mode(qtbot):
    # 1. Demo mode routes through all 4 screens via UI buttons
    demo_win = build_main_window(demo_navigation=True)
    qtbot.addWidget(demo_win)
    demo_win.show()

    demo_win.main_menu_screen.play_button.click()
    assert demo_win.current_screen is ScreenId.LEVEL_SELECTION

    demo_win.level_selection_screen.preview_buttons["4x4"].click()
    assert demo_win.current_screen is ScreenId.GAMEPLAY

    demo_win.gameplay_screen.demo_results_requested.emit()
    assert demo_win.current_screen is ScreenId.RESULTS

    demo_win.results_screen.menu_button.click()
    assert demo_win.current_screen is ScreenId.MAIN_MENU

    # How to Play dialog opens and closes cleanly
    demo_win.show_how_to_play()
    assert demo_win._active_help_dialog is not None
    assert demo_win._active_help_dialog.isVisible()
    demo_win.close()

    # 2. Controller mode (demo_navigation=False): emits intent signal without auto-routing
    ctrl_win = build_main_window(demo_navigation=False)
    qtbot.addWidget(ctrl_win)
    with qtbot.waitSignal(ctrl_win.play_requested, timeout=1000):
        ctrl_win.main_menu_screen.play_button.click()
    assert ctrl_win.current_screen is ScreenId.MAIN_MENU


def test_assets_resolve_independent_of_cwd_and_cache_pixmaps(qtbot, tmp_path):
    loader = PixmapLoader(DEFAULT_REGISTRY)
    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        pm1 = loader.load_pixmap(AssetId.A04_LOGO_WIDE, prefer_derived=True)
        pm2 = loader.load_pixmap(AssetId.A04_LOGO_WIDE, prefer_derived=True)
        assert not pm1.isNull()
        assert pm1 is pm2  # Cached instance, not re-decoded
        assert loader.load_pixmap(AssetId.A06_CASE_COVER_3X3, prefer_derived=False).size() == QSize(1440, 1080)
        assert loader.load_pixmap(AssetId.A06_CASE_COVER_4X4, prefer_derived=False).size() == QSize(1440, 1080)
        assert loader.load_pixmap(AssetId.A06_CASE_COVER_5X5, prefer_derived=False).size() == QSize(1440, 1080)
    finally:
        os.chdir(old_cwd)


def test_missing_assets_handled_gracefully(qtbot, tmp_path):
    empty_registry = AssetRegistry(assets_root=tmp_path)
    loader = PixmapLoader(empty_registry)
    pm = loader.load_pixmap(AssetId.A04_LOGO_WIDE)
    assert pm.isNull()
    assert len(loader.warnings) >= 1

    view = AssetImageView(AssetId.A04_LOGO_WIDE, pixmap_loader=loader)
    qtbot.addWidget(view)
    view.resize(320, 180)
    view.show()
    qtbot.waitExposed(view)
    assert view.is_missing is True


def test_reusable_primitives_variants_and_states(qtbot):
    for variant in ("primary", "secondary", "danger", "success", "ghost"):
        btn = StyledButton(f"Btn {variant}", variant=variant)
        qtbot.addWidget(btn)
        assert btn.variant == variant
        assert btn.minimumHeight() >= 44
        btn.setEnabled(False)
        assert not btn.isEnabled()

    with pytest.raises(ValueError):
        StyledButton("Invalid", variant="neon_pink")

    panel = StyledPanel(title="Case Info", subtitle="Subtitle", variant="elevated", decorative_texture=True)
    qtbot.addWidget(panel)
    panel.resize(320, 220)
    panel.show()
    qtbot.waitExposed(panel)

    header = PageHeader("Screen Title", subtitle="Subtitle")
    qtbot.addWidget(header)
    assert header.title_label.text() == "Screen Title"

    pill = StatusLabel("READY", tone="success")
    qtbot.addWidget(pill)
    assert pill.tone == "success"

    placeholder = SectionPlaceholder("Board Slot", target_phase="GĐ3", description="Reserved")
    qtbot.addWidget(placeholder)
    assert placeholder.target_phase == "GĐ3"


@pytest.mark.parametrize(
    "width,height",
    [(960, 640), (1280, 720), (1366, 768), (1600, 900), (1920, 1080)],
)
def test_window_resizes_cleanly_across_target_resolutions(qtbot, width, height):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show()
    for screen_id in (ScreenId.MAIN_MENU, ScreenId.LEVEL_SELECTION, ScreenId.GAMEPLAY, ScreenId.RESULTS):
        assert window.show_screen(screen_id) is True
        QApplication.processEvents()

    # Verify Gameplay reserves dominant width for future 5x5 GameBoard
    window.show_gameplay()
    QApplication.processEvents()
    board_w = window.gameplay_screen.board_container.width()
    sidebar_w = window.gameplay_screen.clue_container.width()
    assert board_w > sidebar_w
    window.close()


def test_gameplay_hosts_game_board_and_phase4_dashboard_panels(qtbot):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.show_gameplay()
    # Phase 3 GameBoard + Phase 4 real dashboard panels (0 SectionPlaceholders remain)
    views = window.gameplay_screen.findChildren(QGraphicsView)
    assert len(views) == 1
    assert window.gameplay_screen.game_board is views[0]
    placeholders = window.gameplay_screen.findChildren(SectionPlaceholder)
    assert len(placeholders) == 0
    assert window.gameplay_screen.clue_panel is window.gameplay_screen.clue_container
    assert window.gameplay_screen.deduction_panel is window.gameplay_screen.deduction_container
    assert window.gameplay_screen.progress_panel is window.gameplay_screen.progress_container
    window.close()


def test_no_domain_imports_and_no_circular_imports_in_fresh_python():
    """Verify GUI foundation starts cleanly without DPLL, Encoder, Agent, Core, or Controller."""
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = (
        "import sys; "
        "import src.gui, src.gui.app, src.gui.app_window, "
        "src.gui.navigation.screen_router, src.gui.resources.pixmap_loader, "
        "src.gui.styles.theme_manager, src.gui.components, src.gui.screens; "
        "app, tm = src.gui.app.create_application([]); "
        "win = src.gui.app.build_main_window(theme_manager=tm, demo_navigation=True); "
        "win.show_gameplay(); "
        "win.close(); "
        "forbidden = [m for m in sys.modules if m.startswith(('src.solvers', 'src.encoder', 'src.agent', 'src.core', 'src.controller'))]; "
        "assert not forbidden, f'Forbidden domain imports loaded: {forbidden}'; "
        "print('ISOLATION_OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ISOLATION_OK" in proc.stdout
