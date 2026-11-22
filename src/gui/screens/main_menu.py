"""MainMenuScreen — Archival Notched Parchment Hero Dossier over Nocturne Detective Office.

Presents GRIDUCTIVE SOLVER on a cozy atmospheric detective office backdrop (A03
with breathing lamp warmth & floating golden dust motes), centered around a
2-layer vintage notched-corner parchment dossier card fastened with a top-left
3D brass binder clip, subtle magnifying glass / footprint / skyline watermarks,
bottom-right crimson wax seal with golden scales of justice, cartoon detective
emblem + wide GRIDUCTIVE logo, Display Serif headline, and 3 tactile beveled
editorial action buttons (Play / About / Exit).
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.screens.backdrop_screen import BackdropScreen
from src.gui.styles.tokens import SPACING, TYPOGRAPHY


class _DiamondStarRule(QWidget):
    """Thin brass horizontal rule with a centered 4-point brass star ornament."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(16)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        cx, cy = w * 0.5, h * 0.5
        span = min(w * 0.44, 210.0)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(QColor("#C8A86B"), 1.1)
        p.setPen(pen)
        p.drawLine(QPointF(cx - span, cy), QPointF(cx - 12.0, cy))
        p.drawLine(QPointF(cx + 12.0, cy), QPointF(cx + span, cy))

        # 4-point brass star
        arm, waist = 6.5, 2.0
        star = QPolygonF(
            [
                QPointF(cx, cy - arm),
                QPointF(cx + waist, cy - waist),
                QPointF(cx + arm, cy),
                QPointF(cx + waist, cy + waist),
                QPointF(cx, cy + arm),
                QPointF(cx - waist, cy + waist),
                QPointF(cx - arm, cy),
                QPointF(cx - waist, cy - waist),
            ]
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#C49646"))
        p.drawPolygon(star)
        p.end()


class _CircularGoldBezel(QFrame):
    """Circular metallic antique-gold bezel framing the detective emblem cleanly."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(102, 102)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy = self.width() * 0.5, self.height() * 0.5
        # Soft drop shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(34, 22, 10, 48))
        p.drawEllipse(QPointF(cx + 1.0, cy + 2.5), 48.0, 48.0)
        # Beveled gold ring
        grad = QLinearGradient(0.0, 0.0, float(self.width()), float(self.height()))
        grad.setColorAt(0.0, QColor("#EBD08E"))
        grad.setColorAt(0.5, QColor("#C19448"))
        grad.setColorAt(1.0, QColor("#8D6524"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#74511B"), 1.0))
        p.drawEllipse(QPointF(cx, cy), 48.0, 48.0)
        # Deep navy inner well
        p.setBrush(QColor("#17263B"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 44.5, 44.5)
        p.end()


class _MenuActionButton(StyledButton):
    """Beveled detective editorial CTA button with crisp left vector icon & right chevron."""

    def __init__(
        self,
        text: str,
        *,
        variant: str = "primary",
        icon_kind: str = "folder",
        min_height: int = 46,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, variant=variant, min_height=min_height, parent=parent)
        self._icon_kind = icon_kind
        self.setObjectName(f"MenuCta_{icon_kind}")

        if variant == "primary":
            self.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #BD8D3E, stop:0.5 #A37226, stop:1 #875A18);"
                "  color: #FFFDF7;"
                "  border: 2px solid #6E4610;"
                "  border-radius: 9px;"
                "  font-weight: 700;"
                "  font-size: 16px;"
                "  padding: 0 40px 0 44px;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #CC9B4B, stop:0.5 #B27F2E, stop:1 #95641C);"
                "  border: 2px solid #8A5B18;"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8D601C, stop:1 #784E14);"
                "}"
            )
        elif variant == "secondary":
            self.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FDF8EC, stop:1 #F1E5CC);"
                "  color: #16253A;"
                "  border: 1.5px solid #BFA374;"
                "  border-radius: 9px;"
                "  min-height: 42px;"
                "  font-weight: 700;"
                "  font-size: 15.5px;"
                "  padding: 0 40px 0 44px;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFDF6, stop:1 #F6EBD4);"
                "  border: 1.5px solid #A8844A;"
                "}"
                "QPushButton:pressed {"
                "  background: #E9DAB9;"
                "}"
            )
        else:
            self.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F4EAD6, stop:1 #E6D7BC);"
                "  color: #463A2C;"
                "  border: 1.4px solid #C4AD86;"
                "  border-radius: 9px;"
                "  font-weight: 600;"
                "  font-size: 15px;"
                "  padding: 0 40px 0 44px;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F9F0DF, stop:1 #EDE0C7);"
                "  border: 1.4px solid #A88B59;"
                "  color: #241D14;"
                "}"
                "QPushButton:pressed {"
                "  background: #DDCCA9;"
                "}"
            )
        self.setMinimumHeight(min_height)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        w, h = float(self.width()), float(self.height())
        if w <= 40 or h <= 20:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Inner metallic gold highlight rim on primary gold button
        if self.variant == "primary":
            p.setPen(QPen(QColor(248, 224, 166, 170), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(3.0, 3.0, w - 6.0, h - 6.0), 6.5, 6.5)

        cy = h * 0.5
        icon_col = (
            QColor("#FFF8E8")
            if self.variant == "primary"
            else (QColor("#4F3B20") if self.variant == "secondary" else QColor("#69553B"))
        )
        chev_col = (
            QColor(255, 248, 232, 220)
            if self.variant == "primary"
            else QColor(115, 92, 60, 195)
        )

        # Left vector icon
        ix = 26.0
        if self._icon_kind == "folder":
            p.setPen(QPen(icon_col, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(QColor(255, 248, 232, 46))
            folder = QPainterPath(QPointF(ix - 11.0, cy - 8.5))
            folder.lineTo(ix - 3.5, cy - 8.5)
            folder.lineTo(ix - 1.0, cy - 5.5)
            folder.lineTo(ix + 11.0, cy - 5.5)
            folder.lineTo(ix + 11.0, cy + 8.0)
            folder.lineTo(ix - 11.0, cy + 8.0)
            folder.closeSubpath()
            p.drawPath(folder)
        elif self._icon_kind == "book":
            p.setPen(QPen(icon_col, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            left_pg = QPainterPath(QPointF(ix, cy - 6.5))
            left_pg.quadTo(QPointF(ix - 5.5, cy - 8.5), QPointF(ix - 11.0, cy - 6.5))
            left_pg.lineTo(ix - 11.0, cy + 7.5)
            left_pg.quadTo(QPointF(ix - 5.5, cy + 5.5), QPointF(ix, cy + 7.5))
            left_pg.closeSubpath()
            right_pg = QPainterPath(QPointF(ix, cy - 6.5))
            right_pg.quadTo(QPointF(ix + 5.5, cy - 8.5), QPointF(ix + 11.0, cy - 6.5))
            right_pg.lineTo(ix + 11.0, cy + 7.5)
            right_pg.quadTo(QPointF(ix + 5.5, cy + 5.5), QPointF(ix, cy + 7.5))
            right_pg.closeSubpath()
            p.drawPath(left_pg)
            p.drawPath(right_pg)
        else:
            # Crisp power icon
            p.setPen(QPen(icon_col, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(ix - 8.0, cy - 7.0, 16.0, 16.0), 130 * 16, 280 * 16)
            p.drawLine(QPointF(ix, cy - 9.5), QPointF(ix, cy - 0.5))

        # Right chevron ">"
        cx = w - 22.0
        p.setPen(QPen(chev_col, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(cx - 3.5, cy - 5.5), QPointF(cx + 2.5, cy))
        p.drawLine(QPointF(cx + 2.5, cy), QPointF(cx - 3.5, cy + 5.5))
        p.end()


class _MainMenuDossierCard(QFrame):
    """Vintage double-gold notched parchment dossier card with brass clip, watermarks & wax seal."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MainMenuDossierCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(52, 42, 52, 48)
        self.content_layout.setSpacing(12)

    @staticmethod
    def _notched_path(rect: QRectF, notch: float) -> QPainterPath:
        l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        n = min(notch, rect.width() * 0.12, rect.height() * 0.12)
        d = n * 2.0
        path = QPainterPath(QPointF(l + n, t))
        path.lineTo(r - n, t)
        path.arcTo(QRectF(r - n, t - n, d, d), 180.0, 90.0)
        path.lineTo(r, b - n)
        path.arcTo(QRectF(r - n, b - n, d, d), 90.0, 90.0)
        path.lineTo(l + n, b)
        path.arcTo(QRectF(l - n, b - n, d, d), 0.0, 90.0)
        path.lineTo(l, t + n)
        path.arcTo(QRectF(l - n, t - n, d, d), 270.0, 90.0)
        path.closeSubpath()
        return path

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        if w <= 40 or h <= 40:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(22.0, 22.0, w - 44.0, h - 44.0)

        # 1. Stacked tilted cream folder sheets peeking out behind top-left & right/bottom
        for tx, ty, rot, bw, bh, col in (
            (outer.left() + 82.0, outer.top() + 36.0, -7.5, 190.0, 110.0, "#DFCCA8"),
            (outer.left() + 92.0, outer.top() + 30.0, -3.5, 175.0, 95.0, "#EADBC0"),
            (outer.right() - 78.0, outer.bottom() - 56.0, 6.2, 160.0, 125.0, "#DEC9A4"),
        ):
            p.save()
            p.translate(tx, ty)
            p.rotate(rot)
            p.setPen(QPen(QColor("#B69766"), 1.0))
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(-bw * 0.5, -bh * 0.5, bw, bh), 5.0, 5.0)
            p.restore()

        # 2. Deep cinematic tabletop drop shadow
        for expand, dy, alpha in ((8.0, 10.0, 32), (4.0, 6.0, 52), (1.5, 3.0, 72)):
            sh = self._notched_path(outer.adjusted(-expand, dy - expand * 0.3, expand, dy + expand * 0.3), 18.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(12, 8, 5, alpha))
            p.drawPath(sh)

        # 3. Main notched parchment card with warm radial aging gradient
        main_path = self._notched_path(outer, 18.0)
        parch = QRadialGradient(outer.center(), max(outer.width(), outer.height()) * 0.68)
        parch.setColorAt(0.0, QColor("#FCF6E8"))
        parch.setColorAt(0.68, QColor("#F7ECD5"))
        parch.setColorAt(1.0, QColor("#EBDBBC"))
        p.setBrush(parch)

        # Beveled metallic gold outer frame
        frame_grad = QLinearGradient(outer.topLeft(), outer.bottomRight())
        frame_grad.setColorAt(0.0, QColor("#ECD08F"))
        frame_grad.setColorAt(0.45, QColor("#C6994B"))
        frame_grad.setColorAt(1.0, QColor("#9C702A"))
        p.setPen(QPen(frame_grad, 3.2))
        p.drawPath(main_path)

        # Inner fine antique-gold notched contour
        inner_rect = outer.adjusted(7.0, 7.0, -7.0, -7.0)
        inner_path = self._notched_path(inner_rect, 14.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#C8A76E"), 1.2))
        p.drawPath(inner_path)

        # 4. Subtle vintage detective watermarks inside the parchment sheet
        p.save()
        p.setClipPath(inner_path)
        self._draw_watermarks(p, inner_rect)
        p.restore()

        # 5. Top-left 3D Antique Brass Binder Clip clamping top edge of dossier
        self._draw_binder_clip(p, QPointF(outer.left() + 86.0, outer.top()))

        # 6. Bottom-right Glossy Crimson Wax Seal with Golden Scales of Justice & Ribbon Tails
        self._draw_wax_seal(p, QPointF(outer.right() - 22.0, outer.bottom() - 36.0))
        p.end()

    @staticmethod
    def _draw_watermarks(p: QPainter, rect: QRectF) -> None:
        # Top-right magnifying glass line-art watermark
        wm_col = QColor(158, 126, 78, 38)
        lens_c = QPointF(rect.right() - 48.0, rect.top() + 50.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(wm_col, 2.2))
        p.drawEllipse(lens_c, 26.0, 26.0)
        p.setPen(QPen(wm_col, 1.2))
        p.drawEllipse(lens_c, 21.0, 21.0)
        p.setPen(QPen(wm_col, 5.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(lens_c + QPointF(-18.5, 18.5), lens_c + QPointF(-35.0, 35.0))

        # Mid-left subtle shoe footprints watermark
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(158, 126, 78, 34))
        for fx, fy, rot in ((rect.left() + 34.0, rect.bottom() - 122.0, -24.0), (rect.left() + 54.0, rect.bottom() - 94.0, -18.0)):
            p.save()
            p.translate(fx, fy)
            p.rotate(rot)
            p.drawEllipse(QPointF(0.0, -5.0), 5.5, 9.5)
            p.drawRoundedRect(QRectF(-4.2, 6.5, 8.4, 6.5), 3.0, 3.0)
            p.restore()

        # Bottom-center soft detective city skyline silhouette
        p.setBrush(QColor(158, 126, 78, 30))
        base_y = rect.bottom()
        cx = rect.center().x()
        skyline = (
            (-168, 22, 12), (-144, 18, 22), (-124, 24, 15), (-98, 20, 28),
            (-76, 18, 19), (-54, 24, 34), (-28, 18, 24), (-8, 22, 42),
            (16, 18, 28), (36, 24, 20), (62, 18, 32), (82, 22, 22),
            (106, 20, 16), (128, 24, 24), (154, 20, 13),
        )
        for ox, bw, bh in skyline:
            p.drawRect(QRectF(cx + ox, base_y - bh, bw, bh))

    @staticmethod
    def _draw_binder_clip(p: QPainter, anchor: QPointF) -> None:
        p.save()
        p.translate(anchor)
        p.rotate(-6.0)
        # Double wire handles
        wire = QRectF(-9.5, -20.0, 19.0, 18.0)
        p.setPen(QPen(QColor("#5E4118"), 2.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(wire, 7.0, 7.0)
        p.setPen(QPen(QColor("#E3C27A"), 1.2))
        p.drawRoundedRect(wire.adjusted(0.6, 0.6, -0.6, -0.6), 6.5, 6.5)

        # Dark bronze-brass clamp body
        clamp = QRectF(-22.0, -5.0, 44.0, 20.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 10, 4, 58))
        p.drawRoundedRect(clamp.translated(2.0, 3.5), 3.0, 3.0)

        grad = QLinearGradient(clamp.topLeft(), clamp.bottomLeft())
        grad.setColorAt(0.0, QColor("#7B5A2E"))
        grad.setColorAt(0.35, QColor("#4A3419"))
        grad.setColorAt(0.75, QColor("#2D1F0E"))
        grad.setColorAt(1.0, QColor("#573E1E"))
        p.setPen(QPen(QColor("#C8A25B"), 1.2))
        p.setBrush(grad)
        p.drawRoundedRect(clamp, 3.0, 3.0)

        # Specular gold highlight strip along clamp edge
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(238, 208, 144, 155))
        p.drawRect(QRectF(clamp.left() + 4.0, clamp.bottom() - 4.0, clamp.width() - 8.0, 2.0))
        p.restore()

    @staticmethod
    def _draw_wax_seal(p: QPainter, center: QPointF) -> None:
        p.save()
        p.translate(center)

        # Twin crimson-and-gold ribbon tails hanging neatly below seal
        for angle, ox in ((-16.0, -9.0), (14.0, 9.0)):
            p.save()
            p.translate(ox, 17.0)
            p.rotate(angle)
            tail = QPolygonF(
                [
                    QPointF(-9.0, 0.0),
                    QPointF(9.0, 0.0),
                    QPointF(9.0, 28.0),
                    QPointF(0.0, 20.5),
                    QPointF(-9.0, 28.0),
                ]
            )
            p.setPen(QPen(QColor("#D9B263"), 1.2))
            p.setBrush(QColor("#962B23"))
            p.drawPolygon(tail)
            p.restore()

        # Soft 3D elevation shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(22, 10, 6, 75))
        p.drawEllipse(QPointF(2.0, 4.0), 29.0, 29.0)

        # Organic wavy wax outer rim
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
        wax.setColorAt(0.0, QColor("#CC4B3E"))
        wax.setColorAt(0.55, QColor("#9F2D24"))
        wax.setColorAt(1.0, QColor("#6E1A14"))
        p.setBrush(wax)
        p.setPen(QPen(QColor("#5C140F"), 1.3))
        p.drawPath(rim)

        # Recessed inner gold-rimmed seal face
        p.setBrush(QColor("#8C241D"))
        p.setPen(QPen(QColor("#DFB86C"), 1.4))
        p.drawEllipse(QPointF(0.0, 0.0), 20.5, 20.5)

        # Golden Scales of Justice emblem
        gold_pen = QPen(QColor("#F3D591"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(gold_pen)
        p.drawLine(QPointF(0.0, -10.5), QPointF(0.0, 10.5))
        p.drawLine(QPointF(-6.5, 10.5), QPointF(6.5, 10.5))
        p.drawLine(QPointF(-10.5, -5.5), QPointF(10.5, -5.5))
        for sx in (-10.5, 10.5):
            p.drawLine(QPointF(sx, -5.5), QPointF(sx - 3.4, 2.0))
            p.drawLine(QPointF(sx, -5.5), QPointF(sx + 3.4, 2.0))
            p.drawArc(QRectF(sx - 3.8, 0.5, 7.6, 4.2), 180 * 16, 180 * 16)
        p.restore()


class _MenuAtmosphereLayer(QWidget):
    """Subtle living golden lamp glow & drifting dust motes over the A03 office backdrop."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._phase: float = 0.0
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)
        self._motes: tuple[tuple[float, float, float, float, float, float], ...] = tuple(
            (
                ((i * 37 + 7) % 100) / 100.0,
                ((i * 53 + 19) % 100) / 100.0,
                0.35 + 0.65 * ((i % 4) / 3.0),
                0.45 + 0.65 * ((i % 3) / 2.0),
                (i * 1.41) % (2.0 * math.pi),
                1.4 + 2.4 * ((i % 3) / 2.0),
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
        self._phase = (self._phase + 0.038) % (200.0 * math.pi)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        if w <= 4 or h <= 4:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)

        phase = 0.0 if self._reduced_motion else self._phase

        # Breathing warm brass desk lamp glow on left side
        lamp_pt = QPointF(w * 0.085, h * 0.65)
        lamp_pulse = 0.84 + 0.16 * math.sin(phase * 1.45)
        lamp_r = min(w, h) * 0.34
        lamp_g = QRadialGradient(lamp_pt, lamp_r)
        lamp_g.setColorAt(0.0, QColor(255, 224, 146, int(84 * lamp_pulse)))
        lamp_g.setColorAt(0.45, QColor(238, 174, 82, int(36 * lamp_pulse)))
        lamp_g.setColorAt(1.0, QColor(238, 174, 82, 0))
        p.setBrush(lamp_g)
        p.drawEllipse(lamp_pt, lamp_r, lamp_r)

        # 24 gently floating golden dust motes
        for x0, y0, depth, spd, p0, rad in self._motes:
            t = phase * spd + p0
            mx = (x0 * w + math.sin(t * 0.8) * 16.0 * depth) % w
            my = (y0 * h - ((phase * 7.5 * spd * depth) % h)) % h
            tw = 0.4 + 0.6 * math.sin(t * 2.0)
            alpha = int((44 + 82 * depth) * tw)
            mg = QRadialGradient(QPointF(mx, my), rad * 2.8)
            mg.setColorAt(0.0, QColor(255, 232, 168, alpha))
            mg.setColorAt(0.45, QColor(238, 188, 96, int(alpha * 0.4)))
            mg.setColorAt(1.0, QColor(238, 188, 96, 0))
            p.setBrush(mg)
            p.drawEllipse(QPointF(mx, my), rad * 2.8, rad * 2.8)
        p.end()


class MainMenuScreen(BackdropScreen):
    """Centered Archival Notched Parchment Main Menu preserving Play / About / Exit contracts."""

    play_requested = Signal()
    about_requested = Signal()
    how_to_play_requested = Signal()  # Preserved for backward API compatibility
    exit_requested = Signal()

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        demo_mode: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            AssetId.A03_MAIN_MENU_BACKGROUND,
            scrim_rgba=(20, 16, 14, 92),
            pixmap_loader=pixmap_loader,
            parent=parent,
        )
        self.setObjectName("MainMenuScreen")
        self._demo_mode = bool(demo_mode)

        # Living warm lamp & golden dust atmosphere layer behind foreground layout
        self._atmosphere = _MenuAtmosphereLayer(self)
        stack_layout = self.layout()
        if stack_layout is not None:
            stack_layout.addWidget(self._atmosphere, 0, 0)
            self._foreground.raise_()

        outer = QVBoxLayout()
        outer.setContentsMargins(SPACING.space_6, SPACING.space_4, SPACING.space_6, SPACING.space_4)
        outer.setSpacing(SPACING.space_3)
        self.body_layout.addLayout(outer, 1)

        outer.addStretch(1)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch(1)

        # Centerpiece Vintage Double-Gold Notched Parchment Dossier Card
        hero_card = _MainMenuDossierCard(self)
        hero_card.setMinimumWidth(660)
        hero_card.setMaximumWidth(760)

        # Hidden backward-compatible status badge
        self._demo_badge = StatusLabel("HỒ SƠ PHÁ ÁN", tone="paperNeutral", parent=hero_card)
        self._demo_badge.setVisible(False)

        # 1. Centered Brand Row: Gold-Bezel Circular Detective Emblem | Vertical Rule | Wide Logo
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 2, 0, 2)
        brand_row.setSpacing(20)
        brand_row.addStretch(1)

        bezel = _CircularGoldBezel(hero_card)
        bezel_lay = QHBoxLayout(bezel)
        bezel_lay.setContentsMargins(5, 5, 5, 5)
        self._emblem_view = AssetImageView(
            AssetId.A04_APP_EMBLEM,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=bezel,
        )
        self._emblem_view.setFixedSize(92, 92)
        self._emblem_view.set_interactive_tilt(True)
        bezel_lay.addWidget(self._emblem_view)
        brand_row.addWidget(bezel, 0, Qt.AlignmentFlag.AlignVCenter)

        v_div = QFrame(hero_card)
        v_div.setFixedSize(1, 68)
        v_div.setStyleSheet("background-color: #C9AF7E; border: none;")
        brand_row.addWidget(v_div, 0, Qt.AlignmentFlag.AlignVCenter)

        self._logo_view = AssetImageView(
            AssetId.A04_LOGO_WIDE,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=hero_card,
        )
        self._logo_view.setMinimumSize(305, 102)
        self._logo_view.setMaximumSize(365, 118)
        self._logo_view.set_interactive_tilt(True)
        brand_row.addWidget(self._logo_view, 0, Qt.AlignmentFlag.AlignVCenter)

        brand_row.addStretch(1)
        hero_card.content_layout.addLayout(brand_row)

        # 2. Bold Display Serif Headline
        headline = QLabel("Hồ Sơ Phá Án · Suy Luận Logic", hero_card)
        headline.setTextFormat(Qt.TextFormat.PlainText)
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setWordWrap(True)
        headline.setStyleSheet(
            f"color: #142438; font-family: '{TYPOGRAPHY.font_family_display[0]}', Georgia, serif; "
            "font-size: 29px; font-weight: 800; letter-spacing: 0.4px; background: transparent;"
        )
        headline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hero_card.content_layout.addWidget(headline)

        # 3. Centered Brass Rule with 4-Point Star Ornament
        hero_card.content_layout.addWidget(_DiamondStarRule(hero_card))

        # 4. Italic Editorial Tagline
        tagline = QLabel(
            "Khám phá manh mối công khai và suy luận danh tính từng nghi phạm bằng tư duy logic.",
            hero_card,
        )
        tagline.setTextFormat(Qt.TextFormat.PlainText)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setWordWrap(True)
        tagline.setStyleSheet(
            "color: #493D2F; font-style: italic; font-size: 13.5px; background: transparent;"
        )
        tagline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hero_card.content_layout.addWidget(tagline)

        hero_card.content_layout.addSpacing(8)

        # 5. Centered 3-Tier Editorial Action Buttons (preserving width >= 300 & Play/About/Exit contracts)
        btn_wrap = QHBoxLayout()
        btn_wrap.addStretch(1)

        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 0, 0, 0)
        btn_col.setSpacing(10)

        self._play_button = _MenuActionButton(
            "Chơi ngay — Mở Kho Hồ Sơ",
            variant="primary",
            icon_kind="folder",
            min_height=52,
            parent=hero_card,
        )
        self._play_button.setMinimumWidth(300)
        self._play_button.setMaximumWidth(380)
        self._play_button.setFixedWidth(366)
        self._play_button.setMinimumWidth(300)
        self._play_button.setToolTip("Mở Kho Hồ Sơ Vụ Án")
        self._play_button.clicked.connect(self.play_requested.emit)
        btn_col.addWidget(self._play_button)

        self._about_button = _MenuActionButton(
            "Giới thiệu",
            variant="secondary",
            icon_kind="book",
            min_height=46,
            parent=hero_card,
        )
        self._about_button.setMinimumWidth(300)
        self._about_button.setMaximumWidth(380)
        self._about_button.setFixedWidth(366)
        self._about_button.setMinimumWidth(300)
        self._about_button.setToolTip("Giới thiệu đồ án GRIDUCTIVE SOLVER và thông tin nhóm thực hiện")
        self._about_button.clicked.connect(self.about_requested.emit)
        btn_col.addWidget(self._about_button)

        self._exit_button = _MenuActionButton(
            "Thoát ứng dụng",
            variant="tertiary",
            icon_kind="power",
            min_height=46,
            parent=hero_card,
        )
        self._exit_button.setMinimumWidth(300)
        self._exit_button.setMaximumWidth(380)
        self._exit_button.setFixedWidth(366)
        self._exit_button.setMinimumWidth(300)
        self._exit_button.setToolTip("Đóng ứng dụng GRIDUCTIVE SOLVER")
        self._exit_button.clicked.connect(self.exit_requested.emit)
        btn_col.addWidget(self._exit_button)

        btn_wrap.addLayout(btn_col)
        btn_wrap.addStretch(1)
        hero_card.content_layout.addLayout(btn_wrap)

        center_row.addWidget(hero_card)
        center_row.addStretch(1)
        outer.addLayout(center_row)

        outer.addStretch(1)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._atmosphere.set_reduced_motion(bool(enabled))
        self._emblem_view.set_reduced_motion(bool(enabled))
        self._logo_view.set_reduced_motion(bool(enabled))

    @property
    def emblem_view(self) -> AssetImageView:
        return self._emblem_view

    @property
    def logo_view(self) -> AssetImageView:
        return self._logo_view

    @property
    def play_button(self) -> StyledButton:
        return self._play_button

    @property
    def about_button(self) -> StyledButton:
        return self._about_button

    @property
    def exit_button(self) -> StyledButton:
        return self._exit_button

    def set_enabled(self, enabled: bool) -> None:
        self._play_button.setEnabled(enabled)
        self._about_button.setEnabled(enabled)
        self._exit_button.setEnabled(enabled)
