"""AssetImageView primitive for cached aspect-ratio-safe image rendering (Phase 2)."""

from __future__ import annotations

from enum import Enum
import math
from typing import Optional

from PySide6.QtCore import Property, QAbstractAnimation, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.gui.animations.card_flip import build_perspective_3d_transform
from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import SPRING_HIGHLIGHT, build_easing
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
        self._render_scale: float = 1.0
        self._burst_progress: float = 0.0
        self._tilt_x_deg: float = 0.0
        self._tilt_y_deg: float = 0.0
        self._hover_level: float = 0.0
        self._interactive_tilt: bool = False
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)

        self._hover_anim = QPropertyAnimation(self, b"hover_level", self)
        self._hover_anim.setDuration(DEFAULT_MOTION.scaled_ms(180))
        self._hover_anim.setEasingCurve(build_easing(SPRING_HIGHLIGHT, tempo=DEFAULT_MOTION.tempo))

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._load_source()

    def set_interactive_tilt(self, enabled: bool) -> None:
        """Enable 3D mouse-hover parallax tilt & museum-glass glare on this artwork."""
        self._interactive_tilt = bool(enabled)
        self.setMouseTracking(self._interactive_tilt)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            if self._hover_anim.state() == QAbstractAnimation.State.Running:
                self._hover_anim.stop()
            self._hover_level = 0.0
            self._tilt_x_deg = 0.0
            self._tilt_y_deg = 0.0
            self.update()

    def _get_tilt_x_deg(self) -> float:
        return self._tilt_x_deg

    def _set_tilt_x_deg(self, value: float) -> None:
        clamped = max(-30.0, min(30.0, float(value)))
        if clamped != self._tilt_x_deg:
            self._tilt_x_deg = clamped
            self.update()

    tilt_x_deg = Property(float, _get_tilt_x_deg, _set_tilt_x_deg)

    def _get_tilt_y_deg(self) -> float:
        return self._tilt_y_deg

    def _set_tilt_y_deg(self, value: float) -> None:
        clamped = max(-30.0, min(30.0, float(value)))
        if clamped != self._tilt_y_deg:
            self._tilt_y_deg = clamped
            self.update()

    tilt_y_deg = Property(float, _get_tilt_y_deg, _set_tilt_y_deg)

    def _get_hover_level(self) -> float:
        return self._hover_level

    def _set_hover_level(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if clamped != self._hover_level:
            self._hover_level = clamped
            self.update()

    hover_level = Property(float, _get_hover_level, _set_hover_level)

    def enterEvent(self, event) -> None:  # noqa: N802
        if self._interactive_tilt and not self._reduced_motion:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_level)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._interactive_tilt and not self._reduced_motion:
            cx = max(1.0, self.width() * 0.5)
            cy = max(1.0, self.height() * 0.5)
            nx = max(-1.0, min(1.0, (event.position().x() - cx) / cx))
            ny = max(-1.0, min(1.0, (event.position().y() - cy) / cy))
            self._tilt_y_deg = nx * 6.5
            self._tilt_x_deg = -ny * 5.5
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._interactive_tilt:
            self._hover_anim.stop()
            if self._reduced_motion:
                self._hover_level = 0.0
                self._tilt_x_deg = 0.0
                self._tilt_y_deg = 0.0
                self.update()
            else:
                self._hover_anim.setStartValue(self._hover_level)
                self._hover_anim.setEndValue(0.0)
                self._hover_anim.start()
        super().leaveEvent(event)

    def _get_render_scale(self) -> float:
        return self._render_scale

    def _set_render_scale(self, value: float) -> None:
        clamped = max(0.5, min(1.35, float(value)))
        if clamped != self._render_scale:
            self._render_scale = clamped
            self.update()

    render_scale = Property(float, _get_render_scale, _set_render_scale)

    def _get_burst_progress(self) -> float:
        return self._burst_progress

    def _set_burst_progress(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if clamped != self._burst_progress:
            self._burst_progress = clamped
            self.update()

    burst_progress = Property(float, _get_burst_progress, _set_burst_progress)

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

    def set_custom_pixmap(self, pixmap: QPixmap) -> None:
        """Override displayed artwork with a custom local QPixmap while preserving 3D tilt/scale."""
        if pixmap is None or pixmap.isNull():
            return
        self._source_pixmap = pixmap
        self._missing_asset = False
        self._scaled_pixmap = None
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
            painter.save()
            eff_factor = self._hover_level if self._interactive_tilt else 1.0
            eff_tx = 0.0 if self._reduced_motion else (self._tilt_x_deg * eff_factor)
            eff_ty = 0.0 if self._reduced_motion else (self._tilt_y_deg * eff_factor)
            has_3d = abs(eff_tx) > 0.05 or abs(eff_ty) > 0.05

            if has_3d:
                tx = build_perspective_3d_transform(
                    float(target_rect.width()),
                    float(target_rect.height()),
                    eff_ty,
                    eff_tx,
                    lift_scale=self._render_scale,
                )
                painter.setTransform(tx, combine=True)
            elif abs(self._render_scale - 1.0) > 1e-4:
                cx = target_rect.width() * 0.5
                cy = target_rect.height() * 0.5
                painter.translate(cx, cy)
                painter.scale(self._render_scale, self._render_scale)
                painter.translate(-cx, -cy)

            x = (target_rect.width() - self._scaled_pixmap.width()) // 2
            y = (target_rect.height() - self._scaled_pixmap.height()) // 2
            draw_rect = QRect(x, y, self._scaled_pixmap.width(), self._scaled_pixmap.height())
            painter.drawPixmap(draw_rect, self._scaled_pixmap)

            if has_3d and self._interactive_tilt:
                glare = QLinearGradient(
                    draw_rect.left() + (eff_ty / 7.0) * draw_rect.width() * 0.4,
                    draw_rect.top(),
                    draw_rect.right() + (eff_ty / 7.0) * draw_rect.width() * 0.4,
                    draw_rect.bottom(),
                )
                alpha = int(min(36, (abs(eff_tx) + abs(eff_ty)) * 3.0))
                glare.setColorAt(0.0, QColor(255, 248, 225, 0))
                glare.setColorAt(0.5, QColor(255, 246, 218, alpha))
                glare.setColorAt(1.0, QColor(255, 248, 225, 0))
                painter.fillRect(draw_rect, glare)

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
            painter.restore()

            # Expressive celebratory radial particles (bounded, finite burst)
            if 0.0 < self._burst_progress < 1.0:
                self._paint_burst_particles(painter, target_rect, self._burst_progress)
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

    @staticmethod
    def _paint_burst_particles(painter: QPainter, rect: QRect, progress: float) -> None:
        """Render 14 finite brass/amber celebration sparks expanding around an emblem."""
        cx = rect.width() * 0.5
        cy = rect.height() * 0.5
        max_rx = rect.width() * 0.46
        max_ry = rect.height() * 0.46
        fade = max(0.0, min(1.0, (1.0 - progress) * 1.25)) * min(1.0, progress * 6.0)
        palette = (
            QColor(228, 185, 109),
            QColor(246, 213, 142),
            QColor(101, 185, 233),
        )
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        count = 14
        for idx in range(count):
            angle = (2.0 * math.pi * idx) / count + 0.18
            speed = 0.78 + 0.28 * ((idx % 3) / 2.0)
            dist = progress * speed
            px = cx + math.cos(angle) * max_rx * dist
            py = cy + math.sin(angle) * max_ry * dist
            size = (4.6 - 2.2 * progress) * (0.85 + 0.3 * (idx % 2))
            col = QColor(palette[idx % len(palette)])
            col.setAlpha(int(235 * fade))
            painter.setBrush(QBrush(col))
            painter.drawEllipse(QPointF(px, py), size * 0.5, size * 0.5)
        painter.restore()
