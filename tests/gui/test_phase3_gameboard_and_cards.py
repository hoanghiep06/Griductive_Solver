"""Automated Phase 3 tests for GameBoard, CharacterCard, ClueHighlighter & A04 Emblem.

Run headlessly with:
    QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyside6 .venv/bin/python -m pytest tests/gui/test_phase3_gameboard_and_cards.py -v
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from src.gui.app import build_main_window
from src.gui.asset_registry import AssetId, DEFAULT_REGISTRY, read_png_dimensions, resolve_asset
from src.gui.components.character_card import CardDisplayMode, CharacterCard
from src.gui.demo_fixtures import (
    build_demo_3x3_snapshot,
    build_demo_4x4_snapshot,
    build_demo_5x5_snapshot,
    build_demo_snapshot,
)
from src.gui.grid_view import GameBoard
from src.gui.view_models import CardVisibility, PublicBoardSnapshot, PublicCharacterView


# ---------------------------------------------------------------------------
# 11.1. BOARD CONSTRUCTION & VALIDATION
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "grid_size,expected_count,expected_mode",
    [
        (3, 9, CardDisplayMode.EXPANDED),
        (4, 16, CardDisplayMode.STANDARD),
        (5, 25, CardDisplayMode.COMPACT),
    ],
)
def test_board_construction_for_3x3_4x4_5x5(qtbot, grid_size, expected_count, expected_mode):
    board = GameBoard()
    qtbot.addWidget(board)
    snap = build_demo_snapshot(grid_size)
    board.set_board(snap)

    assert board.grid_size == grid_size
    assert board.card_count == expected_count
    assert board.display_mode is expected_mode

    # Verify exact coordinate mapping & row-major spatial ordering (independent of input order)
    positions = set()
    for ch in snap.characters:
        card = board.cards_by_id[ch.cell_id]
        pos = (round(card.pos().x(), 2), round(card.pos().y(), 2))
        assert pos not in positions
        positions.add(pos)

    # Check A1 is strictly top-left of B1 and A2
    assert board.cards_by_id["A1"].pos().x() < board.cards_by_id["B1"].pos().x()
    assert board.cards_by_id["A1"].pos().y() == board.cards_by_id["B1"].pos().y()
    assert board.cards_by_id["A1"].pos().y() < board.cards_by_id["A2"].pos().y()


def test_board_ignores_input_order_and_positions_by_row_col(qtbot):
    snap = build_demo_3x3_snapshot()
    reversed_snap = PublicBoardSnapshot(
        session_id=snap.session_id,
        puzzle_id=snap.puzzle_id,
        grid_size=3,
        kb_version=1,
        characters=tuple(reversed(snap.characters)),
    )
    board = GameBoard()
    qtbot.addWidget(board)
    board.set_board(reversed_snap)
    assert board.cards_by_id["A1"].pos().x() < board.cards_by_id["C1"].pos().x()
    assert board.cards_by_id["A1"].pos().y() < board.cards_by_id["A3"].pos().y()


def test_board_rejects_invalid_snapshots(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    valid = build_demo_3x3_snapshot()

    # Invalid grid size
    with pytest.raises(ValueError):
        PublicBoardSnapshot("s", "p", 6, 0, valid.characters)

    # Missing character
    with pytest.raises(ValueError):
        PublicBoardSnapshot("s", "p", 3, 0, valid.characters[:-1])

    # Duplicate cell_id
    dup_id = list(valid.characters)
    dup_id[-1] = PublicCharacterView("A1", "Dup", "Job", 2, 2, CardVisibility.HIDDEN)
    with pytest.raises(ValueError):
        PublicBoardSnapshot("s", "p", 3, 0, tuple(dup_id))

    # Duplicate coordinates
    dup_coord = list(valid.characters)
    dup_coord[-1] = PublicCharacterView("C3", "Dup", "Job", 0, 0, CardVisibility.HIDDEN)
    with pytest.raises(ValueError):
        PublicBoardSnapshot("s", "p", 3, 0, tuple(dup_coord))

    # Out-of-bounds coordinates
    oob = list(valid.characters)
    oob[-1] = PublicCharacterView("C3", "OOB", "Job", 3, 2, CardVisibility.HIDDEN)
    with pytest.raises(ValueError):
        PublicBoardSnapshot("s", "p", 3, 0, tuple(oob))

    # Hidden character leaking verdict must be rejected
    with pytest.raises(ValueError):
        PublicCharacterView("C1", "Leak", "Job", 0, 2, CardVisibility.HIDDEN, verdict="CRIMINAL")

    # Revealed character without verdict must be rejected
    with pytest.raises(ValueError):
        PublicCharacterView("C1", "Bad", "Job", 0, 2, CardVisibility.REVEALED, verdict=None)


# ---------------------------------------------------------------------------
# 11.2. CHARACTER CARD RENDERING & PUBLIC DATA BOUNDARIES
# ---------------------------------------------------------------------------


def test_character_card_hidden_vs_revealed_criminal_and_innocent(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    board.set_board(build_demo_3x3_snapshot())

    # A1 is initially revealed INNOCENT, B1 is initially revealed CRIMINAL, C1 is HIDDEN
    card_a1 = board.cards_by_id["A1"]
    card_b1 = board.cards_by_id["B1"]
    card_c1 = board.cards_by_id["C1"]

    assert card_a1.is_revealed and card_a1.public_data.verdict == "INNOCENT"
    assert card_b1.is_revealed and card_b1.public_data.verdict == "CRIMINAL"
    assert not card_c1.is_revealed and card_c1.public_data.verdict is None

    # Verify A01/A02 real pixmaps are loaded and shared across cards
    assert card_c1._card_back_pixmap is not None and not card_c1._card_back_pixmap.isNull()
    assert card_a1._card_front_pixmap is not None and not card_a1._card_front_pixmap.isNull()
    assert card_a1._card_back_pixmap is card_c1._card_back_pixmap

    # Hidden tooltip must never mention CRIMINAL or INNOCENT
    assert "CRIMINAL" not in card_c1.toolTip()
    assert "INNOCENT" not in card_c1.toolTip()
    assert "Clara" in card_c1.toolTip()

    # Revealed tooltips reflect public verdict accurately
    assert "INNOCENT" in card_a1.toolTip()
    assert "CRIMINAL" in card_b1.toolTip()


def test_update_character_in_place_without_rebuilding_board(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    board.set_board(build_demo_3x3_snapshot())
    original_item = board.cards_by_id["C1"]

    revealed_c1 = PublicCharacterView(
        cell_id="C1",
        name="Clara",
        profession="Nhà báo",
        row=0,
        col=2,
        visibility=CardVisibility.REVEALED,
        verdict="INNOCENT",
        has_public_clue=True,
    )
    assert board.update_character(revealed_c1) is True
    assert board.cards_by_id["C1"] is original_item
    assert board.cards_by_id["C1"].is_revealed is True
    assert board.cards_by_id["C1"].public_data.verdict == "INNOCENT"

    # Unknown character update fails gracefully
    unknown = PublicCharacterView("Z9", "Ghost", "None", 0, 0, CardVisibility.HIDDEN)
    assert board.update_character(unknown) is False


# ---------------------------------------------------------------------------
# 11.3. INTERACTION: SINGLE SELECTION, HOVER, HIGHLIGHTS, NO EVENT LOOPS
# ---------------------------------------------------------------------------


def test_single_selection_hover_highlight_and_programmatic_no_loop(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    board.resize(900, 700)
    board.set_board(build_demo_3x3_snapshot())
    board.show()
    qtbot.waitExposed(board)

    received: list[str] = []
    board.card_selected.connect(received.append)

    # Simulate user click on C1 via card signal / mouse click
    c1 = board.cards_by_id["C1"]
    a1 = board.cards_by_id["A1"]

    c1.card_selected.emit("C1")
    assert board.selected_cell_id == "C1"
    assert c1.is_selected is True
    assert a1.is_selected is False
    assert received == ["C1"]

    # Selecting A1 deselects C1
    a1.card_selected.emit("A1")
    assert board.selected_cell_id == "A1"
    assert a1.is_selected is True
    assert c1.is_selected is False
    assert received == ["C1", "A1"]

    # Programmatic selection updates visual state WITHOUT emitting card_selected
    assert board.set_selected_card("B2") is True
    assert board.selected_cell_id == "B2"
    assert board.cards_by_id["B2"].is_selected is True
    assert a1.is_selected is False
    assert received == ["C1", "A1"]  # Unchanged -> zero feedback loop

    # Invalid programmatic selection handled gracefully
    assert board.set_selection("Z99") is False
    assert board.selected_cell_id == "B2"

    # Clear selection works cleanly
    board.clear_selection()
    assert board.selected_cell_id is None
    assert board.cards_by_id["B2"].is_selected is False

    # Hover does NOT reveal hidden card or alter verdict
    c1._hovered = True
    assert not c1.is_revealed and c1.public_data.verdict is None

    # Simultaneous SELECTED + HIGHLIGHTED overlays are independent
    board.set_selection("C1")
    highlighted = board.highlight_cells(["C1", "B1", "NON_EXISTENT"])
    assert set(highlighted) == {"C1", "B1"}
    assert c1.is_selected is True and c1.is_highlighted is True
    assert board.cards_by_id["B1"].is_highlighted is True
    board.clear_highlights()
    assert c1.is_selected is True and c1.is_highlighted is False


# ---------------------------------------------------------------------------
# 11.4. RESPONSIVE BOARD ACROSS TARGET RESOLUTIONS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "width,height",
    [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)],
)
@pytest.mark.parametrize("grid_size", [3, 4, 5])
def test_responsive_board_no_overlap_and_valid_geometry(qtbot, width, height, grid_size):
    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show_gameplay(build_demo_snapshot(grid_size))
    window.show()
    QApplication.processEvents()

    board = window.gameplay_screen.game_board
    assert board.width() > 0 and board.height() > 0
    assert board.card_count == grid_size * grid_size
    assert 0.65 <= board.current_scale <= 1.0

    # Verify zero overlap between card bounding rects in scene coordinates
    rects = [card.mapRectToScene(card.card_rect()) for card in board.cards_by_id.values()]
    for i, r1 in enumerate(rects):
        assert r1.width() > 0 and r1.height() > 0
        for r2 in rects[i + 1 :]:
            assert not r1.intersects(r2), f"Overlapping cards detected on {grid_size}x{grid_size}"

    window.close()


# ---------------------------------------------------------------------------
# 11.5. SECURITY / ARCHITECTURE ISOLATION
# ---------------------------------------------------------------------------


def test_phase3_gui_does_not_import_domain_or_solver_modules():
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    code = "\n".join(
        [
            "import sys",
            "from src.gui.app import create_application, build_main_window",
            "from src.gui.demo_fixtures import build_demo_snapshot",
            "app, tm = create_application([])",
            "win = build_main_window(theme_manager=tm, demo_navigation=True)",
            "for n in (3, 4, 5):",
            "    win.show_gameplay(build_demo_snapshot(n))",
            "win.close()",
            "forbidden = [m for m in sys.modules if m.startswith(('src.solvers', 'src.encoder', 'src.agent', 'src.core', 'src.controller'))]",
            "assert not forbidden, f'Forbidden imports: {forbidden}'",
            "print('PHASE3_ISOLATION_OK')",
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
    assert "PHASE3_ISOLATION_OK" in proc.stdout


# ---------------------------------------------------------------------------
# 11.6. NEW CARTOON DETECTIVE A04 APP EMBLEM TESTS
# ---------------------------------------------------------------------------


def test_new_cartoon_a04_app_emblem_and_preserved_wide_logo(qtbot):
    orig = resolve_asset(AssetId.A04_APP_EMBLEM, prefer_derived=False)
    clean = resolve_asset(AssetId.A04_APP_EMBLEM, prefer_derived=True)
    wide = resolve_asset(AssetId.A04_LOGO_WIDE, prefer_derived=False)

    assert orig.exists and orig.path is not None
    assert clean.exists and clean.path is not None
    assert wide.exists and wide.path is not None

    # New cartoon detective app emblem is 1024x1024; wide logo stays 1920x819
    assert read_png_dimensions(orig.path) == (1024, 1024)
    assert read_png_dimensions(clean.path) == (1024, 1024)
    assert read_png_dimensions(wide.path) == (1920, 819)

    # Backup of old V1.2 emblem exists
    backup = DEFAULT_REGISTRY.root / "backup" / "v1_2_original" / "A04_app_emblem_v1_2.png"
    assert backup.is_file()
    assert read_png_dimensions(backup) == (1254, 1254)

    # Manifest records new A04 version & MainWindow loads non-null windowIcon
    manifest = DEFAULT_REGISTRY.load_manifest()
    a04_entry = next(e for e in manifest["assets"] if e["asset_id"] == "A04_APP_EMBLEM")
    assert a04_entry["source_version"] == "1.3-cartoon-emblem"
    assert a04_entry["validation_status"] == "VALIDATED"

    window = build_main_window(demo_navigation=True)
    qtbot.addWidget(window)
    assert not window.windowIcon().isNull()
    window.close()
