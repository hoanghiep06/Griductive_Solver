"""Tests for Option 1 Detective Editorial Case Naming across Archive & Gameplay."""

from __future__ import annotations

import ast
from pathlib import Path

from src.gui.app import build_main_window
from src.gui.case_catalog import (
    OFFICIAL_CASE_CATALOG,
    format_case_title,
    format_gameplay_case_header,
    localize_difficulty,
)
from src.gui.demo_fixtures import build_official_public_snapshot
from src.gui.view_models import LevelSummary


def test_official_case_catalog_has_15_clean_editorial_titles():
    assert len(OFFICIAL_CASE_CATALOG) == 15
    assert format_case_title("3x3_01") == "#01 · Thư viện nửa đêm"
    assert format_case_title("4x4_03") == "#08 · Bức thư không ký tên"
    assert format_case_title("5x5_03") == "#13 · Sương mù ga trung tâm"
    assert format_case_title("5x5_05") == "#15 · Chuyên án tổng lực"

    for pid, meta in OFFICIAL_CASE_CATALOG.items():
        assert meta.case_number.startswith("#")
        assert "3x3" not in meta.name.lower()
        assert "4x4" not in meta.name.lower()
        assert "5x5" not in meta.name.lower()
        assert "3×3" not in meta.name
        assert "4×4" not in meta.name
        assert "5×5" not in meta.name
        assert pid not in meta.full_title


def test_difficulty_localization():
    assert localize_difficulty("Tutorial") == "Nhập môn"
    assert localize_difficulty("Easy") == "Dễ"
    assert localize_difficulty("Medium") == "Trung bình"
    assert localize_difficulty("Hard") == "Khó"
    assert localize_difficulty("Very Hard") == "Rất khó"
    assert localize_difficulty(None) is None


def test_level_selection_tiles_footer_and_gameplay_header(qtbot):
    window = build_main_window(demo_navigation=False)
    qtbot.addWidget(window)
    window.resize(1360, 820)
    window.show()

    catalog = [
        LevelSummary("3x3_01", format_case_title("3x3_01"), 3, "Tutorial"),
        LevelSummary("4x4_03", format_case_title("4x4_03"), 4, "Hard"),
        LevelSummary("5x5_03", format_case_title("5x5_03"), 5, "Hard"),
        LevelSummary("5x5_05", format_case_title("5x5_05"), 5, "Very Hard"),
    ]
    window.show_level_selection(catalog)
    ls = window.level_selection_screen

    tile = ls.case_tiles["5x5_03"]
    assert tile.puzzle_id == "5x5_03"
    assert tile._code_label.text() == "#13"
    assert tile._title_label.text() == "Sương mù ga trung tâm"
    assert tile._meta_pill.text() == "Khó"
    assert not tile._id_label.isVisible()

    ls.set_selected_puzzle("5x5_03")
    footer_text = ls._selection_label.text()
    assert "#13 · Sương mù ga trung tâm" in footer_text
    assert "5×5 · Khó" in footer_text
    assert "[5x5_03]" not in footer_text

    # Gameplay top bar renders clean editorial case heading
    snap = build_official_public_snapshot("5x5_03")
    window.gameplay_screen.set_board(snap)
    assert (
        window.gameplay_screen._case_label.text()
        == format_gameplay_case_header("5x5_03", 5)
        == "Hồ sơ #13 · Sương mù ga trung tâm  ·  Bàn cờ 5×5"
    )
    window.close()


def test_case_catalog_module_has_zero_domain_imports():
    path = Path("src/gui/case_catalog.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = ("src.core", "src.solvers", "src.encoder", "src.agent", "src.controller")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(forbidden)
