"""Automated tests for Main Menu About button & dedicated AboutScreen.

Covers all 17 verification items from the Main Menu About Screen Update spec.

Run headlessly with:
    QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyside6 .venv/bin/python -m pytest tests/gui/test_about_screen.py -v
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.gui.app import build_main_window
from src.gui.demo_fixtures import build_demo_3x3_snapshot
from src.gui.navigation.screen_router import ScreenId
from src.gui.project_info import (
    GITHUB_REPO_URL,
    PROJECT_INTRO_PARAGRAPHS,
    TEAM_MEMBERS,
    TECH_SPECS,
    YOUTUBE_DEMO_URL,
    is_valid_external_url,
)
from src.gui.screens.about_screen import AboutScreen


def test_main_menu_replaces_how_to_play_with_about_button_preserving_geometry(qtbot):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    menu = window.main_menu_screen
    assert menu.play_button.text() == "Chơi ngay — Mở Kho Hồ Sơ"
    assert menu.about_button.text() == "Giới thiệu"
    assert menu.exit_button.text() == "Thoát ứng dụng"
    assert menu.about_button.minimumWidth() == menu.play_button.minimumWidth() == 300
    assert menu.about_button.minimumHeight() == 46
    assert menu.about_button.variant == "secondary"

    # Clicking About opens AboutScreen (and does NOT open HowToPlayDialog)
    menu.about_button.click()
    assert window.current_screen is ScreenId.ABOUT
    assert window._active_help_dialog is None
    window.close()


def test_about_screen_displays_project_overview_tech_specs_and_five_members(qtbot):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.show_about()
    window.show()
    qtbot.waitExposed(window)

    about = window.about_screen
    assert not about.logo_view.is_missing
    assert not about.emblem_view.is_missing

    all_text = "\n".join(lbl.text() for lbl in about.findChildren(QLabel))

    assert "GIỚI THIỆU GRIDUCTIVE SOLVER" in all_text
    assert "GRIDUCTIVE SOLVER" in all_text
    assert "Hồ Sơ Phá Án" in all_text
    for para in PROJECT_INTRO_PARAGRAPHS:
        assert para in all_text

    # Technology specs table was intentionally removed from AboutScreen for a cleaner dossier
    assert "THÔNG TIN KỸ THUẬT" not in all_text

    assert len(about.member_cards) == 5
    expected_roster = [
        ("24122015", "Mai Hoàng Hiệp"),
        ("24122022", "Nguyễn Hoài Phước"),
        ("24122035", "Phan Nguyễn Gia Huy"),
        ("24122009", "Phan Thế Phong"),
        ("24122051", "Nguyễn Đức Tài"),
    ]
    assert len(TEAM_MEMBERS) == 5
    for mssv, name in expected_roster:
        assert mssv in all_text
        assert name in all_text

    window.close()


def test_about_screen_github_and_youtube_link_behavior(qtbot):
    opened_urls: list[str] = []

    # Default repository state: GitHub enabled with exact URL; YouTube disabled (None)
    assert GITHUB_REPO_URL == "https://github.com/hoanghiep06/Griductive_Solver"
    assert YOUTUBE_DEMO_URL is None

    about = AboutScreen(url_opener=lambda u: (opened_urls.append(u) or True))
    qtbot.addWidget(about)

    assert about.github_button.isEnabled()
    assert about.github_button.text() == "Mã nguồn GitHub"
    about.github_button.click()
    assert opened_urls == [GITHUB_REPO_URL]

    # YouTube has no URL yet -> disabled with honest label, never opens placeholder/homepage
    assert not about.youtube_button.isEnabled()
    assert "Chưa cập nhật" in about.youtube_button.text()
    about.youtube_button.click()
    assert opened_urls == [GITHUB_REPO_URL]

    # Invalid URL stays disabled
    about.set_youtube_url("not-a-valid-url")
    assert not about.youtube_button.isEnabled()
    assert is_valid_external_url("not-a-valid-url") is False

    # Valid future URL enables button and opens cleanly
    demo_url = "https://youtu.be/exampleDemo123"
    about.set_youtube_url(demo_url)
    assert about.youtube_button.isEnabled()
    assert about.youtube_button.text() == "Video minh họa"
    about.youtube_button.click()
    assert opened_urls == [GITHUB_REPO_URL, demo_url]


def test_about_navigation_back_escape_repeat_and_preserves_gameplay_state(qtbot):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    # Load a 3x3 board on GameplayScreen first to verify opening About never resets it
    snap3 = build_demo_3x3_snapshot()
    window.show_gameplay(snap3)
    window.set_selection("C1")
    assert window.gameplay_screen.game_board.card_count == 9
    assert window.gameplay_screen.game_board.selected_cell_id == "C1"

    # Return to Main Menu and repeatedly open/close About via Back button and Esc
    window.show_main_menu()
    about_instance = window.about_screen

    for _ in range(3):
        window.main_menu_screen.about_button.click()
        assert window.current_screen is ScreenId.ABOUT
        assert window.about_screen is about_instance  # Single instance reused
        window.about_screen.back_button.click()
        assert window.current_screen is ScreenId.MAIN_MENU

    # Esc key returns to Main Menu from AboutScreen
    window.main_menu_screen.about_button.click()
    assert window.current_screen is ScreenId.ABOUT
    qtbot.keyClick(window.about_screen, Qt.Key.Key_Escape)
    assert window.current_screen is ScreenId.MAIN_MENU

    # Gameplay board & selection remained untouched
    assert window.gameplay_screen.game_board.card_count == 9
    assert window.gameplay_screen.game_board.selected_cell_id == "C1"

    # Play & Exit still function properly
    window.main_menu_screen.play_button.click()
    assert window.current_screen is ScreenId.LEVEL_SELECTION

    window.show_main_menu()
    with qtbot.waitSignal(window.exit_requested, timeout=1000):
        window.main_menu_screen.exit_button.click()


@pytest.mark.parametrize("width,height", [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
def test_about_screen_responsive_across_target_resolutions(qtbot, width, height):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show_about()
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()

    about = window.about_screen
    assert about.back_button.isVisible()
    assert about.github_button.isVisible()
    assert about.youtube_button.isVisible()
    assert about.emblem_view.width() == 82 and about.emblem_view.height() == 82
    assert about.logo_view.height() >= 80
    window.close()
