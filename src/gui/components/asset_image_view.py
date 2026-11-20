"""AssetImageView primitive for cached aspect-ratio-safe image rendering (Phase 2)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.gui.asset_registry import AssetId
from src.gui.resources.pixmap_loader import PixmapLoader, default_pixmap_loader
from src.gui.styles.tokens import COLORS, GEOMETRY, TYPOGRAPHY


class ImageScaleMode(str, Enum):
    CONTAIN = "CONTAIN"
    COVER = "COVER"


class AssetImageView(QWidget):
    """Render an approved AssetId with aspect-ratio preservation, caching, and fallback.

    Optional features:
        - ``scrim_rgba``: semi-transparent dark scrim over busy backgrounds (A03/A05).
        - ``overlay_text`` + ``overlay_rect_ratio``: dynamic Qt text placed inside a
          normalized safe area (e.g., ``CASE CLOSED`` inside A07's blank navy ribbon).
    """

    def __init__(
        self,
        asset_id: AssetId,
        *,
        scale_mode: ImageScaleMode = ImageScaleMode.CONTAIN,
        prefer_derived: bool = True,
        scrim_rgba: Optional[tuple[int, int, int, int]] = None,
        overlay_text: Optional[str] = None,
        overlay_rect_ratio: tuple[float, float, float, float] = (0.17, 0.49, 0.66, 0.16),
        rounded_radius: int = 0,
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._asset_id = asset_id
        self._scale_mode = scale_mode
        self._prefer_derived = prefer_derived
        self._scrim_rgba = scrim_rgba
        self._overlay_text = overlay_text
        self._overlay_rect_ratio = overlay_rect_ratio
        self._rounded_radius = rounded_radius
        self._loader = pixmap_loader

        self._source_pixmap: Optional[QPixmap] = None
        self._scaled_pixmap: Optional[QPixmap] = None
        self._cached_size = QSize(0, 0)
        self._missing_asset = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._load_source()

    @property
    def asset_id(self) -> AssetId:
        return self._asset_id

    @property
    def is_missing(self) -> bool:
        return self._missing_asset

    def _load_source(self) -> None:
        loader = self._loader or default_pixmap_loader()
        pm = loader.load_pixmap(self._asset_id, prefer_derived=self._prefer_derived)
        self._source_pixmap = pm
        self._missing_asset = pm.isNull()
        self._scaled_pixmap = None
        self._cached_size = QSize(0, 0)

    def set_asset(self, asset_id: AssetId, *, prefer_derived: bool = True) -> None:
        self._asset_id = asset_id
        self._prefer_derived = prefer_derived
        self._load_source()
        self._rebuild_scaled_cache()
        self.update()

    def _rebuild_scaled_cache(self) -> None:
        size = self.size()
        if size.width() <= 0 or size.height() <= 0 or self._source_pixmap is None or self._source_pixmap.isNull():
            self._scaled_pixmap = None
            return
        if self._scale_mode is ImageScaleMode.COVER:
            self._scaled_pixmap = PixmapLoader.scale_cover(self._source_pixmap, size)
        else:
            self._scaled_pixmap = PixmapLoader.scale_contain(self._source_pixmap, size, allow_upscale=False)
        self._cached_size = QSize(size)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rebuild_scaled_cache()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._scaled_pixmap is None or self._cached_size != self.size():
            self._rebuild_scaled_cache()

        target_rect = self.rect()
        if self._scaled_pixmap is not None and not self._scaled_pixmap.isNull():
            x = (target_rect.width() - self._scaled_pixmap.width()) // 2
            y = (target_rect.height() - self._scaled_pixmap.height()) // 2
            draw_rect = QRect(x, y, self._scaled_pixmap.width(), self._scaled_pixmap.height())
            painter.drawPixmap(draw_rect, self._scaled_pixmap)

            if self._overlay_text:
                rx, ry, rw, rh = self._overlay_rect_ratio
                text_rect = QRectF(
                    draw_rect.x() + draw_rect.width() * rx,
                    draw_rect.y() + draw_rect.height() * ry,
                    draw_rect.width() * rw,
                    draw_rect.height() * rh,
                )
                font = QFont(TYPOGRAPHY.font_family_display[0])
                font.setPixelSize(max(12, int(text_rect.height() * 0.56)))
                font.setBold(True)
                font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112.0)
                painter.setFont(font)
                painter.setPen(QColor(COLORS.accent_primary))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._overlay_text)
        else:
            # Graceful fallback when asset file is missing.
            painter.fillRect(target_rect, QColor(COLORS.elevated_panel))
            pen = QPen(QColor(COLORS.card_border), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(
                target_rect.adjusted(2, 2, -2, -2),
                GEOMETRY.radius_sm,
                GEOMETRY.radius_sm,
            )
            painter.setPen(QColor(COLORS.secondary_text))
            painter.drawText(
                target_rect.adjusted(8, 8, -8, -8),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                f"[Missing asset: {self._asset_id.value}]",
            )

        if self._scrim_rgba is not None:
            r, g, b, a = self._scrim_rgba
            painter.fillRect(target_rect, QColor(r, g, b, a))

        painter.end()
