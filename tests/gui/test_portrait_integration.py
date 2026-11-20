"""Comprehensive automated tests for Character Portrait Integration (Phase J1–J5).

Covers:
    - J1. Manifest & Asset Integrity Tests (46 PNGs, 12 professions, 250 mappings across 15
      official cases, 0 missing PNGs, 0 path traversal, 0 duplicate portraits inside any
      single puzzle, exact cross-check against official public character data, and
      non-destructive cleaned derivatives in assets/characters/portraits_clean/).
    - J2. PortraitRegistry Tests ((puzzle_id, cell_id) resolution, distinct portraits across
      puzzles for same cell_id and same character_name, MOCK_* exclusion,
      expected_name/expected_profession mismatch rejection + warning, path traversal
      rejection, missing key / bad file graceful fallback, 2-tier QPixmap cache consistency
      & clear_cache_if_needed, and zero solver/engine imports).
    - J3. CharacterCard Portrait Rendering Tests (has_portrait True on official cards in both
      HIDDEN and REVEALED states, HIDDEN never leaks verdict in tooltip or state, REVEALED
      preserves same portrait path/pixmap, fallback initials medallion when portrait_pixmap=None,
      responsive display modes EXPANDED / STANDARD / COMPACT, and offscreen rendering).
    - J4. Animation & Interaction Regression with Portraits (3D perspective card flip preserves
      portrait before/at/after 90° midpoint without mirroring, emits animation_finished once,
      cancel_animations emits animation_cancelled without animation_finished, reduced_motion,
      highlight_cells glow, hover, selection, and same-topology board switch).
    - J5. Full GUI Screen & Panel Regression with Official Public Roster Demo (MainMenu,
      LevelSelection 15 official cases, Gameplay 3x3/4x4/5x5, About, Results, CluePanel,
      DeductionPanel, ActionBar, ProgressPanel).
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from src.gui.animations import MotionConfig, compute_flip_frame
from src.gui.app import build_main_window
from src.gui.assets import (
    PortraitMappingEntry,
    PortraitRegistry,
    PortraitValidationReport,
    default_portrait_registry,
)
from src.gui.components.character_card import CardDisplayMode, CharacterCard
from src.gui.demo_fixtures import (
    OFFICIAL_PUZZLE_IDS,
    build_demo_4x4_snapshot,
    build_official_public_level_catalog,
    build_official_public_snapshot,
)
from src.gui.grid_view import GameBoard
from src.gui.view_models import AnimationToken, CardVisibility, PublicCharacterView


REPO_ROOT = Path(__file__).resolve().parents[2]
CHARACTERS_DIR = REPO_ROOT / "assets" / "characters"
MANIFEST_PATH = CHARACTERS_DIR / "portrait_manifest.json"
PORTRAITS_ORIG_DIR = CHARACTERS_DIR / "portraits"
PORTRAITS_CLEAN_DIR = CHARACTERS_DIR / "portraits_clean"
PUZZLES_DIR = REPO_ROOT / "puzzles"


def _render_card_to_image(card: CharacterCard) -> QImage:
    rect = card.boundingRect()
    w = max(1, int(rect.width()))
    h = max(1, int(rect.height()))
    image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    card.paint(painter, None, None)
    painter.end()
    return image


# ---------------------------------------------------------------------------
# J1. MANIFEST & ASSET INTEGRITY TESTS
# ---------------------------------------------------------------------------


def test_j1_manifest_counts_and_structure():
    assert MANIFEST_PATH.is_file(), f"Missing manifest: {MANIFEST_PATH}"
    reg = PortraitRegistry(prefer_cleaned=True)
    report: PortraitValidationReport = reg.validate_mapping()

    assert report.is_valid, f"Manifest validation errors: {report.errors}"
    assert report.portrait_count == 46
    assert report.slot_count == 250
    assert report.puzzle_count == 15
    assert report.profession_count == 12
    assert len(report.errors) == 0
    assert len(report.puzzles_by_size[3]) == 5
    assert len(report.puzzles_by_size[4]) == 5
    assert len(report.puzzles_by_size[5]) == 5


def test_j1_original_and_cleaned_46_pngs_exist_and_have_valid_dimensions(qapp):
    orig_pngs = sorted(PORTRAITS_ORIG_DIR.glob("*.png"))
    clean_pngs = sorted(PORTRAITS_CLEAN_DIR.glob("*.png"))

    assert len(orig_pngs) == 46
    assert len(clean_pngs) == 46
    assert [p.name for p in orig_pngs] == [p.name for p in clean_pngs]

    for png in orig_pngs + clean_pngs:
        img = QImage(str(png))
        assert not img.isNull(), f"Corrupt PNG: {png}"
        assert img.width() == 512 and img.height() == 512, f"Expected 512x512 for {png}, got {img.width()}x{img.height()}"
        assert img.hasAlphaChannel(), f"Expected RGBA alpha channel for {png}"


def test_j1_15_official_puzzles_grid_distribution_and_zero_intra_puzzle_duplicates():
    reg = PortraitRegistry()
    reg.load_manifest()

    puzzles_by_size = {3: [], 4: [], 5: []}
    for pid in OFFICIAL_PUZZLE_IDS:
        entries = reg.list_puzzle_mappings(pid)
        assert len(entries) in (9, 16, 25)
        grid_size = int(pid[0])
        assert len(entries) == grid_size * grid_size
        puzzles_by_size[grid_size].append(pid)

        # Ensure every card within a puzzle has a distinct portrait file
        files = [e.portrait_file for e in entries]
        assert len(set(files)) == len(files), f"Duplicate portrait inside puzzle {pid}: {files}"

    assert len(puzzles_by_size[3]) == 5
    assert len(puzzles_by_size[4]) == 5
    assert len(puzzles_by_size[5]) == 5


def test_j1_guard_7_variants_in_5x5_02_and_baker_5_variants_in_5x5_05():
    reg = PortraitRegistry()
    reg.load_manifest()

    # 5x5_02 has 7 Guards -> must use all 7 distinct Guard variants
    entries_5x5_02 = reg.list_puzzle_mappings("5x5_02")
    guards_5x5_02 = [e for e in entries_5x5_02 if e.profession == "Guard"]
    assert len(guards_5x5_02) == 7
    guard_files = {Path(e.portrait_file).name for e in guards_5x5_02}
    assert guard_files == {f"prof_guard_v0{i}.png" for i in range(1, 8)}

    # 5x5_05 has 5 Bakers -> must use all 5 distinct Baker variants
    entries_5x5_05 = reg.list_puzzle_mappings("5x5_05")
    bakers_5x5_05 = [e for e in entries_5x5_05 if e.profession == "Baker"]
    assert len(bakers_5x5_05) == 5
    baker_files = {Path(e.portrait_file).name for e in bakers_5x5_05}
    assert baker_files == {f"prof_baker_v0{i}.png" for i in range(1, 6)}


def test_j1_manifest_matches_official_puzzle_public_character_data_100_percent():
    """Verify (in test only) that portrait_manifest.json matches public character fields of all 15 puzzles."""
    reg = PortraitRegistry()
    reg.load_manifest()

    public_roster: dict[tuple[str, str], tuple[str, str]] = {}
    for pid in OFFICIAL_PUZZLE_IDS:
        pfile = PUZZLES_DIR / f"{pid}.json"
        assert pfile.is_file()
        raw = json.loads(pfile.read_text(encoding="utf-8"))
        assert raw["puzzle_id"] == pid
        for ch in raw["characters"]:
            cell_id = ch["id"]
            entry = reg.get_mapping(pid, cell_id)
            assert entry is not None, f"Missing manifest mapping for ({pid}, {cell_id})"
            assert entry.character_name == ch["name"]
            assert entry.profession == ch["profession"]
            public_roster[(pid, cell_id)] = (ch["name"], ch["profession"])

    assert len(public_roster) == 250
    report = reg.validate_mapping(public_roster=public_roster)
    assert report.is_valid, f"Public roster cross-check failed: {report.errors}"


# ---------------------------------------------------------------------------
# J2. PORTRAIT REGISTRY TESTS
# ---------------------------------------------------------------------------


def test_j2_exact_lookup_by_puzzle_id_and_cell_id():
    reg = PortraitRegistry(prefer_cleaned=True)

    # ("3x3_01", "A1") -> Abel, Doctor -> prof_doctor_v01.png
    entry_3x3 = reg.get_mapping("3x3_01", "A1")
    assert isinstance(entry_3x3, PortraitMappingEntry)
    assert entry_3x3.character_name == "Abel"
    assert entry_3x3.profession == "Doctor"
    assert entry_3x3.portrait_file == "prof_doctor_v01.png"

    path_3x3 = reg.get_portrait_path(
        "3x3_01", "A1", expected_name="Abel", expected_profession="Doctor"
    )
    assert path_3x3 is not None
    assert path_3x3.name == "prof_doctor_v01.png"
    assert path_3x3.parent == PORTRAITS_CLEAN_DIR

    # ("5x5_01", "A1") -> Abel, Florist -> prof_florist_v01.png
    # ("5x5_05", "A1") -> Abel, Engineer -> prof_engineer_v01.png
    # Proves same character_name ("Abel") and same cell_id ("A1") resolve to different portraits per puzzle_id!
    path_5x5_01 = reg.get_portrait_path(
        "5x5_01", "A1", expected_name="Abel", expected_profession="Florist"
    )
    path_5x5_05 = reg.get_portrait_path(
        "5x5_05", "A1", expected_name="Abel", expected_profession="Engineer"
    )
    assert path_5x5_01 is not None and path_5x5_01.name == "prof_florist_v01.png"
    assert path_5x5_05 is not None and path_5x5_05.name == "prof_engineer_v01.png"
    assert len({path_3x3, path_5x5_01, path_5x5_05}) == 3


def test_j2_mock_puzzle_ids_never_map_to_official_portraits(qapp):
    reg = PortraitRegistry()
    for mock_id in ("MOCK_3x3_01", "MOCK_4x4_02", "MOCK_5x5_01", "mock_3x3_01", ""):
        assert reg.get_mapping(mock_id, "A1") is None
        assert reg.get_portrait_path(mock_id, "A1") is None
        assert reg.get_portrait(mock_id, "A1", size=(120, 120)) is None


def test_j2_metadata_mismatch_returns_none_and_logs_warning(caplog):
    reg = PortraitRegistry()

    with caplog.at_level(logging.WARNING):
        # Wrong character name
        res_name = reg.get_portrait_path(
            "3x3_01", "A1", expected_name="WrongName", expected_profession="Doctor"
        )
        assert res_name is None
        assert "name mismatch" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        # Wrong profession
        res_prof = reg.get_portrait_path(
            "3x3_01", "A1", expected_name="Abel", expected_profession="Guard"
        )
        assert res_prof is None
        assert "profession mismatch" in caplog.text


def test_j2_missing_key_and_invalid_inputs_fallback_safely(qapp):
    reg = PortraitRegistry()
    assert reg.get_portrait_path("9x9_99", "A1") is None
    assert reg.get_portrait_path("3x3_01", "Z9") is None
    assert reg.get_portrait("9x9_99", "Z9", size=(100, 100)) is None


def test_j2_path_traversal_guard_rejects_outside_paths(tmp_path):
    bad_manifest = tmp_path / "portrait_manifest.json"
    bad_manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "portrait_count": 1,
                "puzzle_count": 1,
                "slot_count": 1,
                "assets": [
                    {
                        "filename": "../../etc/passwd",
                        "profession": "Doctor",
                        "variant": 1,
                    }
                ],
                "mapping": [
                    {
                        "portrait_slot_id": "3x3_01_A1",
                        "puzzle_id": "3x3_01",
                        "cell_id": "A1",
                        "character_name": "Abel",
                        "profession": "Doctor",
                        "portrait_file": "../../etc/passwd",
                        "portrait_path": "portraits/../../etc/passwd",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    reg = PortraitRegistry(characters_root=tmp_path)
    report = reg.validate_mapping()
    assert not report.is_valid
    assert any("Unsafe" in err for err in report.errors)
    assert reg.get_portrait_path("3x3_01", "A1") is None


def test_j2_two_tier_pixmap_cache_and_clear_cache(qapp):
    reg = PortraitRegistry()
    reg.clear_cache_if_needed()
    assert reg.cached_base_count == 0
    assert reg.cached_scaled_count == 0

    pix1 = reg.get_portrait("3x3_01", "A1", size=(160, 160))
    assert pix1 is not None and not pix1.isNull()
    assert reg.cached_base_count == 1
    assert reg.cached_scaled_count == 1

    # Second request for same size reuses cache
    pix2 = reg.get_portrait("3x3_01", "A1", size=(160, 160))
    assert pix2 is not None
    assert reg.cached_base_count == 1
    assert reg.cached_scaled_count == 1

    # Find another (puzzle_id, cell_id) slot that shares prof_doctor_v01.png
    other_slot = next(
        k
        for k, v in reg.mappings.items()
        if v.portrait_file == "prof_doctor_v01.png" and k != ("3x3_01", "A1")
    )
    pix3 = reg.get_portrait(other_slot[0], other_slot[1], size=(160, 160))
    assert pix3 is not None
    assert reg.cached_base_count == 1
    assert reg.cached_scaled_count == 1

    # Different target size adds 1 scaled entry but reuses base 512x512 entry
    pix4 = reg.get_portrait("3x3_01", "A1", size=(112, 112))
    assert pix4 is not None
    assert reg.cached_base_count == 1
    assert reg.cached_scaled_count == 2

    reg.clear_cache_if_needed()
    assert reg.cached_base_count == 0
    assert reg.cached_scaled_count == 0


def test_j2_zero_solver_or_engine_imports_and_no_puzzle_json_reads_in_gui():
    gui_dir = REPO_ROOT / "src" / "gui"
    forbidden_modules = {"src.core", "src.solvers", "src.encoder", "src.agent"}
    for py_file in gui_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for mod in forbidden_modules:
                        assert not alias.name.startswith(mod), f"Forbidden import {alias.name} in {py_file}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for mod in forbidden_modules:
                    assert not node.module.startswith(mod), f"Forbidden import {node.module} in {py_file}"

    # Verify portrait_registry, character_card, grid_view, and demo_fixtures never touch hidden_solution
    for rel in (
        "assets/portrait_registry.py",
        "components/character_card.py",
        "grid_view.py",
        "demo_fixtures.py",
    ):
        text = (gui_dir / rel).read_text(encoding="utf-8")
        tree = ast.parse(text, filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                assert "hidden_solution" not in ast.unparse(node)


# ---------------------------------------------------------------------------
# J3. CHARACTER CARD PORTRAIT RENDERING TESTS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "puzzle_id,expected_mode",
    [
        ("3x3_01", CardDisplayMode.EXPANDED),
        ("4x4_01", CardDisplayMode.STANDARD),
        ("5x5_01", CardDisplayMode.COMPACT),
    ],
)
def test_j3_gameboard_assigns_portraits_for_official_3x3_4x4_5x5(qtbot, puzzle_id, expected_mode):
    board = GameBoard()
    qtbot.addWidget(board)
    snap = build_official_public_snapshot(puzzle_id, include_demo_reveals=True)
    board.set_board(snap)

    assert board.display_mode is expected_mode
    hidden_count = 0
    revealed_count = 0

    for ch in snap.characters:
        card = board.cards_by_id[ch.cell_id]
        assert card.has_portrait, f"Expected portrait on ({puzzle_id}, {ch.cell_id})"
        assert card.portrait_pixmap is not None and not card.portrait_pixmap.isNull()
        assert card.portrait_path is not None and Path(card.portrait_path).is_file()

        if card.is_revealed:
            revealed_count += 1
        else:
            hidden_count += 1
            # Hidden card must NEVER leak verdict in state or tooltip
            assert card.public_data.verdict is None
            tip = card.toolTip()
            assert "CRIMINAL" not in tip
            assert "INNOCENT" not in tip
            assert "Chưa chứng minh" in tip

        # Offscreen render check
        img = _render_card_to_image(card)
        assert not img.isNull()

    assert hidden_count > 0
    assert revealed_count > 0


def test_j3_hidden_and_revealed_share_identical_portrait_and_frame_geometry(qapp):
    reg = default_portrait_registry()
    pix = reg.get_portrait("3x3_01", "A1", size=(216, 216))
    path = reg.get_portrait_path("3x3_01", "A1")

    hidden_ch = PublicCharacterView(
        cell_id="A1",
        name="Abel",
        profession="Doctor",
        row=0,
        col=0,
        visibility=CardVisibility.HIDDEN,
        verdict=None,
        has_public_clue=False,
    )
    revealed_ch = PublicCharacterView(
        cell_id="A1",
        name="Abel",
        profession="Doctor",
        row=0,
        col=0,
        visibility=CardVisibility.REVEALED,
        verdict="INNOCENT",
        has_public_clue=True,
    )

    card_hidden = CharacterCard(
        hidden_ch,
        display_mode=CardDisplayMode.EXPANDED,
        portrait_pixmap=pix,
        portrait_path=str(path),
    )
    card_revealed = CharacterCard(
        revealed_ch,
        display_mode=CardDisplayMode.EXPANDED,
        portrait_pixmap=pix,
        portrait_path=str(path),
    )

    assert card_hidden.has_portrait and card_revealed.has_portrait
    assert card_hidden.portrait_path == card_revealed.portrait_path
    rect_hidden: QRectF = card_hidden._compute_portrait_frame_rect(card_hidden.boundingRect())
    rect_revealed: QRectF = card_revealed._compute_portrait_frame_rect(card_revealed.boundingRect())
    assert rect_hidden == rect_revealed


def test_j3_fallback_initials_medallion_when_portrait_is_none(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    mock_snap = build_demo_4x4_snapshot()
    board.set_board(mock_snap)

    for cell_id, card in board.cards_by_id.items():
        assert not card.has_portrait, f"MOCK card {cell_id} must use initials fallback"
        assert card.portrait_pixmap is None
        img = _render_card_to_image(card)
        assert not img.isNull()


# ---------------------------------------------------------------------------
# J4. ANIMATION & INTERACTION REGRESSION WITH PORTRAITS
# ---------------------------------------------------------------------------


def test_j4_3d_card_flip_preserves_portrait_throughout_flip_and_emits_once(qtbot):
    fast_cfg = MotionConfig(card_flip_duration=80)
    board = GameBoard(motion_config=fast_cfg)
    qtbot.addWidget(board)
    snap = build_official_public_snapshot("3x3_01", include_demo_reveals=False)
    board.set_board(snap)

    card = board.cards_by_id["B2"]
    assert not card.is_revealed
    assert card.has_portrait
    orig_path = card.portrait_path

    finished_events = []
    board.animation_finished.connect(lambda cid, tok: finished_events.append((cid, tok)))

    ch_b2 = card.public_data
    revealed_b2 = PublicCharacterView(
        cell_id="B2",
        name=ch_b2.name,
        profession=ch_b2.profession,
        row=ch_b2.row,
        col=ch_b2.col,
        visibility=CardVisibility.REVEALED,
        verdict="CRIMINAL",
        has_public_clue=True,
    )
    token = AnimationToken("sess-portrait", 1, 2, "B2")
    assert board.reveal_card("B2", revealed_b2, token) is True

    # Render while flip is active
    assert card.has_portrait and card.portrait_path == orig_path
    img_mid = _render_card_to_image(card)
    assert not img_mid.isNull()

    qtbot.waitUntil(lambda: len(finished_events) == 1, timeout=2000)
    assert finished_events[0] == ("B2", token)
    assert card.is_revealed
    assert card.has_portrait and card.portrait_path == orig_path


def test_j4_cancel_animations_and_same_topology_case_switch_refresh_portraits(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)

    snap_5x5_01 = build_official_public_snapshot("5x5_01", include_demo_reveals=False)
    board.set_board(snap_5x5_01)
    assert Path(board.cards_by_id["A1"].portrait_path).name == "prof_florist_v01.png"

    cancelled_events = []
    finished_events = []
    board.animation_cancelled.connect(lambda cid, tok: cancelled_events.append((cid, tok)))
    board.animation_finished.connect(lambda cid, tok: finished_events.append((cid, tok)))

    ch_a1 = board.cards_by_id["A1"].public_data
    revealed_a1 = PublicCharacterView(
        cell_id="A1",
        name=ch_a1.name,
        profession=ch_a1.profession,
        row=ch_a1.row,
        col=ch_a1.col,
        visibility=CardVisibility.REVEALED,
        verdict="INNOCENT",
        has_public_clue=True,
    )
    tok = AnimationToken("sess-cancel", 1, 2, "A1")
    board.reveal_card("A1", revealed_a1, tok)
    board.cancel_animations()

    assert len(cancelled_events) == 1
    assert len(finished_events) == 0

    # Switching to another 5x5 official puzzle (same_topology=True) must update portraits in-place
    snap_5x5_05 = build_official_public_snapshot("5x5_05", include_demo_reveals=False)
    board.set_board(snap_5x5_05)
    assert board.cards_by_id["A1"].public_data.profession == "Engineer"
    assert Path(board.cards_by_id["A1"].portrait_path).name == "prof_engineer_v01.png"


def test_j4_reduced_motion_and_evidence_glow_with_portraits(qtbot):
    board = GameBoard()
    qtbot.addWidget(board)
    board.set_reduced_motion(True)

    snap = build_official_public_snapshot("4x4_01", include_demo_reveals=False)
    board.set_board(snap)

    finished = []
    board.animation_finished.connect(lambda cid, tok: finished.append((cid, tok)))

    ch_c2 = board.cards_by_id["C2"].public_data
    rev_c2 = PublicCharacterView(
        cell_id="C2",
        name=ch_c2.name,
        profession=ch_c2.profession,
        row=ch_c2.row,
        col=ch_c2.col,
        visibility=CardVisibility.REVEALED,
        verdict="INNOCENT",
        has_public_clue=True,
    )
    tok = AnimationToken("sess-rm", 1, 2, "C2")
    board.reveal_card("C2", rev_c2, tok)
    qtbot.waitUntil(lambda: len(finished) == 1, timeout=500)
    assert board.cards_by_id["C2"].is_revealed
    assert board.cards_by_id["C2"].has_portrait

    # Evidence glow highlight on portrait cards
    board.highlight_cells(["A1", "C2"])
    assert board.cards_by_id["A1"].is_highlighted
    assert board.cards_by_id["C2"].is_highlighted
    board.clear_highlights()
    assert not board.cards_by_id["A1"].is_highlighted


# ---------------------------------------------------------------------------
# J5. FULL GUI SCREEN & PANEL REGRESSION WITH OFFICIAL PUBLIC ROSTER DEMO
# ---------------------------------------------------------------------------


def test_j5_main_window_official_15_case_catalog_and_screen_navigation(qtbot):
    win = build_main_window()
    qtbot.addWidget(win)
    win.show()

    # Level selection catalog in standalone demo mode lists all 15 official cases
    catalog = build_official_public_level_catalog()
    assert len(catalog) == 15
    assert [lvl.puzzle_id for lvl in catalog] == list(OFFICIAL_PUZZLE_IDS)

    # Navigate MainMenu -> LevelSelection -> Load 3x3_01 -> 4x4_01 -> 5x5_02 -> About -> Results
    win._demo_open_level_selection()
    assert win.current_screen.value == "LEVEL_SELECTION"

    for pid in ("3x3_01", "4x4_01", "5x5_02", "5x5_05"):
        win._demo_open_case_by_id(pid)
        assert win.current_screen.value == "GAMEPLAY"
        assert win.gameplay_screen.game_board.puzzle_id == pid
        assert all(c.has_portrait for c in win.gameplay_screen.game_board.cards_by_id.values())

    win.show_about()
    assert win.current_screen.value == "ABOUT"

    win._demo_open_results()
    assert win.current_screen.value == "RESULTS"
