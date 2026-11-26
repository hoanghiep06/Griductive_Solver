"""LevelSelectionScreen — Archival Master Dossier "Kho Hồ Sơ Vụ Án" over Living Noir Desk.

Presents the 15 official cases grouped into 3 classic ribbon-headed folder columns
(3×3 Cơ bản / 4×4 Nâng cao / 5×5 Phức tạp) inside a centered archival parchment
sheet fastened with a top-left 3D brass binder clip, 4 filigree corners, faint
sepia city etching, top-right crimson wax seal with braided twine, and an
integrated bottom selection bar with vector indicators and luminous CTA button.

Strictly presentation-only: renders ONLY public ``LevelSummary`` items supplied
by Controller. Never reads puzzle files or hidden solutions.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.asset_registry import AssetId
from src.gui.case_catalog import localize_difficulty, split_case_number_and_name
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.case_tile import CaseTile
from src.gui.components.page_header import PageHeader
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.styles.tokens import SPACING, TYPOGRAPHY
from src.gui.view_models import LevelSummary, normalize_level_summary

# (grid_size, key, ribbon_title, suspects_count, cover_asset, ribbon_palette)
_GROUP_SPECS: tuple[tuple[int, str, str, int, AssetId, tuple[str, str]], ...] = (
    (3, "3x3", "Hồ sơ cơ bản · 3 × 3", 9, AssetId.A06_CASE_COVER_3X3, ("#203752", "#142438")),
    (4, "4x4", "Hồ sơ nâng cao · 4 × 4", 16, AssetId.A06_CASE_COVER_4X4, ("#1B3049", "#101E30")),
    (5, "5x5", "Hồ sơ phức tạp · 5 × 5", 25, AssetId.A06_CASE_COVER_5X5, ("#872926", "#5E1917")),
)


class _LivingArchiveBackdrop(QWidget):
    """Cozy moonlit noir detective desk backdrop with breathing lamp, steam & golden dust."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        bg_path = Path(__file__).resolve().parents[3] / "assets" / "backgrounds" / "A07_results_desk_backdrop.png"
        self._raw_bg = QPixmap(str(bg_path)) if bg_path.is_file() else QPixmap()
        self._scaled_bg: Optional[QPixmap] = None
        self._cached_sz = QSize(0, 0)
        self._phase: float = 0.0
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)

        self._motes: tuple[tuple[float, float, float, float, float, float], ...] = tuple(
            (
                (0.015 + ((i * 19) % 10) * 0.012) if (i % 2 == 0) else (0.875 + ((i * 17) % 10) * 0.011),
                0.06 + ((i * 29 + 13) % 86) / 100.0,
                0.45 + 0.55 * ((i % 4) / 3.0),
                0.48 + 0.62 * ((i % 3) / 2.0),
                (i * 1.43) % (2.0 * math.pi),
                1.4 + 2.2 * ((i % 3) / 2.0),
            )
            for i in range(24)
        )

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            self._timer.stop()
            self.update()
        elif self.isVisible():
            self._timer.start()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._reduced_motion and not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def _on_tick(self) -> None:
        if self._reduced_motion or not self.isVisible():
            self._timer.stop()
            return
        self._phase = (self._phase + 0.036) % (200.0 * math.pi)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        if w <= 4 or h <= 4:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if not self._raw_bg.isNull():
            sz = QSize(int(w), int(h))
            if self._scaled_bg is None or self._cached_sz != sz:
                self._scaled_bg = self._raw_bg.scaled(
                    sz,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._cached_sz = sz
            ox = int((w - self._scaled_bg.width()) * 0.5)
            oy = int(h - self._scaled_bg.height())
            p.drawPixmap(ox, oy, self._scaled_bg)
        else:
            p.fillRect(self.rect(), QColor("#1D140E"))

        phase = 0.0 if self._reduced_motion else self._phase
        p.setPen(Qt.PenStyle.NoPen)

        # Warm lamp glow left
        lamp_pt = QPointF(w * 0.11, h * 0.34)
        lp = 0.85 + 0.15 * math.sin(phase * 1.45)
        lr = min(w, h) * 0.26
        lg = QRadialGradient(lamp_pt, lr)
        lg.setColorAt(0.0, QColor(255, 228, 155, int(86 * lp)))
        lg.setColorAt(0.5, QColor(240, 178, 84, int(32 * lp)))
        lg.setColorAt(1.0, QColor(240, 178, 84, 0))
        p.setBrush(lg)
        p.drawEllipse(lamp_pt, lr, lr)

        # Shimmering full moon corona right
        moon_pt = QPointF(w * 0.94, h * 0.14)
        mp = 0.84 + 0.16 * math.sin(phase * 1.1)
        mr = min(w, h) * 0.20
        mg = QRadialGradient(moon_pt, mr)
        mg.setColorAt(0.0, QColor(255, 246, 214, int(80 * mp)))
        mg.setColorAt(1.0, QColor(242, 212, 152, 0))
        p.setBrush(mg)
        p.drawEllipse(moon_pt, mr, mr)

        # Floating golden dust motes in margins
        for x0, y0, depth, spd, p0, rad in self._motes:
            t = phase * spd + p0
            mx = (x0 * w + math.sin(t * 0.8) * 12.0 * depth) % w
            my = (y0 * h - ((phase * 6.8 * spd * depth) % h)) % h
            tw = 0.42 + 0.58 * math.sin(t * 2.0)
            al = int((50 + 96 * depth) * tw)
            dg = QRadialGradient(QPointF(mx, my), rad * 2.6)
            dg.setColorAt(0.0, QColor(255, 236, 178, al))
            dg.setColorAt(1.0, QColor(238, 188, 96, 0))
            p.setBrush(dg)
            p.drawEllipse(QPointF(mx, my), rad * 2.6, rad * 2.6)
        p.end()


class _MiniDetectiveNotebookBadge(QWidget):
    """Hand-drawn antique dossier notebook + pinned sepia detective silhouette card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(78, 72)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Back dark leather notebook cover tilted left
        p.save()
        p.translate(26.0, 38.0)
        p.rotate(-14.0)
        p.setPen(QPen(QColor("#241B12"), 1.0))
        p.setBrush(QColor("#3E3224"))
        p.drawRoundedRect(QRectF(-16.0, -24.0, 32.0, 48.0), 3.0, 3.0)
        p.setPen(QPen(QColor("#C49D5A"), 1.0))
        p.drawLine(QPointF(-10.0, -20.0), QPointF(-10.0, 20.0))
        p.restore()

        # Front sepia suspect card tilted slightly right
        p.save()
        p.translate(45.0, 36.0)
        p.rotate(-4.0)
        card = QRectF(-20.0, -26.0, 40.0, 52.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(34, 22, 10, 48))
        p.drawRoundedRect(card.translated(2.0, 3.0), 2.5, 2.5)
        p.setBrush(QColor("#EAD7B4"))
        p.setPen(QPen(QColor("#AE8D5A"), 1.1))
        p.drawRoundedRect(card, 2.5, 2.5)

        # Detective fedora silhouette inside card
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#433120"))
        # Fedora brim + crown
        p.drawEllipse(QPointF(0.0, -10.5), 11.0, 2.8)
        p.drawRoundedRect(QRectF(-6.5, -18.5, 13.0, 8.5), 3.5, 3.5)
        # Head + coat shoulders
        p.drawEllipse(QPointF(0.0, -4.5), 5.6, 6.2)
        shoulders = QPainterPath(QPointF(-11.0, 16.0))
        shoulders.quadTo(QPointF(-10.0, 3.5), QPointF(0.0, 3.0))
        shoulders.quadTo(QPointF(10.0, 3.5), QPointF(11.0, 16.0))
        shoulders.closeSubpath()
        p.drawPath(shoulders)

        # Tiny crimson wax pin at bottom-right corner
        p.setBrush(QColor("#A32E27"))
        p.setPen(QPen(QColor("#6B1813"), 0.8))
        p.drawEllipse(QPointF(15.0, 20.0), 4.5, 4.5)
        p.restore()
        p.end()


class _GroupBannerRibbon(QWidget):
    """Notched antique-gold bordered header ribbon with gold star dots on both ends."""

    def __init__(
        self,
        title: str,
        *,
        bg_top: str,
        bg_bottom: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._bg_top = QColor(bg_top)
        self._bg_bottom = QColor(bg_bottom)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Centered notched ribbon banner
        margin_x = max(8.0, w * 0.08)
        r = QRectF(margin_x, 2.0, w - 2.0 * margin_x, h - 4.0)
        cut = 6.0
        poly = QPolygonF(
            [
                QPointF(r.left() + cut, r.top()),
                QPointF(r.right() - cut, r.top()),
                QPointF(r.right(), r.center().y()),
                QPointF(r.right() - cut, r.bottom()),
                QPointF(r.left() + cut, r.bottom()),
                QPointF(r.left(), r.center().y()),
            ]
        )

        # Subtle shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(28, 18, 8, 38))
        p.drawPolygon(poly.translated(0.0, 2.0))

        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, self._bg_top)
        grad.setColorAt(1.0, self._bg_bottom)
        p.setBrush(grad)
        p.setPen(QPen(QColor("#D2AD64"), 1.5))
        p.drawPolygon(poly)

        # Tiny 4-point brass stars on left & right of title
        for sx in (r.left() + 12.0, r.right() - 12.0):
            cy = r.center().y()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#E8C884"))
            p.drawPolygon(
                QPolygonF(
                    [
                        QPointF(sx, cy - 3.6),
                        QPointF(sx + 1.4, cy - 1.4),
                        QPointF(sx + 3.6, cy),
                        QPointF(sx + 1.4, cy + 1.4),
                        QPointF(sx, cy + 3.6),
                        QPointF(sx - 1.4, cy + 1.4),
                        QPointF(sx - 3.6, cy),
                        QPointF(sx - 1.4, cy - 1.4),
                    ]
                )
            )

        font = QFont(TYPOGRAPHY.font_family_display[0])
        font.setPixelSize(13)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFF8E8"))
        p.drawText(r.adjusted(18.0, 0.0, -18.0, 0.0), Qt.AlignmentFlag.AlignCenter, self._title)
        p.end()


class _ArchiveDossierSheet(QFrame):
    """Master archival parchment board with brass clip, filigree corners, city etching & top-right wax seal."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("LevelArchiveDossierSheet")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(36, 26, 36, 24)
        self.content_layout.setSpacing(10)

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        if w <= 60 or h <= 60:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(20.0, 16.0, w - 40.0, h - 28.0)

        # 1. Background kraft folder & tilted sepia photo cards peeking out left & right
        p.save()
        p.translate(outer.center().x(), outer.center().y())
        p.rotate(-0.8)
        p.setPen(QPen(QColor("#8C6735"), 1.0))
        p.setBrush(QColor("#BA8F54"))
        p.drawRoundedRect(
            QRectF(-outer.width() * 0.506, -outer.height() * 0.510, outer.width() * 1.012, outer.height() * 1.018),
            6.0,
            6.0,
        )
        p.restore()

        # Soft shadow beneath parchment
        for expand, dy, alpha in ((7.0, 9.0, 32), (3.5, 5.0, 50), (1.0, 2.0, 68)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(10, 6, 3, alpha))
            p.drawRoundedRect(outer.adjusted(-expand, dy - 2.0, expand, dy + 2.0), 6.0, 6.0)

        # 2. Main warm ivory-parchment body
        parch = QRadialGradient(outer.center(), max(outer.width(), outer.height()) * 0.65)
        parch.setColorAt(0.0, QColor("#FDF8EC"))
        parch.setColorAt(0.75, QColor("#F7ECD5"))
        parch.setColorAt(1.0, QColor("#ECDCB9"))
        p.setBrush(parch)
        p.setPen(QPen(QColor("#C4A062"), 2.0))
        p.drawRoundedRect(outer, 5.0, 5.0)

        # Inner fine double gold frame
        inner = outer.adjusted(7.0, 7.0, -7.0, -7.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#CCAC73"), 1.2))
        p.drawRoundedRect(inner, 3.0, 3.0)

        # 3. Subtle sepia domed-city silhouette watermark along top-right header zone
        p.save()
        p.setClipRect(inner)
        self._draw_header_city_watermark(p, inner)
        p.restore()

        # 4. Ornate gold filigree corner flourishes
        self._draw_corner_filigree(p, inner)

        # 5. Top-left 3D Antique Brass Binder Clip
        self._draw_binder_clip(p, QPointF(outer.left() + 74.0, outer.top()))

        # 6. Top-right Glossy Crimson Wax Seal with braided hemp twine
        self._draw_top_right_wax_seal(p, QPointF(outer.right() - 84.0, outer.top() + 56.0), outer.right(), outer.top())
        p.end()

    @staticmethod
    def _draw_header_city_watermark(p: QPainter, inner: QRectF) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(172, 142, 92, 26))
        base_y = inner.top() + 86.0
        rx = inner.right() - 290.0
        # Classical dome + towers silhouette
        p.drawChord(QRectF(rx + 68.0, base_y - 68.0, 48.0, 56.0), 0, 180 * 16)
        p.drawRect(QRectF(rx + 89.0, base_y - 78.0, 6.0, 12.0))
        for ox, bw, bh in (
            (10, 22, 24), (36, 18, 36), (58, 66, 40), (130, 22, 48),
            (156, 18, 32), (178, 24, 54), (206, 20, 30), (230, 26, 22),
        ):
            p.drawRect(QRectF(rx + ox, base_y - bh, bw, bh))

    @staticmethod
    def _draw_corner_filigree(p: QPainter, rect: QRectF) -> None:
        pen = QPen(QColor("#BC9450"), 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for cx, cy, sx, sy in (
            (rect.left() + 3.0, rect.top() + 3.0, 1.0, 1.0),
            (rect.right() - 3.0, rect.top() + 3.0, -1.0, 1.0),
            (rect.left() + 3.0, rect.bottom() - 3.0, 1.0, -1.0),
            (rect.right() - 3.0, rect.bottom() - 3.0, -1.0, -1.0),
        ):
            p.save()
            p.translate(cx, cy)
            p.scale(sx, sy)
            p.drawLine(QPointF(0.0, 0.0), QPointF(16.0, 0.0))
            p.drawLine(QPointF(0.0, 0.0), QPointF(0.0, 16.0))
            scroll = QPainterPath(QPointF(3.0, 12.5))
            scroll.quadTo(QPointF(4.0, 4.0), QPointF(12.5, 3.0))
            p.drawPath(scroll)
            p.drawEllipse(QPointF(6.8, 6.8), 1.8, 1.8)
            p.restore()

    @staticmethod
    def _draw_binder_clip(p: QPainter, anchor: QPointF) -> None:
        p.save()
        p.translate(anchor)
        wire = QRectF(-8.0, -16.0, 16.0, 16.0)
        p.setPen(QPen(QColor("#5C3F18"), 2.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(wire, 6.0, 6.0)
        p.setPen(QPen(QColor("#E3C27A"), 1.0))
        p.drawRoundedRect(wire.adjusted(0.5, 0.5, -0.5, -0.5), 5.5, 5.5)

        clamp = QRectF(-18.0, -3.5, 36.0, 15.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(16, 10, 4, 52))
        p.drawRoundedRect(clamp.translated(1.5, 2.8), 2.5, 2.5)
        grad = QLinearGradient(clamp.topLeft(), clamp.bottomLeft())
        grad.setColorAt(0.0, QColor("#6E5028"))
        grad.setColorAt(0.45, QColor("#362612"))
        grad.setColorAt(1.0, QColor("#22170B"))
        p.setPen(QPen(QColor("#C8A25B"), 1.1))
        p.setBrush(grad)
        p.drawRoundedRect(clamp, 2.5, 2.5)
        p.restore()

    @staticmethod
    def _draw_top_right_wax_seal(p: QPainter, center: QPointF, right_edge: float, top_edge: float) -> None:
        p.save()
        # Braided hemp twine curving neatly from seal up to top-right sheet corner
        twine = QPainterPath(center + QPointF(16.0, -4.0))
        twine.cubicTo(
            QPointF(right_edge - 26.0, center.y() - 6.0),
            QPointF(right_edge - 12.0, top_edge + 22.0),
            QPointF(right_edge - 2.0, top_edge + 6.0),
        )
        p.setPen(QPen(QColor("#8C6738"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(twine)
        p.setPen(QPen(QColor("#D8B982"), 1.1, Qt.PenStyle.DashLine))
        p.drawPath(twine)

        p.translate(center)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(22, 10, 6, 62))
        p.drawEllipse(QPointF(2.0, 3.5), 29.0, 29.0)

        rim = QPainterPath()
        pts = 24
        for i in range(pts + 1):
            ang = (i / pts) * 2.0 * math.pi
            rad = 27.5 + 1.8 * math.sin(i * 3.0)
            pt = QPointF(math.cos(ang) * rad, math.sin(ang) * rad)
            if i == 0:
                rim.moveTo(pt)
            else:
                rim.lineTo(pt)
        rim.closeSubpath()

        wax = QRadialGradient(QPointF(-7.0, -7.0), 34.0)
        wax.setColorAt(0.0, QColor("#C64236"))
        wax.setColorAt(0.55, QColor("#96241C"))
        wax.setColorAt(1.0, QColor("#64150F"))
        p.setBrush(wax)
        p.setPen(QPen(QColor("#52100C"), 1.2))
        p.drawPath(rim)

        p.setBrush(QColor("#821E17"))
        p.setPen(QPen(QColor("#DC9F82"), 1.1))
        p.drawEllipse(QPointF(0.0, 0.0), 19.5, 19.5)

        # Embossed detective fedora silhouette inside wax seal
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#EAA98B"))
        p.drawEllipse(QPointF(0.0, -5.5), 9.5, 2.2)
        p.drawRoundedRect(QRectF(-5.5, -12.0, 11.0, 6.8), 3.0, 3.0)
        p.drawEllipse(QPointF(0.0, -0.5), 4.6, 5.2)
        p.drawRoundedRect(QRectF(-8.5, 5.0, 17.0, 7.5), 4.0, 4.0)
        p.restore()


class _ArchiveOpenButton(StyledButton):
    """Deep Ink Navy CTA button with double antique-gold rim (preserves variant='primary')."""

    def __init__(self, text: str, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, variant="primary", min_height=42, parent=parent)
        self.setMinimumWidth(196)
        self.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1D324D, stop:1 #112034);"
            "  color: #FFFDF7;"
            "  border: 2px solid #D9B365;"
            "  border-radius: 8px;"
            "  font-weight: 700;"
            "  font-size: 14.5px;"
            "  padding: 0 20px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #264164, stop:1 #172B45);"
            "  border: 2px solid #F0D088;"
            "}"
            "QPushButton:disabled {"
            "  background: #DFD2B8;"
            "  color: #827562;"
            "  border: 1.5px solid #C6B494;"
            "}"
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.isEnabled():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(QPen(QColor(246, 218, 152, 130), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(3.5, 3.5, self.width() - 7.0, self.height() - 7.0), 5.5, 5.5)
            p.end()


class _FooterDocIcon(QWidget):
    """Crisp vector document emblem for the integrated bottom selection strip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(26, 26)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor("#8D662C"), 1.5))
        p.setBrush(QColor("#FBF5E8"))
        p.drawRoundedRect(QRectF(5.0, 3.0, 16.0, 20.0), 2.5, 2.5)
        p.setPen(QPen(QColor("#A3463B"), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(8.5, 8.5), QPointF(17.5, 8.5))
        p.setPen(QPen(QColor("#8D662C"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(8.5, 13.0), QPointF(17.5, 13.0))
        p.drawLine(QPointF(8.5, 17.0), QPointF(14.5, 17.0))
        p.end()


class LevelSelectionScreen(QWidget):
    """Archival 15-case Kho Hồ Sơ Vụ Án screen over Living Moonlit Detective Desk."""

    load_requested = Signal(str)
    back_requested = Signal()
    demo_gameplay_requested = Signal(str)

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        demo_mode: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LevelSelectionScreen")
        self.setProperty("surface", "paperCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._pixmap_loader = pixmap_loader
        self._demo_mode = bool(demo_mode)
        self._levels: list[LevelSummary] = []
        self._tiles_by_id: dict[str, CaseTile] = {}
        self._selected_puzzle_id: Optional[str] = None
        self._cover_views: dict[str, AssetImageView] = {}
        self._preview_buttons: dict[str, StyledButton] = {}
        self._group_list_layouts: dict[int, QVBoxLayout] = {}
        self._group_empty_labels: dict[int, QLabel] = {}
        self._group_subtitle_labels: dict[int, QLabel] = {}
        self._group_panels: dict[int, QFrame] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Top Masthead Bar
        self._back_button = StyledButton("← Màn hình chính", variant="ghost", parent=self)
        self._back_button.clicked.connect(self.back_requested.emit)

        self._catalog_badge = StatusLabel("KHO HỒ SƠ · 15 VỤ ÁN", tone="accent", parent=self)
        header = PageHeader(
            "Kho Hồ Sơ Vụ Án",
            subtitle="Chọn một hồ sơ vụ án bên dưới để bắt đầu điều tra",
            left_widget=self._back_button,
            right_widget=self._catalog_badge,
            parent=self,
        )
        root.addWidget(header)

        # 2. Scrollable Living Moonlit Desk Canvas containing Master Archival Dossier
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._canvas = _LivingArchiveBackdrop(self._scroll_area)
        canvas_v = QVBoxLayout(self._canvas)
        canvas_v.setContentsMargins(SPACING.space_5, 10, SPACING.space_5, 14)
        canvas_v.setSpacing(0)
        canvas_v.addStretch(1)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch(1)

        dossier = _ArchiveDossierSheet(self._canvas)
        dossier.setMinimumWidth(960)
        dossier.setMaximumWidth(1220)

        # ==================== MASTER ARCHIVE HEADER INSIDE DOSSIER ====================
        arch_head = QHBoxLayout()
        arch_head.setContentsMargins(24, 0, 120, 0)
        arch_head.setSpacing(14)

        arch_head.addWidget(_MiniDetectiveNotebookBadge(dossier), 0, Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)

        kicker = QLabel("GRIDUCTIVE · KHO LƯU TRỮ HỒ SƠ", dossier)
        kicker.setTextFormat(Qt.TextFormat.PlainText)
        kicker.setStyleSheet(
            "color: #9A382E; font-weight: 800; font-size: 11px; letter-spacing: 1px; background: transparent;"
        )
        title_col.addWidget(kicker)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(12)
        main_title = QLabel("Kho Hồ Sơ Vụ Án", dossier)
        main_title.setTextFormat(Qt.TextFormat.PlainText)
        main_title.setStyleSheet(
            f"color: #162436; font-family: '{TYPOGRAPHY.font_family_display[0]}', Georgia, serif; "
            "font-size: 27px; font-weight: 800; background: transparent;"
        )
        title_row.addWidget(main_title, 0)
        title_line = QFrame(dossier)
        title_line.setFixedHeight(1)
        title_line.setStyleSheet("background-color: #D2B788; border: none;")
        title_row.addWidget(title_line, 1, Qt.AlignmentFlag.AlignVCenter)
        title_col.addLayout(title_row)

        self._archive_count_sub = QLabel("15 hồ sơ đang chờ điều tra", dossier)
        self._archive_count_sub.setTextFormat(Qt.TextFormat.PlainText)
        self._archive_count_sub.setStyleSheet(
            "color: #5E4E3B; font-style: italic; font-size: 12.5px; background: transparent;"
        )
        title_col.addWidget(self._archive_count_sub)

        arch_head.addLayout(title_col, 1)
        dossier.content_layout.addLayout(arch_head)

        # ==================== 3 CLASSIC RIBBON-HEADED CASE COLUMNS ====================
        groups_row = QHBoxLayout()
        groups_row.setContentsMargins(0, 2, 0, 0)
        groups_row.setSpacing(14)

        for grid_size, key, ribbon_title, suspects, cover_asset, (bg_top, bg_bot) in _GROUP_SPECS:
            col_frame = QFrame(dossier)
            col_frame.setObjectName(f"ArchiveCol_{key}")
            col_frame.setStyleSheet(
                f"QFrame#ArchiveCol_{key} {{"
                "  background-color: rgba(252, 246, 234, 215);"
                "  border: 1.2px solid #D9C39A;"
                "  border-radius: 8px;"
                "}"
            )
            col_frame.setMinimumWidth(285)
            col_lay = QVBoxLayout(col_frame)
            col_lay.setContentsMargins(10, 10, 10, 10)
            col_lay.setSpacing(6)
            self._group_panels[grid_size] = col_frame

            col_lay.addWidget(
                _GroupBannerRibbon(ribbon_title, bg_top=bg_top, bg_bottom=bg_bot, parent=col_frame)
            )

            sub_lbl = QLabel(f"▦ Bàn cờ {suspects} nghi phạm · 5 vụ án", col_frame)
            sub_lbl.setTextFormat(Qt.TextFormat.PlainText)
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_lbl.setStyleSheet(
                "color: #4A3D2E; font-weight: 700; font-size: 12px; background: transparent; border: none;"
            )
            col_lay.addWidget(sub_lbl)
            self._group_subtitle_labels[grid_size] = sub_lbl

            # Framed A06 cover image with subtle interactive 3D hover tilt
            cover_mat = QFrame(col_frame)
            cover_mat.setStyleSheet(
                "background-color: #EFE2C8; border: 1px solid #CBB286; border-radius: 5px;"
            )
            mat_lay = QVBoxLayout(cover_mat)
            mat_lay.setContentsMargins(5, 5, 5, 5)
            cover = AssetImageView(
                cover_asset,
                scale_mode=ImageScaleMode.CONTAIN,
                prefer_derived=False,
                pixmap_loader=pixmap_loader,
                parent=cover_mat,
            )
            cover.setMinimumHeight(124)
            cover.setMaximumHeight(148)
            cover.set_interactive_tilt(True)
            mat_lay.addWidget(cover)
            col_lay.addWidget(cover_mat)
            self._cover_views[key] = cover

            # 5 Compact CaseTile rows
            tiles_host = QWidget(col_frame)
            tiles_host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            tiles_lay = QVBoxLayout(tiles_host)
            tiles_lay.setContentsMargins(0, 2, 0, 0)
            tiles_lay.setSpacing(2)

            empty_lbl = QLabel(
                f"Chưa có danh sách vụ án {key}.\nHệ thống sẽ nạp danh mục công khai tại đây.",
                tiles_host,
            )
            empty_lbl.setProperty("role", "paperCaption")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setWordWrap(True)
            tiles_lay.addWidget(empty_lbl)

            self._group_list_layouts[grid_size] = tiles_lay
            self._group_empty_labels[grid_size] = empty_lbl
            col_lay.addWidget(tiles_host, 1)

            quick_btn = StyledButton(
                f"Mở nhanh nhóm {key}",
                variant="paperSecondary",
                min_height=36,
                parent=col_frame,
            )
            quick_btn.clicked.connect(
                lambda _checked=False, gs=grid_size, k=key: self._on_group_quick_open(gs, k)
            )
            quick_btn.setVisible(False)
            col_lay.addWidget(quick_btn)
            self._preview_buttons[key] = quick_btn

            groups_row.addWidget(col_frame, 1)

        dossier.content_layout.addLayout(groups_row, 1)

        # ==================== INTEGRATED BOTTOM SELECTION STRIP ====================
        footer_bar = QFrame(dossier)
        footer_bar.setObjectName("ArchiveSelectionStrip")
        footer_bar.setStyleSheet(
            "QFrame#ArchiveSelectionStrip {"
            "  background-color: #F5EBD6;"
            "  border: 1.2px solid #D3BC90;"
            "  border-radius: 7px;"
            "}"
        )
        f_row = QHBoxLayout(footer_bar)
        f_row.setContentsMargins(14, 8, 12, 8)
        f_row.setSpacing(10)

        f_row.addWidget(_FooterDocIcon(footer_bar), 0, Qt.AlignmentFlag.AlignVCenter)

        self._footer_kicker = QLabel("HỒ SƠ ĐANG CHỌN", footer_bar)
        self._footer_kicker.setTextFormat(Qt.TextFormat.PlainText)
        self._footer_kicker.setStyleSheet(
            "color: #9A382E; font-weight: 800; font-size: 11.5px; letter-spacing: 0.6px; "
            "background: transparent; border: none;"
        )
        f_row.addWidget(self._footer_kicker, 0, Qt.AlignmentFlag.AlignVCenter)

        f_div = QFrame(footer_bar)
        f_div.setFixedSize(1, 20)
        f_div.setStyleSheet("background-color: #CFB78B; border: none;")
        f_row.addWidget(f_div, 0, Qt.AlignmentFlag.AlignVCenter)

        self._selection_label = QLabel(
            "Nhấp vào một hồ sơ ở trên để xem chi tiết và mở bàn cờ.",
            footer_bar,
        )
        self._selection_label.setTextFormat(Qt.TextFormat.PlainText)
        self._selection_label.setStyleSheet(
            "color: #1A2636; font-weight: 700; font-size: 14px; background: transparent; border: none;"
        )
        self._selection_label.setWordWrap(False)
        self._selection_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        f_row.addWidget(self._selection_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self._open_case_btn = _ArchiveOpenButton("Mở hồ sơ vụ án →", parent=footer_bar)
        self._open_case_btn.setEnabled(False)
        self._open_case_btn.clicked.connect(self._on_open_selected_clicked)
        f_row.addWidget(self._open_case_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        dossier.content_layout.addWidget(footer_bar)

        center_row.addWidget(dossier, 8)
        center_row.addStretch(1)
        canvas_v.addLayout(center_row)
        canvas_v.addStretch(1)

        self._scroll_area.setWidget(self._canvas)
        root.addWidget(self._scroll_area, 1)

    # ------------------------------------------------------------------
    # Public API & Properties (100% preserved)
    # ------------------------------------------------------------------

    def set_levels(self, levels: Iterable[Any]) -> None:
        normalized: list[LevelSummary] = []
        seen: set[str] = set()
        for raw in levels:
            item = normalize_level_summary(raw)
            if item.puzzle_id in seen:
                continue
            seen.add(item.puzzle_id)
            normalized.append(item)

        self._clear_tiles()
        self._levels = normalized

        counts = {3: 0, 4: 0, 5: 0}
        suspects_map = {3: 9, 4: 16, 5: 25}
        for summary in self._levels:
            layout = self._group_list_layouts.get(summary.grid_size)
            if layout is None:
                continue
            tile = CaseTile(summary, parent=self._group_panels[summary.grid_size])
            tile.case_selected.connect(self._on_tile_selected)
            tile.case_activated.connect(self._on_tile_activated)
            layout.addWidget(tile)
            self._tiles_by_id[summary.puzzle_id] = tile
            counts[summary.grid_size] += 1

        for gs, empty_lbl in self._group_empty_labels.items():
            empty_lbl.setVisible(counts[gs] == 0)
            self._group_subtitle_labels[gs].setText(
                f"▦ Bàn cờ {suspects_map[gs]} nghi phạm · {counts[gs]} vụ án"
            )

        total = len(self._levels)
        self._catalog_badge.set_status(f"KHO HỒ SƠ · {total} VỤ ÁN", tone="accent")
        self._archive_count_sub.setText(f"{total} hồ sơ đang chờ điều tra")

        if self._selected_puzzle_id not in self._tiles_by_id:
            self._selected_puzzle_id = None
            self._sync_selection_footer()

    def set_selected_puzzle(self, puzzle_id: Optional[str]) -> bool:
        if puzzle_id is None:
            if self._selected_puzzle_id and self._selected_puzzle_id in self._tiles_by_id:
                self._tiles_by_id[self._selected_puzzle_id].set_selected(False)
            self._selected_puzzle_id = None
            self._sync_selection_footer()
            return True

        tile = self._tiles_by_id.get(puzzle_id)
        if tile is None:
            return False
        if self._selected_puzzle_id and self._selected_puzzle_id in self._tiles_by_id:
            self._tiles_by_id[self._selected_puzzle_id].set_selected(False)
        self._selected_puzzle_id = puzzle_id
        tile.set_selected(True)
        self._sync_selection_footer()
        return True

    def set_reduced_motion(self, enabled: bool) -> None:
        self._canvas.set_reduced_motion(bool(enabled))
        for cover in self._cover_views.values():
            cover.set_reduced_motion(bool(enabled))

    @property
    def back_button(self) -> StyledButton:
        return self._back_button

    @property
    def open_case_button(self) -> StyledButton:
        return self._open_case_btn

    @property
    def cover_views(self) -> dict[str, AssetImageView]:
        return dict(self._cover_views)

    @property
    def preview_buttons(self) -> dict[str, StyledButton]:
        return dict(self._preview_buttons)

    @property
    def case_tiles(self) -> dict[str, CaseTile]:
        return dict(self._tiles_by_id)

    @property
    def levels(self) -> tuple[LevelSummary, ...]:
        return tuple(self._levels)

    @property
    def selected_puzzle_id(self) -> Optional[str]:
        return self._selected_puzzle_id

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    def _clear_tiles(self) -> None:
        for tile in self._tiles_by_id.values():
            parent_layout = self._group_list_layouts.get(tile.summary.grid_size)
            if parent_layout is not None:
                parent_layout.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()
        self._tiles_by_id.clear()

    def _on_tile_selected(self, puzzle_id: str) -> None:
        self.set_selected_puzzle(puzzle_id)

    def _on_tile_activated(self, puzzle_id: str) -> None:
        if puzzle_id in self._tiles_by_id:
            self.load_requested.emit(puzzle_id)

    def _on_open_selected_clicked(self) -> None:
        if self._selected_puzzle_id and self._selected_puzzle_id in self._tiles_by_id:
            self.load_requested.emit(self._selected_puzzle_id)

    def _on_group_quick_open(self, grid_size: int, grid_key: str) -> None:
        first_in_group = next((lvl for lvl in self._levels if lvl.grid_size == grid_size), None)
        if first_in_group is not None:
            self.set_selected_puzzle(first_in_group.puzzle_id)
            self.load_requested.emit(first_in_group.puzzle_id)
        else:
            self.demo_gameplay_requested.emit(grid_key)

    def _sync_selection_footer(self) -> None:
        tile = self._tiles_by_id.get(self._selected_puzzle_id or "")
        if tile is None:
            self._footer_kicker.setText("CHƯA CHỌN VỤ ÁN")
            self._selection_label.setText(
                "Nhấp vào một hồ sơ ở trên để xem chi tiết và mở bàn cờ."
            )
            self._open_case_btn.setEnabled(False)
            return
        s = tile.summary
        case_number, clean_title = split_case_number_and_name(s.puzzle_id, s.title)
        display_name = f"{case_number} · {clean_title}" if case_number else clean_title
        localized_diff = localize_difficulty(s.difficulty_label)
        diff_part = f" · {localized_diff}" if localized_diff else ""
        self._footer_kicker.setText("HỒ SƠ ĐANG CHỌN")
        self._selection_label.setText(
            f"{display_name}    |    ▦ {s.grid_size}×{s.grid_size}{diff_part}"
            + (f"\n{ s.archetype_label }" if s.archetype_label else "")
        )
        self._open_case_btn.setEnabled(True)
