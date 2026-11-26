"""Deterministic Phase 1 QA tests for V1.2 visual assets, registry, and design tokens.

Runs with pure Python stdlib + pytest (zero PySide6 dependency required).
Validates asset existence, PNG headers, exact dimensions (including 1440x1080
for all three revised A06 case covers), manifest consistency, CWD-independent
asset resolution, graceful missing-asset behavior, and WCAG AA contrast ratios.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from src.gui.asset_registry import (
    AssetId,
    AssetRegistry,
    CASE_COVER_BY_GRID_SIZE,
    CLUE_ICON_BY_TYPE,
    DEFAULT_REGISTRY,
    DERIVED_RELATIVE_PATHS,
    ORIGINAL_RELATIVE_PATHS,
    read_png_dimensions,
    resolve_asset,
)
from src.gui.styles.tokens import (
    ANIMATION,
    COLORS,
    GEOMETRY,
    PRIMITIVE_COLORS,
    SPACING,
    THEME,
    TYPOGRAPHY,
    contrast_ratio,
)


def test_manifest_and_all_18_original_plus_3_derived_pngs_valid():
    report = DEFAULT_REGISTRY.validate(verify_sha256=True)
    assert report.valid, f"Asset validation errors: {report.errors}"
    assert report.checked_originals == 18
    assert report.checked_derived == 3
    assert len(ORIGINAL_RELATIVE_PATHS) == 18
    assert len(DERIVED_RELATIVE_PATHS) == 3
    # Remaining original RGBA assets with NEEDS_FIX alpha warnings (A04_LOGO_WIDE, A07_CASE_CLOSED_EMBLEM);
    # A04_APP_EMBLEM was replaced with the clean user-supplied 1024x1024 cartoon detective emblem in Phase 3.
    assert len(report.warnings) == 2


def test_three_revised_case_covers_are_1440x1080():
    assert set(CASE_COVER_BY_GRID_SIZE.keys()) == {3, 4, 5}
    for grid_size in (3, 4, 5):
        res = DEFAULT_REGISTRY.resolve_case_cover(grid_size)
        assert res.exists and res.path is not None
        assert not res.used_derived
        w, h = read_png_dimensions(res.path)
        assert (w, h) == (1440, 1080), f"A06 {grid_size}x{grid_size} cover must be 1440x1080"


def test_card_front_and_back_have_identical_3_to_4_proportions():
    back = resolve_asset(AssetId.A01_CARD_BACK)
    front = resolve_asset(AssetId.A02_CARD_FRONT_TEMPLATE)
    assert back.exists and back.path is not None
    assert front.exists and front.path is not None
    bw, bh = read_png_dimensions(back.path)
    fw, fh = read_png_dimensions(front.path)
    assert (bw, bh) == (fw, fh) == (1086, 1448)
    assert pytest.approx(bw / bh, rel=1e-3) == 0.75
    assert pytest.approx(GEOMETRY.card_design_width / GEOMETRY.card_design_height, rel=1e-3) == 0.75
    assert pytest.approx(GEOMETRY.card_compact_width / GEOMETRY.card_compact_height, rel=1e-3) == 0.75


def test_all_six_core_clue_icons_available():
    expected_types = {"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST"}
    assert set(CLUE_ICON_BY_TYPE.keys()) == expected_types
    for clue_type in expected_types:
        res = DEFAULT_REGISTRY.resolve_clue_icon(clue_type)
        assert res is not None and res.exists and res.path is not None
        w, h = read_png_dimensions(res.path)
        assert w >= 200 and h >= 200
    assert DEFAULT_REGISTRY.resolve_clue_icon("UNKNOWN_EXTENSION") is None


def test_derived_alpha_cleaned_assets_preferred_by_default():
    for asset_id in (AssetId.A04_LOGO_WIDE, AssetId.A04_APP_EMBLEM, AssetId.A07_CASE_CLOSED_EMBLEM):
        clean_res = resolve_asset(asset_id, prefer_derived=True)
        orig_res = resolve_asset(asset_id, prefer_derived=False)
        assert clean_res.exists and clean_res.used_derived and clean_res.path is not None
        assert orig_res.exists and not orig_res.used_derived and orig_res.path is not None
        assert clean_res.path != orig_res.path
        assert read_png_dimensions(clean_res.path) == read_png_dimensions(orig_res.path)


def test_asset_resolution_works_from_different_working_directory(tmp_path):
    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        res = resolve_asset(AssetId.A01_CARD_BACK)
        assert res.exists and res.path is not None and res.path.is_file()
    finally:
        os.chdir(old_cwd)


def test_missing_asset_handled_gracefully(tmp_path):
    empty_registry = AssetRegistry(assets_root=tmp_path)
    res = empty_registry.resolve(AssetId.A01_CARD_BACK)
    assert not res.exists
    assert res.path is None
    assert res.warning is not None
    report = empty_registry.validate()
    assert not report.valid
    assert report.errors


def test_approval_status_not_silently_marked_approved():
    manifest = DEFAULT_REGISTRY.load_manifest()
    assert manifest["package_approval_status"] == "PENDING_FINAL_APPROVAL"
    for a in manifest["assets"]:
        if a["asset_id"] == "A04_APP_EMBLEM":
            assert a["approval_status"] == "APPROVED_BY_USER_INPUT"
        else:
            assert a["approval_status"] == "PENDING_FINAL_APPROVAL"
    assert all(d["approval_status"] == "PENDING_FINAL_APPROVAL" for d in manifest["derived_assets"])


def test_design_tokens_wcag_aa_contrast_and_invariants():
    assert PRIMITIVE_COLORS["MIDNIGHT_NAVY"] == "#101B30"
    assert PRIMITIVE_COLORS["DETECTIVE_BLUE"] == "#253F68"
    assert PRIMITIVE_COLORS["CRIMSON_RED"] == "#C83D50"
    assert PRIMITIVE_COLORS["EVIDENCE_GOLD"] == "#E4B96D"
    assert PRIMITIVE_COLORS["CLUE_CYAN"] == "#65B9E9"
    assert PRIMITIVE_COLORS["INNOCENT_TEAL"] == "#41B99A"
    assert PRIMITIVE_COLORS["STEEL_GRAY"] == "#76869C"
    assert PRIMITIVE_COLORS["PAPER_WHITE"] == "#F2F5FA"

    wcag_aa_pairs = [
        (COLORS.primary_text, COLORS.app_background),
        (COLORS.primary_text, COLORS.elevated_panel),
        (COLORS.primary_text, COLORS.card_background),
        (COLORS.secondary_text, COLORS.app_background),
        (COLORS.secondary_text, COLORS.elevated_panel),
        (COLORS.secondary_text, COLORS.card_background),
        (COLORS.disabled_text, COLORS.elevated_panel),
        (COLORS.text_on_gold, COLORS.accent_primary),
        (COLORS.text_on_crimson, COLORS.criminal_verdict),
        (COLORS.criminal_text, COLORS.elevated_panel),
        (COLORS.text_on_innocent, COLORS.innocent_verdict),
        (COLORS.innocent_text, COLORS.elevated_panel),
        (COLORS.clue_highlight, COLORS.app_background),
        (COLORS.clue_highlight, COLORS.card_background),
        (COLORS.warning, COLORS.elevated_panel),
        (COLORS.error, COLORS.elevated_panel),
    ]
    for fg, bg in wcag_aa_pairs:
        ratio = contrast_ratio(fg, bg)
        assert ratio >= 4.5, f"Contrast {fg} on {bg} is {ratio:.2f}:1 (< 4.5:1)"

    assert (SPACING.space_1, SPACING.space_2, SPACING.space_3, SPACING.space_4, SPACING.space_5, SPACING.space_6) == (
        4, 8, 12, 16, 24, 32
    )
    assert GEOMETRY.button_min_height >= 44
    assert ANIMATION.card_flip_duration_ms == 320
    assert ANIMATION.reduced_motion_duration_ms == 0
    assert TYPOGRAPHY.size_min_readable >= 10
    assert THEME.colors is COLORS
