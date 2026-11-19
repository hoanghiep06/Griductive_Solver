"""Centralized ThemeManager V2 for PySide6 presentation layer.

Renders ``src/gui/styles/styles.qss`` from ``src/gui/styles/tokens.py`` so no
raw hex colors, font families, or spacing magic numbers are duplicated across
widgets, and resolves verified Vietnamese-capable Display Serif, UI Sans, and
Technical Mono font families from ``QFontDatabase``.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Mapping, Optional

from src.gui.styles.tokens import THEME, ThemeTokens


_STYLESHEET_PATH = Path(__file__).resolve().parent / "styles.qss"
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _safe_resolve_font_family(candidates: tuple[str, ...], fallback: str) -> str:
    """Resolve first installed font family if QApplication/QFontDatabase is active."""
    try:
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is not None:
            available = set(QFontDatabase.families())
            for family in candidates:
                if family in available:
                    return family
    except Exception:
        pass
    return candidates[0] if candidates else fallback


def build_qss_variables(
    tokens: ThemeTokens = THEME,
    *,
    font_display: Optional[str] = None,
    font_ui: Optional[str] = None,
    font_mono: Optional[str] = None,
) -> dict[str, str]:
    """Map semantic/component tokens & resolved font stacks into QSS variables."""
    c = tokens.colors
    s = tokens.spacing
    g = tokens.geometry
    t = tokens.typography
    comp = tokens.components

    resolved_display = font_display or _safe_resolve_font_family(t.font_family_display, "Noto Serif")
    resolved_ui = font_ui or _safe_resolve_font_family(t.font_family_ui, "Lato")
    resolved_mono = font_mono or _safe_resolve_font_family(t.font_family_mono, "Noto Sans Mono")

    return {
        # Nocturne surfaces & text
        "APP_BG": c.app_background,
        "BACKDROP_DEEP": c.backdrop_deep,
        "ELEVATED_PANEL": c.elevated_panel,
        "SURFACE_HOVER": c.surface_hover,
        "CARD_BG": c.card_background,
        "CARD_BG_HOVER": c.card_background_hover,
        "BORDER_SUBTLE": c.border_subtle,
        "CARD_BORDER": c.card_border,
        "SELECTED_CARD": c.selected_card,
        "FOCUS_RING": c.focus_ring,
        "CLUE_HIGHLIGHT": c.clue_highlight,
        "PRIMARY_TEXT": c.primary_text,
        "SECONDARY_TEXT": c.secondary_text,
        "DISABLED_TEXT": c.disabled_text,
        "TEXT_ON_GOLD": c.text_on_gold,
        "TEXT_ON_CRIMSON": c.text_on_crimson,
        "TEXT_ON_INNOCENT": c.text_on_innocent,
        # Editorial Warm Cream & Dossier surfaces
        "PAPER_CANVAS": c.paper_canvas,
        "PAPER_SHEET": c.paper_sheet,
        "PAPER_BEIGE": c.paper_beige,
        "PAPER_LINEN": c.paper_linen,
        "PAPER_HOVER": c.paper_hover,
        "PAPER_SELECTED": c.paper_selected,
        "PAPER_BORDER": c.paper_border,
        "PAPER_BORDER_STRONG": c.paper_border_strong,
        "INK_PRIMARY": c.ink_primary,
        "INK_HOVER": c.ink_hover,
        "MIDNIGHT_SLATE": c.midnight_slate,
        "STEEL_BLUE": c.steel_blue,
        "CREAM_TEXT_PRIMARY": c.cream_text_primary,
        "INK_SECONDARY": c.ink_secondary,
        "INK_DISABLED": c.ink_disabled,
        "BRICK_ACCENT": c.brick_accent,
        "BRICK_ACCENT_DARK": c.brick_accent_dark,
        "BRASS_ACCENT": c.brass_accent,
        "BRASS_INK": c.brass_ink,
        "EVIDENCE_TEAL": c.evidence_teal,
        "WARNING_AMBER_CREAM": c.warning_amber_cream,
        "CRIMINAL_SEMANTIC": c.criminal_semantic,
        "INNOCENT_SEMANTIC": c.innocent_semantic,
        "INFO_CLUE_SEMANTIC": c.info_clue_semantic,
        "PAPER_INNOCENT": c.paper_innocent,
        "PAPER_CLUE": c.paper_clue,
        # Semantic verdicts & alerts
        "CRIMINAL_VERDICT": c.criminal_verdict,
        "CRIMINAL_VERDICT_HOVER": c.criminal_verdict_hover,
        "CRIMINAL_TEXT": c.criminal_text,
        "INNOCENT_VERDICT": c.innocent_verdict,
        "INNOCENT_VERDICT_HOVER": c.innocent_verdict_hover,
        "INNOCENT_TEXT": c.innocent_text,
        "ACCENT_PRIMARY": c.accent_primary,
        "ACCENT_PRIMARY_HOVER": c.accent_primary_hover,
        "ACCENT_PRIMARY_PRESSED": c.accent_primary_pressed,
        "WARNING": c.warning,
        "ERROR": c.error,
        "SUCCESS": c.success,
        # Button tokens
        "BTN_PRIMARY_BG": comp.btn_primary_bg,
        "BTN_PRIMARY_FG": comp.btn_primary_fg,
        "BTN_PRIMARY_HOVER_BG": comp.btn_primary_hover_bg,
        "BTN_SECONDARY_BG": comp.btn_secondary_bg,
        "BTN_SECONDARY_FG": comp.btn_secondary_fg,
        "BTN_SECONDARY_BORDER": comp.btn_secondary_border,
        "BTN_CRIMINAL_BG": comp.btn_criminal_bg,
        "BTN_CRIMINAL_FG": comp.btn_criminal_fg,
        "BTN_INNOCENT_BG": comp.btn_innocent_bg,
        "BTN_INNOCENT_FG": comp.btn_innocent_fg,
        "BTN_INK_PRIMARY_BG": comp.btn_ink_primary_bg,
        "BTN_INK_PRIMARY_FG": comp.btn_ink_primary_fg,
        "BTN_INK_PRIMARY_HOVER_BG": comp.btn_ink_primary_hover_bg,
        # Spacing & Geometry
        "SPACE_1": str(s.space_1),
        "SPACE_2": str(s.space_2),
        "SPACE_3": str(s.space_3),
        "SPACE_4": str(s.space_4),
        "SPACE_5": str(s.space_5),
        "SPACE_6": str(s.space_6),
        "RADIUS_SM": str(g.radius_sm),
        "RADIUS_MD": str(g.radius_md),
        "RADIUS_LG": str(g.radius_lg),
        "BUTTON_MIN_HEIGHT": str(g.button_min_height),
        "BORDER_THIN": str(g.border_thin),
        "FOCUS_RING_WIDTH": str(g.focus_ring_width),
        # Typography families & scale
        "FONT_DISPLAY": resolved_display,
        "FONT_UI": resolved_ui,
        "FONT_MONO": resolved_mono,
        "SIZE_DISPLAY": str(t.size_display),
        "SIZE_TITLE": str(t.size_title),
        "SIZE_HEADING": str(t.size_heading),
        "SIZE_SUBHEADING": str(t.size_subheading),
        "SIZE_BODY": str(t.size_body),
        "SIZE_LABEL": str(t.size_label),
        "SIZE_METADATA": str(t.size_metadata),
    }


def render_stylesheet(
    template_path: Optional[Path] = None,
    tokens: ThemeTokens = THEME,
    extra_vars: Optional[Mapping[str, str]] = None,
) -> str:
    """Read ``styles.qss`` and resolve every ``{{TOKEN}}`` placeholder."""
    path = template_path or _STYLESHEET_PATH
    raw = path.read_text(encoding="utf-8")
    if raw.startswith('"""'):
        end = raw.find('"""', 3)
        if end != -1:
            raw = raw[end + 3 :].lstrip()

    variables = build_qss_variables(tokens)
    if extra_vars:
        variables.update(extra_vars)

    missing: set[str] = set()

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            missing.add(key)
            return match.group(0)
        return variables[key]

    rendered = _PLACEHOLDER_RE.sub(_replace, raw)
    if missing:
        raise KeyError(f"Unresolved QSS template placeholders: {sorted(missing)}")
    return rendered


class ThemeManager:
    """Manage centralized tokens, QSS application, triple-stack font resolution & motion."""

    def __init__(self, tokens: ThemeTokens = THEME, *, reduced_motion: bool = False) -> None:
        self._tokens = tokens
        self._reduced_motion = bool(reduced_motion)
        self._cached_qss: Optional[str] = None

    @property
    def tokens(self) -> ThemeTokens:
        return self._tokens

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)

    def stylesheet(self) -> str:
        if self._cached_qss is None:
            self._cached_qss = render_stylesheet(tokens=self._tokens)
        return self._cached_qss

    def resolve_ui_font_family(self) -> str:
        """Select the first available Vietnamese-capable UI sans font family (Lato -> Noto Sans)."""
        return _safe_resolve_font_family(self._tokens.typography.font_family_ui, "Sans Serif")

    def resolve_display_font_family(self) -> str:
        """Select the first available editorial display serif family (Noto Serif Display -> Noto Serif)."""
        return _safe_resolve_font_family(
            self._tokens.typography.font_family_display,
            self.resolve_ui_font_family(),
        )

    def resolve_mono_font_family(self) -> str:
        """Select the first available technical monospace family (Noto Sans Mono)."""
        return _safe_resolve_font_family(
            self._tokens.typography.font_family_mono,
            "Monospace",
        )

    def apply_to_application(self, app) -> str:
        """Configure global QFont and Editorial V2 QSS on a QApplication instance."""
        from PySide6.QtGui import QFont

        font = QFont(self.resolve_ui_font_family())
        font.setPixelSize(self._tokens.typography.size_body)
        app.setFont(font)
        # Re-render QSS now that QFontDatabase is guaranteed initialized
        self._cached_qss = render_stylesheet(tokens=self._tokens)
        app.setStyleSheet(self._cached_qss)
        return self._cached_qss

    def apply_to_widget(self, widget) -> str:
        """Apply stylesheet directly to a widget (useful in isolated widget tests)."""
        qss = self.stylesheet()
        widget.setStyleSheet(qss)
        return qss
