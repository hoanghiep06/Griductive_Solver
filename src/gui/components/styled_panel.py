"""StyledPanel reusable container supporting Nocturne & Warm Paper Dossier surfaces."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.asset_registry import AssetId
from src.gui.resources.pixmap_loader import PixmapLoader, default_pixmap_loader
from src.gui.styles.tokens import COLORS, SPACING

VALID_PANEL_VARIANTS = frozenset(
    {"elevated", "card", "deep", "accent", "translucent", "paper", "dossier", "paperLinen"}
)
_PAPER_VARIANTS = frozenset({"paper", "dossier", "paperLinen"})
_VARIANT_CANONICAL: dict[str, str] = {v.lower(): v for v in VALID_PANEL_VARIANTS}


class StyledPanel(QFrame):
    """Themed QFrame supporting Nocturne dark and Warm Paper editorial materials."""

    def __init__(
        self,
        *,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        variant: str = "elevated",
        padding: int = SPACING.space_4,
        decorative_texture: bool = False,
        accent_bar: Optional[str] = None,  # None | "brick" | "brass" | "ink"
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("widgetKind", "styledPanel")
        self._variant = "elevated"
        self._decorative_texture = bool(decorative_texture)
        self._accent_bar = accent_bar
        self._pixmap_loader = pixmap_loader
        self._cached_texture: Optional[QPixmap] = None
        self._cached_texture_size: tuple[int, int] = (0, 0)

        self._root_layout = QVBoxLayout(self)
        top_pad = padding + (3 if accent_bar else 0)
        self._root_layout.setContentsMargins(padding, top_pad, padding, padding)
        self._root_layout.setSpacing(SPACING.space_2)

        canonical_init = _VARIANT_CANONICAL.get(variant.strip().lower(), "elevated")
        is_paper = canonical_init in _PAPER_VARIANTS

        self._title_label: Optional[QLabel] = None
        self._subtitle_label: Optional[QLabel] = None
        if title:
            self._title_label = QLabel(title, self)
            self._title_label.setProperty("role", "paperHeading" if is_paper else "heading")
            self._title_label.setWordWrap(True)
            self._root_layout.addWidget(self._title_label)
        if subtitle:
            self._subtitle_label = QLabel(subtitle, self)
            self._subtitle_label.setProperty("role", "paperCaption" if is_paper else "caption")
            self._subtitle_label.setWordWrap(True)
            self._root_layout.addWidget(self._subtitle_label)

        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(SPACING.space_3)
        self._root_layout.addLayout(self._content_layout, 1)

        self.set_variant(variant)

    @property
    def variant(self) -> str:
        return self._variant

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    @property
    def title_label(self) -> Optional[QLabel]:
        return self._title_label

    @property
    def subtitle_label(self) -> Optional[QLabel]:
        return self._subtitle_label

    def set_header_icon(self, icon_widget: QWidget) -> None:
        """Place a crisp vector icon cleanly beside the panel title & subtitle."""
        if self._title_label is None:
            return
        self._root_layout.removeWidget(self._title_label)
        if self._subtitle_label is not None:
            self._root_layout.removeWidget(self._subtitle_label)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 2)
        header_row.setSpacing(8)
        icon_widget.setParent(self)
        header_row.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        text_col.addWidget(self._title_label)
        if self._subtitle_label is not None:
            text_col.addWidget(self._subtitle_label)
        header_row.addLayout(text_col, 1)
        self._root_layout.insertLayout(0, header_row)

    def set_variant(self, variant: str) -> None:
        key = variant.strip().lower()
        canonical = _VARIANT_CANONICAL.get(key)
        if canonical is None:
            raise ValueError(
                f"Unsupported StyledPanel variant {variant!r}; "
                f"expected one of {sorted(VALID_PANEL_VARIANTS)}"
            )
        self._variant = canonical
        self.setProperty("variant", canonical)
        is_paper = canonical in _PAPER_VARIANTS
        if self._title_label is not None:
            self._title_label.setProperty("role", "paperHeading" if is_paper else "heading")
            self._title_label.style().unpolish(self._title_label)
            self._title_label.style().polish(self._title_label)
        if self._subtitle_label is not None:
            self._subtitle_label.setProperty("role", "paperCaption" if is_paper else "caption")
            self._subtitle_label.style().unpolish(self._subtitle_label)
            self._subtitle_label.style().polish(self._subtitle_label)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def _refresh_texture_cache(self) -> None:
        if not self._decorative_texture or self.width() <= 0 or self.height() <= 0:
            self._cached_texture = None
            return
        loader = self._pixmap_loader or default_pixmap_loader()
        raw = loader.load_pixmap(AssetId.A08_EVIDENCE_TEXTURE, prefer_derived=False)
        if raw.isNull():
            self._cached_texture = None
            return
        # Phase 1 rule: A08 is NOT seamless and has a garbled red stamp in top-right.
        # Crop strictly to the clean central paper region (avoiding top-right stamp & border props).
        crop = QRect(
            int(raw.width() * 0.24),
            int(raw.height() * 0.24),
            int(raw.width() * 0.52),
            int(raw.height() * 0.52),
        )
        cropped = raw.copy(crop)
        self._cached_texture = PixmapLoader.scale_cover(cropped, self.size())
        self._cached_texture_size = (self.width(), self.height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._decorative_texture:
            self._refresh_texture_cache()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._decorative_texture:
            if self._cached_texture is None or self._cached_texture_size != (self.width(), self.height()):
                self._refresh_texture_cache()
            if self._cached_texture is not None and not self._cached_texture.isNull():
                painter = QPainter(self)
                painter.setOpacity(0.08 if self._variant in _PAPER_VARIANTS else 0.10)
                painter.drawPixmap(0, 0, self._cached_texture)
                painter.end()

        if self._accent_bar:
            bar_color_map = {
                "brick": COLORS.brick_accent,
                "brass": COLORS.brass_accent,
                "ink": COLORS.ink_primary,
            }
            color_hex = bar_color_map.get(self._accent_bar)
            if color_hex:
                painter = QPainter(self)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color_hex))
                painter.drawRect(1, 1, max(0, self.width() - 2), 3)
                painter.end()
