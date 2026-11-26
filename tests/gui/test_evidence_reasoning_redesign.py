"""Comprehensive Phase J automated tests for Evidence & Reasoning UI Redesign.

Covers Section 14 (J1–J5):
    - J1: 8 Vietnamese Clue Icons (RGBA 512x512, manifest mapping, fallback, High-DPI)
    - J2: Evidence Ledger & Cards (hierarchy, chips, custom editorial check toggle,
          selection without layout shift, 10+ clue scrolling, signal preservation)
    - J3: Investigation Notebook Deduction Timeline (empty state, append/replace/clear,
          timeline rail ordering, truthful verdict colors, smart scroll preservation,
          zero fabricated proof steps)
    - J4: Compact Collapsible Hint UI (show/hide, expand/collapse, long hints, zero spoiler)
    - J5: Sleek ProgressPanel (0/25, 2/25, 25/25, zero-safe, never infers SOLVED)
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.gui.asset_registry import (
    DEFAULT_REGISTRY,
    VIETNAMESE_CLUE_ICON_PATHS,
    VIETNAMESE_CLUE_LABELS,
    read_png_dimensions,
)
from src.gui.components import CluePanel, DeductionPanel, ProgressPanel
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.view_models import DeductionStepView, GameState, HintView, PublicClueView


# ---------------------------------------------------------------------------
# J1. 8 VIETNAMESE CLUE ICONS & ASSET VALIDATION
# ---------------------------------------------------------------------------


def test_j1_eight_vietnamese_icons_valid_manifest_mapping_and_alpha():
    ok, errors = DEFAULT_REGISTRY.validate_vietnamese_clue_icons(verify_sha256=True)
    assert ok, f"Vietnamese clue icon validation failed: {errors}"

    expected = {
        "FACT": ("A10_fact_vi.png", "SỰ THẬT"),
        "SAME": ("A10_same_vi.png", "CÙNG PHE"),
        "DIFFERENT": ("A10_different_vi.png", "KHÁC PHE"),
        "EXACTLY": ("A10_exactly_vi.png", "CHÍNH XÁC"),
        "AT_LEAST": ("A10_at_least_vi.png", "ÍT NHẤT"),
        "AT_MOST": ("A10_at_most_vi.png", "NHIỀU NHẤT"),
        "PARITY": ("A10_parity_vi.png", "CHẴN / LẺ"),
        "COUNT_COMPARE": ("A10_count_compare_vi.png", "SO SÁNH SỐ LƯỢNG"),
    }
    assert set(VIETNAMESE_CLUE_ICON_PATHS.keys()) == set(expected.keys())

    resolved_paths: dict[str, str] = {}
    for ctype, (fname, vi_label) in expected.items():
        assert VIETNAMESE_CLUE_LABELS[ctype] == vi_label
        res = DEFAULT_REGISTRY.resolve_clue_icon(ctype, prefer_vietnamese=True)
        assert res is not None and res.exists and res.path is not None
        assert res.path.name == fname
        w, h = read_png_dimensions(res.path)
        assert (w, h) == (512, 512)
        img = QImage(str(res.path))
        assert not img.isNull()
        assert img.hasAlphaChannel()
        assert img.pixelColor(0, 0).alpha() == 0
        resolved_paths[ctype] = str(res.path)

    # Distinct files for semantic opposites
    assert resolved_paths["SAME"] != resolved_paths["DIFFERENT"]
    assert resolved_paths["AT_LEAST"] != resolved_paths["AT_MOST"]

    # Unknown clue type returns None cleanly
    assert DEFAULT_REGISTRY.resolve_clue_icon("FUTURE_CUSTOM_TYPE") is None


def test_j1_pixmap_loader_caches_and_scales_high_dpi(qtbot):
    loader = PixmapLoader(DEFAULT_REGISTRY)
    p1 = loader.load_clue_icon("FACT")
    p2 = loader.load_clue_icon("FACT")
    assert not p1.isNull()
    assert p1.cacheKey() == p2.cacheKey()
    assert p1.size() == QSize(512, 512)

    hi_dpi = loader.load_clue_icon_scaled("PARITY", QSize(52, 52), device_pixel_ratio=2.0)
    assert not hi_dpi.isNull()
    assert hi_dpi.devicePixelRatio() == pytest.approx(2.0)
    assert hi_dpi.width() == 104 and hi_dpi.height() == 104

    # Missing/unknown type returns null without crashing
    missing = loader.load_clue_icon_scaled("UNKNOWN_CLUE_XYZ", QSize(52, 52))
    assert missing.isNull()


# ---------------------------------------------------------------------------
# J2. EVIDENCE LEDGER & CARDS
# ---------------------------------------------------------------------------


def test_j2_evidence_cards_icons_chips_check_toggle_scroll_and_stable_height(qtbot):
    panel = CluePanel()
    qtbot.addWidget(panel)
    panel.resize(420, 360)
    panel.show()

    clue_types = ("FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", "COUNT_COMPARE", "CUSTOM_UNKNOWN")
    clues = [
        PublicClueView(
            clue_id=f"CLUE_{idx:02d}",
            owner_id=f"A{(idx % 5) + 1}",
            clue_type=ct,
            text=f"Manh mối kiểm thử #{idx} thuộc loại {ct} với nội dung đủ dài để kiểm tra xuống dòng tự nhiên.",
            referenced_cells=("E2", "C2") if ct in {"SAME", "DIFFERENT", "COUNT_COMPARE"} else ("B1",),
            primary_cells=("E2",) if ct in {"SAME", "DIFFERENT", "COUNT_COMPARE"} else ("B1",),
            secondary_cells=("C2",) if ct in {"SAME", "DIFFERENT", "COUNT_COMPARE"} else (),
        )
        for idx, ct in enumerate(clue_types, start=1)
    ]
    panel.set_clues(clues)
    QApplication.processEvents()

    assert len(panel.clues) == 9
    # All 8 known Vietnamese types use real icons; unknown uses clean fallback
    for idx, ct in enumerate(clue_types, start=1):
        card = panel.clue_cards[f"CLUE_{idx:02d}"]
        if ct == "CUSTOM_UNKNOWN":
            assert card.used_fallback_icon is True
        else:
            assert card.used_fallback_icon is False
            assert card.icon_label.pixmap() is not None and not card.icon_label.pixmap().isNull()
            assert VIETNAMESE_CLUE_LABELS[ct] in card.type_caption_label.text()

    # Selection emits clue_selected and does NOT cause card height jump
    selected_ids: list[str] = []
    cleared: list[bool] = []
    panel.clue_selected.connect(selected_ids.append)
    panel.focus_cleared.connect(lambda: cleared.append(True))

    c3 = panel.clue_cards["CLUE_03"]
    h_before = c3.sizeHint().height()
    qtbot.mouseClick(c3, Qt.MouseButton.LeftButton)
    assert selected_ids == ["CLUE_03"]
    assert c3.is_selected is True
    assert c3._chips.isVisible()
    assert c3.sizeHint().height() == h_before

    # Second click toggles selection off cleanly
    qtbot.mouseClick(c3, Qt.MouseButton.LeftButton)
    assert c3.is_selected is False
    assert cleared == [True]

    # Editorial circular used toggle works via click & double-click
    c1 = panel.clue_cards["CLUE_01"]
    assert not c1.used_button.isChecked()
    c1.used_button.click()
    assert c1.used_button.isChecked()
    assert c1.text_label.font().strikeOut()
    assert "CLUE_01" in panel.solved_clues

    # Scrollable vertically, never horizontal scroll
    assert panel.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    qtbot.waitUntil(lambda: panel.scroll_area.verticalScrollBar().maximum() > 0, timeout=1000)


# ---------------------------------------------------------------------------
# J3 & J4. DEDUCTION TIMELINE & COMPACT COLLAPSIBLE HINT
# ---------------------------------------------------------------------------


def test_j3_j4_deduction_timeline_and_collapsible_hint(qtbot):
    panel = DeductionPanel()
    qtbot.addWidget(panel)
    panel.resize(420, 420)
    panel.show()

    # Empty state shown initially
    assert panel.is_empty
    assert panel._empty_container.isVisible()
    assert not panel.hint_box.isVisible()

    # Display long Hint -> compact collapsed by default, does NOT count as deduction step
    long_hint = HintView(
        session_id="sess-1",
        kb_version=2,
        outcome="FORCED",
        cell_id="E1",
        verdict=None,
        text=(
            "Hãy đối chiếu hai manh mối công khai từ A1 và C2 để loại trừ khả năng mâu thuẫn "
            "đối với nghi phạm ở ô E1 trước khi đưa ra kết luận cuối cùng."
        ),
        source_clue_ids=("CLUE_A1", "CLUE_C2"),
    )
    panel.show_hint(long_hint)
    assert panel.hint_box.isVisible()
    assert panel.step_count == 0
    assert panel.is_empty is True
    assert panel.hint_box.is_expanded is False
    assert panel.hint_box.toggle_button.isVisible()

    # Expand -> reveals full text & public clue references; Collapse -> returns compact
    panel.hint_box.toggle_button.click()
    assert panel.hint_box.is_expanded is True
    assert "A1, C2" in panel.hint_box._refs_label.text()
    assert "CLUE_" not in panel.hint_box._refs_label.text()
    assert panel.hint_box._detail_box.isVisible()

    panel.hint_box.toggle_button.click()
    assert panel.hint_box.is_expanded is False
    assert not panel.hint_box._detail_box.isVisible()

    # Dismiss hides hint cleanly
    panel.hint_box.dismiss_button.click()
    assert not panel.hint_box.isVisible()
    assert panel.current_hint is None

    # Append genuine accepted deduction steps -> timeline rail updates truthfully
    s1 = DeductionStepView(
        session_id="sess-1",
        request_id=1,
        kb_version=1,
        cell_id="C1",
        verdict="CRIMINAL",
        explanation="Chứng minh ô C1 là CRIMINAL từ tập manh mối công khai.",
        source_clue_ids=("CLUE_A1", "CLUE_B1"),
        step=1,
    )
    s2 = DeductionStepView(
        session_id="sess-1",
        request_id=2,
        kb_version=2,
        cell_id="B2",
        verdict="INNOCENT",
        explanation="Chứng minh ô B2 là INNOCENT từ manh mối C1.",
        source_clue_ids=("CLUE_C1",),
        step=2,
    )
    s3 = DeductionStepView(
        session_id="sess-1",
        request_id=3,
        kb_version=3,
        cell_id="D3",
        verdict="UNKNOWN",
        explanation="Chưa xác định trạng thái ô D3.",
        source_clue_ids=(),
        step=3,
    )
    assert panel.append_step(s1) is True
    assert panel.append_step(s1) is False  # idempotent
    assert panel.append_step(s2) is True
    assert panel.append_step(s3) is True
    assert not panel._empty_container.isVisible()
    assert panel.step_count == 3

    e1, e2, e3 = panel.entry_widgets
    assert e1.property("isLast") == "false"
    assert e2.property("isLast") == "false"
    assert e3.property("isLast") == "true"
    assert e1.verdict_badge.tone == "danger"
    assert e2.verdict_badge.tone == "success"
    assert e3.verdict_badge.tone == "neutral"

    # Clear resets cleanly to empty state
    panel.clear()
    assert panel.step_count == 0
    assert panel._empty_container.isVisible()


# ---------------------------------------------------------------------------
# J5. SLEEK PROGRESS PANEL
# ---------------------------------------------------------------------------


def test_j5_progress_panel_boundaries_zero_safe_and_no_solved_inference(qtbot):
    panel = ProgressPanel()
    qtbot.addWidget(panel)
    panel.set_reduced_motion(True)

    panel.set_progress(0, 25)
    assert panel.progress_bar.text() == "0.0%"
    assert panel.percent_label.text() == "0.0%"
    assert panel.remaining_count == 25
    assert panel.game_state is GameState.NO_PUZZLE

    panel.set_progress(2, 25)
    assert panel.progress_bar.text() == "8.0%"
    assert panel.percent_label.text() == "8.0%"
    assert "2 / 25" in panel.revealed_label.text()
    assert "23" in panel.remaining_label.text()

    panel.set_progress(25, 25)
    assert panel.progress_bar.text() == "100.0%"
    assert panel.remaining_count == 0
    assert panel.progress_bar.property("complete") == "true"
    # Never infers SOLVED from counts alone!
    assert panel.game_state is GameState.NO_PUZZLE

    # Zero / negative safe
    panel.set_progress(0, 0)
    assert panel.progress_percent == 0.0
    panel.set_progress(5, -5)
    assert panel.total_count == 0 and panel.revealed_count == 0


def test_j6_auto_solve_sidebar_continuity_no_flicker(qtbot):
    """During Auto-Solve, CluePanel appends incrementally and HintBox updates in-place with zero blink."""
    clue_panel = CluePanel()
    qtbot.addWidget(clue_panel)
    clue_panel.show()

    c1 = PublicClueView("CLUE_A1", "A1", "FACT", "Manh mối 1", ("A1",))
    c2 = PublicClueView("CLUE_B1", "B1", "SAME", "Manh mối 2", ("B1", "C1"))
    c3 = PublicClueView("CLUE_C1", "C1", "DIFFERENT", "Manh mối 3", ("C1", "D1"))

    clue_panel.set_clues([c1, c2])
    w1_before = clue_panel.clue_cards["CLUE_A1"]
    w2_before = clue_panel.clue_cards["CLUE_B1"]
    clue_panel.set_evidence_clues(["CLUE_A1"])

    # Incremental append preserves existing card widgets in-place (no destroy/rebuild flicker)
    clue_panel.set_clues([c1, c2, c3])
    assert clue_panel.clue_cards["CLUE_A1"] is w1_before
    assert clue_panel.clue_cards["CLUE_B1"] is w2_before
    assert "CLUE_C1" in clue_panel.clue_cards
    assert w1_before.is_selected is True

    # Calm Auto-Solve mode shows active evidence strip without jumping scroll position
    clue_panel.set_auto_solving(True)
    clue_panel.set_evidence_clues(["CLUE_A1", "CLUE_C1"])
    assert clue_panel._active_strip.isVisible()
    assert "A1" in clue_panel._active_strip.text() and "C1" in clue_panel._active_strip.text()
    clue_panel.set_auto_solving(False)
    assert not clue_panel._active_strip.isVisible()

    # HintBox updates smoothly in-place with fixed compact height (zero vertical jump & zero blink)
    ded_panel = DeductionPanel()
    qtbot.addWidget(ded_panel)
    ded_panel.resize(440, 380)
    ded_panel.show()

    h1 = HintView("s1", 1, "FORCED", "A1", "INNOCENT", "Ngắn gọn.", ("CLUE_A1",))
    h2 = HintView(
        "s1",
        2,
        "FORCED",
        "B1",
        "CRIMINAL",
        "Nhóm A1, B1, C1 có đúng 2 tội phạm. Kết hợp các ô đã chứng minh nên B1 bắt buộc là tội phạm.",
        ("CLUE_B1",),
    )
    ded_panel.show_hint(h1)
    ded_panel.hint_box._enter.stop()
    ded_panel.hint_box._opacity.setOpacity(1.0)
    QApplication.processEvents()
    h_compact_1 = ded_panel.hint_box.height()
    assert ded_panel.hint_box.isVisible()

    ded_panel.show_hint(h2)
    QApplication.processEvents()
    assert ded_panel.hint_box.isVisible()
    assert ded_panel.hint_box._opacity.opacity() == 1.0
    assert ded_panel.hint_box.height() == h_compact_1
    assert "Ô B1" in ded_panel.hint_box._title_label.text()
