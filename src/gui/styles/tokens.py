"""Centralized 3-layer Design Token System V2 for GRIDUCTIVE — Detective Editorial.

Pure Python configuration module (zero PySide6 / Qt runtime dependency) so both
Phase 1 validation tests and Phase 2+ QSS/QPainter modules share one single
source of truth without hardcoded hex colors or magic pixel constants.

Architecture (Design System V2 — "Detective Editorial / Modern Case Files"):
    Layer 1: PRIMITIVE_COLORS (core nocturne + warm archival paper primitives)
    Layer 2: COLORS / SPACING / GEOMETRY / TYPOGRAPHY / ANIMATION (semantic tokens)
    Layer 3: COMPONENT_TOKENS (component-level defaults)

Dual-Material Surface System:
    - Cinematic Nocturne Layer: Midnight Navy & Deep Ink for Main Menu city
      atmosphere and the interactive GameBoard stage (maximizes 3D Card Flip,
      A01/A02 artwork, Gold Selection, and Cyan Evidence Glow contrast).
    - Warm Paper Editorial Layer: Warm Paper (#F3E9D6), Pale Ivory (#FAF7F0),
      Linen (#E6DAC4), Deep Ink (#152437), Brick Red (#A6352E), and Antique
      Brass (#7C5821 / #C99D55) for About Dossier, Level Selection Case Archive,
      Gameplay Evidence/Trace Dossiers, and Results Case-Closed Sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


# ---------------------------------------------------------------------------
# Layer 1 — Primitive Color Tokens
# ---------------------------------------------------------------------------

PRIMITIVE_COLORS: Mapping[str, str] = MappingProxyType(
    {
        # Core 8 brand colors (preserved for backward compatibility & nocturne stage)
        "MIDNIGHT_NAVY": "#101B30",
        "DETECTIVE_BLUE": "#253F68",
        "CRIMSON_RED": "#C83D50",
        "EVIDENCE_GOLD": "#E4B96D",
        "CLUE_CYAN": "#65B9E9",
        "INNOCENT_TEAL": "#41B99A",
        "STEEL_GRAY": "#76869C",
        "PAPER_WHITE": "#F2F5FA",
        # Supporting dark elevation & WCAG AA dark-surface foreground steps
        "DEEP_NAVY": "#0B1220",
        "ELEVATED_NAVY": "#152238",
        "PANEL_HOVER_NAVY": "#20324D",
        "DETECTIVE_BLUE_HOVER": "#2E4D7E",
        "EVIDENCE_GOLD_BRIGHT": "#F2C14E",
        "EVIDENCE_GOLD_PRESSED": "#C99A4E",
        "CRIMSON_DARK": "#A32F40",
        "CRIMSON_TEXT": "#FF7A85",
        "INNOCENT_DARK": "#2E947A",
        "INNOCENT_TEXT": "#65D6A4",
        "SLATE_SECONDARY": "#B8C4D8",
        "SLATE_DISABLED": "#8D9BB0",
        "BORDER_SUBTLE": "#42546E",
        "WARNING_AMBER": "#F2B84B",
        "ERROR_CORAL": "#FF9B85",
        # V2 Cream Detective Editorial & Case File Palette (Section 3 + WCAG AA verified)
        "WARM_PAPER": "#F5EFE4",        # Warm Cream: primary system background
        "WARM_CREAM": "#F5EFE4",        # Warm Cream alias
        "PALE_IVORY": "#FBF7F0",        # Soft Ivory: elevated dossier / card surface
        "SOFT_IVORY": "#FBF7F0",        # Soft Ivory alias
        "PAPER_BEIGE": "#EDE3D2",       # Paper Beige: secondary grouped surface & cover mat
        "LINEN": "#E4D8C3",             # Archive Linen: pills, pull-quotes, subtle accents
        "ARCHIVE_LINEN": "#E4D8C3",     # Archive Linen alias
        "LINEN_HOVER": "#EDE3D2",       # Warm Paper Beige hover tint on cards
        "PARCHMENT_BORDER": "#D5C7B2",  # Delicate editorial hairline divider
        "PARCHMENT_STRONG": "#B8A58B",  # Stronger paper rule / interactive border
        "DEEP_INK": "#1E2F45",          # Deep Ink Blue (12.71:1 on Soft Ivory)
        "DEEP_INK_BLUE": "#1E2F45",     # Deep Ink Blue alias
        "MIDNIGHT_SLATE": "#24374D",    # Midnight Slate: board stage & ink hover
        "INK_HOVER": "#24374D",         # Interactive Deep Ink button hover
        "STEEL_BLUE": "#4B6278",        # Steel Blue: technical borders & secondary accents
        "CREAM_TEXT_PRIMARY": "#1F2430",    # Primary Text (14.53:1 on Soft Ivory)
        "INK_MUTED": "#4E5A67",             # Secondary Text (6.59:1 on Soft Ivory)
        "INK_DISABLED": "#6E7882",          # Muted Text
        "BRICK_RED": "#A64A4A",             # Muted Crimson (5.32:1 on Soft Ivory)
        "MUTED_CRIMSON": "#A64A4A",         # Muted Crimson alias
        "BRICK_RED_DARK": "#8C3B3B",        # Pressed crimson
        "ANTIQUE_BRASS": "#C8A96B",         # Brass Gold accent
        "BRASS_GOLD": "#C8A96B",            # Brass Gold alias
        "ANTIQUE_BRASS_INK": "#7C5821",     # High-contrast brass heading text on cream (5.99:1)
        "EVIDENCE_TEAL": "#4F8C8D",         # Evidence Teal accent
        "WARNING_AMBER_CREAM": "#C88B3A",   # Warning Amber on cream
        "CRIMINAL_SEMANTIC": "#B55252",     # Semantic Criminal fill
        "INNOCENT_SEMANTIC": "#4C8C78",     # Semantic Innocent fill
        "INFO_CLUE_SEMANTIC": "#5B7FA3",    # Semantic Info/Clue fill
        "INNOCENT_PAPER_TEAL": "#186F59",   # High-contrast teal text on ivory (5.68:1)
        "CLUE_PAPER_BLUE": "#185D85",       # High-contrast clue text on ivory (6.67:1)
        "PAPER_SELECTED_BG": "#F5EAD6",     # Selected cream card surface
    }
)


# ---------------------------------------------------------------------------
# Layer 2 — Semantic Tokens
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ColorTokens:
    """Semantic color roles mapped strictly from PRIMITIVE_COLORS."""

    # Dark Nocturne Surfaces (Main Menu skyline & Gameplay Board stage)
    app_background: str = PRIMITIVE_COLORS["MIDNIGHT_NAVY"]
    backdrop_deep: str = PRIMITIVE_COLORS["DEEP_NAVY"]
    elevated_panel: str = PRIMITIVE_COLORS["ELEVATED_NAVY"]
    surface_hover: str = PRIMITIVE_COLORS["PANEL_HOVER_NAVY"]
    card_background: str = PRIMITIVE_COLORS["DETECTIVE_BLUE"]
    card_background_hover: str = PRIMITIVE_COLORS["DETECTIVE_BLUE_HOVER"]

    # Editorial Warm Cream Surfaces (Unified system-wide Cream Detective Editorial palette)
    paper_canvas: str = PRIMITIVE_COLORS["WARM_PAPER"]
    paper_sheet: str = PRIMITIVE_COLORS["PALE_IVORY"]
    paper_beige: str = PRIMITIVE_COLORS["PAPER_BEIGE"]
    paper_linen: str = PRIMITIVE_COLORS["LINEN"]
    paper_hover: str = PRIMITIVE_COLORS["LINEN_HOVER"]
    paper_selected: str = PRIMITIVE_COLORS["PAPER_SELECTED_BG"]
    paper_border: str = PRIMITIVE_COLORS["PARCHMENT_BORDER"]
    paper_border_strong: str = PRIMITIVE_COLORS["PARCHMENT_STRONG"]
    ink_primary: str = PRIMITIVE_COLORS["DEEP_INK"]
    ink_hover: str = PRIMITIVE_COLORS["INK_HOVER"]
    midnight_slate: str = PRIMITIVE_COLORS["MIDNIGHT_SLATE"]
    steel_blue: str = PRIMITIVE_COLORS["STEEL_BLUE"]
    cream_text_primary: str = PRIMITIVE_COLORS["CREAM_TEXT_PRIMARY"]
    ink_secondary: str = PRIMITIVE_COLORS["INK_MUTED"]
    ink_disabled: str = PRIMITIVE_COLORS["INK_DISABLED"]
    brick_accent: str = PRIMITIVE_COLORS["BRICK_RED"]
    brick_accent_dark: str = PRIMITIVE_COLORS["BRICK_RED_DARK"]
    brass_accent: str = PRIMITIVE_COLORS["ANTIQUE_BRASS"]
    brass_ink: str = PRIMITIVE_COLORS["ANTIQUE_BRASS_INK"]
    evidence_teal: str = PRIMITIVE_COLORS["EVIDENCE_TEAL"]
    warning_amber_cream: str = PRIMITIVE_COLORS["WARNING_AMBER_CREAM"]
    criminal_semantic: str = PRIMITIVE_COLORS["CRIMINAL_SEMANTIC"]
    innocent_semantic: str = PRIMITIVE_COLORS["INNOCENT_SEMANTIC"]
    info_clue_semantic: str = PRIMITIVE_COLORS["INFO_CLUE_SEMANTIC"]
    paper_innocent: str = PRIMITIVE_COLORS["INNOCENT_PAPER_TEAL"]
    paper_clue: str = PRIMITIVE_COLORS["CLUE_PAPER_BLUE"]

    # Borders & Overlays (Nocturne board / cards)
    border_subtle: str = PRIMITIVE_COLORS["BORDER_SUBTLE"]
    card_border: str = PRIMITIVE_COLORS["STEEL_GRAY"]
    selected_card: str = PRIMITIVE_COLORS["EVIDENCE_GOLD"]
    focus_ring: str = PRIMITIVE_COLORS["EVIDENCE_GOLD_BRIGHT"]
    clue_highlight: str = PRIMITIVE_COLORS["CLUE_CYAN"]

    # Dark-Surface Text (all verified >= 4.5:1 against intended dark backgrounds)
    primary_text: str = PRIMITIVE_COLORS["PAPER_WHITE"]
    secondary_text: str = PRIMITIVE_COLORS["SLATE_SECONDARY"]
    disabled_text: str = PRIMITIVE_COLORS["SLATE_DISABLED"]
    text_on_gold: str = PRIMITIVE_COLORS["MIDNIGHT_NAVY"]
    text_on_crimson: str = PRIMITIVE_COLORS["PAPER_WHITE"]
    text_on_innocent: str = PRIMITIVE_COLORS["MIDNIGHT_NAVY"]

    # Verdicts (always paired with explicit text + geometric icon)
    criminal_verdict: str = PRIMITIVE_COLORS["CRIMSON_RED"]
    criminal_verdict_hover: str = PRIMITIVE_COLORS["CRIMSON_DARK"]
    criminal_text: str = PRIMITIVE_COLORS["CRIMSON_TEXT"]
    innocent_verdict: str = PRIMITIVE_COLORS["INNOCENT_TEAL"]
    innocent_verdict_hover: str = PRIMITIVE_COLORS["INNOCENT_DARK"]
    innocent_text: str = PRIMITIVE_COLORS["INNOCENT_TEXT"]

    # Interactive CTA & Status
    accent_primary: str = PRIMITIVE_COLORS["EVIDENCE_GOLD"]
    accent_primary_hover: str = PRIMITIVE_COLORS["EVIDENCE_GOLD_BRIGHT"]
    accent_primary_pressed: str = PRIMITIVE_COLORS["EVIDENCE_GOLD_PRESSED"]
    warning: str = PRIMITIVE_COLORS["WARNING_AMBER"]
    error: str = PRIMITIVE_COLORS["ERROR_CORAL"]
    error_surface: str = PRIMITIVE_COLORS["CRIMSON_RED"]
    success: str = PRIMITIVE_COLORS["INNOCENT_TEXT"]

    # Semi-transparent scrims (RGBA tuples for QColor / QSS rgba())
    scrim_menu_rgba: tuple[int, int, int, int] = (242, 231, 210, 232)      # Warm sepia-cream wash neutralizing blue cast of A03
    scrim_gameplay_rgba: tuple[int, int, int, int] = (245, 239, 228, 248)  # Unified Warm Cream gameplay canvas
    scrim_card_text_rgba: tuple[int, int, int, int] = (16, 27, 48, 224)    # >= 9:1 card text scrim
    scrim_evidence_rgba: tuple[int, int, int, int] = (16, 27, 48, 224)


@dataclass(frozen=True, slots=True)
class SpacingTokens:
    """Consistent 4px/8px editorial spacing scale (logical px)."""

    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 24
    space_6: int = 32
    space_7: int = 48


@dataclass(frozen=True, slots=True)
class GeometryTokens:
    """Radii, sizing, borders, and layout geometry constants (logical px)."""

    # Corner radii (crisper archival dossier geometry)
    radius_sm: int = 6
    radius_md: int = 8
    radius_lg: int = 12
    radius_pill: int = 999

    # Panel & control metrics
    panel_padding: int = 16
    panel_gap: int = 16
    button_min_height: int = 44  # WCAG / touch-friendly target >= 44px
    button_min_width: int = 96
    header_height: int = 58
    action_bar_height: int = 60
    verdict_strip_height: int = 56

    # Border & focus ring widths
    border_thin: int = 1
    border_selected: int = 3
    border_highlight: int = 3
    focus_ring_width: int = 2

    # Icon sizes
    icon_inline_px: int = 20     # Qt-native / vector ONLY (never raster A10)
    icon_button_px: int = 20     # Qt-native / vector ONLY
    icon_legend_px: int = 56     # Minimum recommended size for raster A10_*.png
    icon_emblem_px: int = 128

    # Board & Card proportions (compatible with A01/A02 3:4 aspect ratio = 0.75)
    card_design_width: int = 144
    card_design_height: int = 192  # Exact 3:4 matching A01/A02 (1086x1448)
    card_compact_width: int = 114  # Compact mode for 5x5 on smaller viewports
    card_compact_height: int = 152  # Exact 3:4
    card_gap: int = 12
    card_gap_compact: int = 8
    board_margin: int = 24
    board_axis_label_space: int = 28
    board_min_scale: float = 0.80
    board_max_scale: float = 1.00

    # Window & Responsive breakpoints
    window_default_width: int = 1280
    window_default_height: int = 800
    window_min_width: int = 960
    window_min_height: int = 640
    breakpoint_wide: int = 1100
    breakpoint_compact: int = 960
    sidebar_width_wide: int = 360
    sidebar_width_min: int = 280

    # Subtle shadow / glow limits
    shadow_blur_panel: int = 16
    glow_blur_selected: int = 14
    glow_blur_highlight: int = 12


@dataclass(frozen=True, slots=True)
class TypographyTokens:
    """Editorial Detective triple-stack typography (100% Ubuntu Vietnamese verified).

    - Display / Editorial Serif: Noto Serif Display -> Noto Serif -> DejaVu Serif
    - UI / Body Sans:            Lato -> Noto Sans -> DejaVu Sans
    - Metadata / Technical Mono: Noto Sans Mono -> Liberation Mono -> DejaVu Sans Mono
    """

    font_family_display: tuple[str, ...] = (
        "Noto Serif Display",
        "Noto Serif",
        "DejaVu Serif",
        "Georgia",
        "serif",
    )
    font_family_ui: tuple[str, ...] = (
        "Lato",
        "Noto Sans",
        "DejaVu Sans",
        "Liberation Sans",
        "sans-serif",
    )
    font_family_mono: tuple[str, ...] = (
        "Noto Sans Mono",
        "Liberation Mono",
        "DejaVu Sans Mono",
        "monospace",
    )

    # Sizes (logical px at 100% scale)
    size_display: int = 30
    size_title: int = 23
    size_heading: int = 18
    size_subheading: int = 15
    size_body: int = 14
    size_label: int = 13
    size_metadata: int = 12
    size_card_name: int = 14
    size_card_name_compact: int = 12
    size_card_profession: int = 12
    size_card_profession_compact: int = 11
    size_card_badge: int = 11
    size_axis_coord: int = 13
    size_min_readable: int = 10  # Absolute floor after board scaling

    # Weights (Qt QFont numerical weights / CSS weights)
    weight_regular: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700

    # Line heights
    line_height_tight: float = 1.2
    line_height_normal: float = 1.48
    line_height_relaxed: float = 1.6


@dataclass(frozen=True, slots=True)
class AnimationTokens:
    """Timing & easing standards preserved for compatibility."""

    card_flip_duration_ms: int = 320
    hover_duration_ms: int = 150
    highlight_duration_ms: int = 200
    panel_transition_ms: int = 180
    result_reveal_ms: int = 600
    reduced_motion_duration_ms: int = 0

    easing_card_flip: str = "InOutCubic"
    easing_hover: str = "OutQuad"
    easing_highlight: str = "OutCubic"
    easing_panel: str = "InOutQuad"
    easing_result: str = "OutBack"


COLORS = ColorTokens()
SPACING = SpacingTokens()
GEOMETRY = GeometryTokens()
TYPOGRAPHY = TypographyTokens()
ANIMATION = AnimationTokens()


# ---------------------------------------------------------------------------
# Layer 3 — Component-Level Tokens
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComponentTokens:
    """Component-specific visual defaults derived from Layers 1 & 2."""

    # Buttons (Nocturne & Paper)
    btn_primary_bg: str = COLORS.accent_primary
    btn_primary_fg: str = COLORS.text_on_gold
    btn_primary_hover_bg: str = COLORS.accent_primary_hover
    btn_secondary_bg: str = COLORS.card_background
    btn_secondary_fg: str = COLORS.primary_text
    btn_secondary_border: str = COLORS.card_border
    btn_criminal_bg: str = COLORS.criminal_verdict
    btn_criminal_fg: str = COLORS.text_on_crimson
    btn_innocent_bg: str = COLORS.innocent_verdict
    btn_innocent_fg: str = COLORS.text_on_innocent

    btn_ink_primary_bg: str = COLORS.ink_primary
    btn_ink_primary_fg: str = COLORS.paper_sheet
    btn_ink_primary_hover_bg: str = COLORS.ink_hover

    # Panels
    panel_bg: str = COLORS.elevated_panel
    panel_border: str = COLORS.border_subtle
    panel_header_fg: str = COLORS.accent_primary
    dossier_bg: str = COLORS.paper_sheet
    dossier_border: str = COLORS.paper_border

    # CharacterCard overlays
    card_hidden_badge_bg: str = COLORS.backdrop_deep
    card_hidden_badge_fg: str = COLORS.secondary_text
    card_criminal_badge_bg: str = COLORS.criminal_verdict
    card_criminal_badge_fg: str = COLORS.text_on_crimson
    card_innocent_badge_bg: str = COLORS.innocent_verdict
    card_innocent_badge_fg: str = COLORS.text_on_innocent
    card_selected_ring: str = COLORS.selected_card
    card_highlight_ring: str = COLORS.clue_highlight


COMPONENT_TOKENS = ComponentTokens()


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Aggregate read-only design system object."""

    colors: ColorTokens = COLORS
    spacing: SpacingTokens = SPACING
    geometry: GeometryTokens = GEOMETRY
    typography: TypographyTokens = TYPOGRAPHY
    animation: AnimationTokens = ANIMATION
    components: ComponentTokens = COMPONENT_TOKENS


THEME = ThemeTokens()


def _relative_luminance(hex_color: str) -> float:
    cleaned = hex_color.strip()
    if not cleaned.startswith("#") or len(cleaned) != 7:
        raise ValueError(f"Expected #RRGGBB hex color, got {hex_color!r}")
    r, g, b = (int(cleaned[i : i + 2], 16) / 255.0 for i in (1, 3, 5))

    def _linearize(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two #RRGGBB hex colors."""
    l1 = _relative_luminance(fg_hex)
    l2 = _relative_luminance(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
