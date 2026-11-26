"""ResultsScreen — Wide 2-Column Archival "Biên Bản Khép Án" Dossier over Living Noir Desk.

Displays the confirmed ``ResultsView`` metrics supplied by PlayController on a
cozy moonlit detective office backdrop (lamp glow, rising coffee steam, lens glint,
moon corona, twinkling city lights, floating golden dust) with a centered 2-column
vintage notched parchment dossier:
  - Left column: Khép Án crest with 3D stamp pop celebration, laurel-flanked
    verdict heading, 100% completion seal, and case ID / grid size metadata.
  - Right column: 2×2 notched antique-gold metric cards (count-up animation)
    and SAT deduction query count.
  - Bottom row: 4 vector-icon action buttons (Chơi lại / Vụ án tiếp theo → /
    Kho hồ sơ / Trang chủ).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
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
    QShowEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import (
    EASE_OUT,
    SCALE_STAMP_START,
    SPRING_CHECK_POP,
    SPRING_NUMBER,
    build_easing,
)
from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.page_header import PageHeader
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.screens.backdrop_screen import BackdropScreen
from src.gui.styles.tokens import SPACING, TYPOGRAPHY
from src.gui.view_models import ResultsView, normalize_results_view


def _format_elapsed_ms(elapsed_ms: Optional[float]) -> str:
    if elapsed_ms is None:
        return "—"
    if elapsed_ms < 1000.0:
        return f"{int(round(elapsed_ms))} ms"
    seconds = elapsed_ms / 1000.0
    if seconds < 60.0:
        return f"{seconds:.1f} giây"
    minutes = int(seconds // 60)
    rem = seconds % 60.0
    return f"{minutes} phút {rem:.1f} giây"


def _notched_rect_path(rect: QRectF, notch: float) -> QPainterPath:
    """Build a vintage certificate rectangle with 4 concave quarter-circle corners."""
    l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
    n = min(notch, rect.width() * 0.16, rect.height() * 0.24)
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


def _draw_vector_glyph(p: QPainter, kind: str, center: QPointF, size: float, color: QColor) -> None:
    """Draw crisp vector icons (zero emojis) for stat cards, metadata rows, and CTA buttons."""
    cx, cy = center.x(), center.y()
    r = size * 0.5
    p.save()
    if kind == "team":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        for ox in (-r * 0.62, r * 0.62):
            p.drawEllipse(QPointF(cx + ox, cy - r * 0.26), r * 0.24, r * 0.24)
            p.drawRoundedRect(QRectF(cx + ox - r * 0.34, cy + r * 0.06, r * 0.68, r * 0.52), 2.5, 2.5)
        p.setBrush(color.darker(115))
        p.drawEllipse(QPointF(cx, cy - r * 0.38), r * 0.30, r * 0.30)
        p.drawRoundedRect(QRectF(cx - r * 0.42, cy - r * 0.02, r * 0.84, r * 0.66), 3.0, 3.0)
    elif kind == "clock":
        p.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QColor(252, 246, 232, 200))
        p.drawEllipse(QPointF(cx, cy), r * 0.78, r * 0.78)
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy - r * 0.44))
        p.drawLine(QPointF(cx, cy), QPointF(cx + r * 0.36, cy + r * 0.16))
    elif kind == "nodes":
        p.setPen(QPen(color, 1.5))
        pts = (
            QPointF(cx, cy - r * 0.58),
            QPointF(cx - r * 0.56, cy + r * 0.42),
            QPointF(cx + r * 0.56, cy + r * 0.42),
            QPointF(cx, cy + r * 0.06),
        )
        for pt in pts[:3]:
            p.drawLine(pts[3], pt)
        p.setBrush(color)
        for pt in pts:
            p.drawEllipse(pt, r * 0.18, r * 0.18)
    elif kind == "bulb":
        p.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QColor(246, 208, 122, 110))
        p.drawEllipse(QPointF(cx, cy - r * 0.12), r * 0.44, r * 0.48)
        p.drawLine(QPointF(cx - r * 0.24, cy + r * 0.46), QPointF(cx + r * 0.24, cy + r * 0.46))
        p.drawLine(QPointF(cx - r * 0.18, cy + r * 0.66), QPointF(cx + r * 0.18, cy + r * 0.66))
        for deg in (-140, -90, -40, 15, 165):
            ang = math.radians(deg)
            p.drawLine(
                QPointF(cx + math.cos(ang) * r * 0.64, cy - r * 0.12 + math.sin(ang) * r * 0.64),
                QPointF(cx + math.cos(ang) * r * 0.88, cy - r * 0.12 + math.sin(ang) * r * 0.88),
            )
    elif kind == "gear":
        p.setPen(QPen(color, 1.5))
        p.setBrush(color)
        for i in range(8):
            ang = i * (math.pi / 4.0)
            p.save()
            p.translate(cx + math.cos(ang) * r * 0.62, cy + math.sin(ang) * r * 0.62)
            p.rotate(math.degrees(ang))
            p.drawRect(QRectF(-r * 0.16, -r * 0.14, r * 0.32, r * 0.28))
            p.restore()
        p.drawEllipse(QPointF(cx, cy), r * 0.56, r * 0.56)
        p.setBrush(QColor("#FAF3E4"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.24, r * 0.24)
    elif kind == "folder":
        p.setPen(QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(color)
        path = QPainterPath(QPointF(cx - r * 0.72, cy - r * 0.52))
        path.lineTo(cx - r * 0.18, cy - r * 0.52)
        path.lineTo(cx, cy - r * 0.30)
        path.lineTo(cx + r * 0.72, cy - r * 0.30)
        path.lineTo(cx + r * 0.72, cy + r * 0.56)
        path.lineTo(cx - r * 0.72, cy + r * 0.56)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "grid":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        step = r * 0.52
        box = r * 0.38
        for gy in (-1, 0, 1):
            for gx in (-1, 0, 1):
                p.drawRoundedRect(QRectF(cx + gx * step - box * 0.5, cy + gy * step - box * 0.5, box, box), 1.0, 1.0)
    elif kind == "refresh":
        p.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - r * 0.62, cy - r * 0.62, r * 1.24, r * 1.24), 35 * 16, 285 * 16)
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(
            QPolygonF(
                [
                    QPointF(cx + r * 0.76, cy - r * 0.22),
                    QPointF(cx + r * 0.24, cy - r * 0.32),
                    QPointF(cx + r * 0.52, cy - r * 0.74),
                ]
            )
        )
    elif kind == "home":
        p.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(color)
        roof = QPolygonF(
            [
                QPointF(cx, cy - r * 0.72),
                QPointF(cx + r * 0.78, cy - r * 0.04),
                QPointF(cx - r * 0.78, cy - r * 0.04),
            ]
        )
        p.drawPolygon(roof)
        p.drawRect(QRectF(cx - r * 0.52, cy - r * 0.06, r * 1.04, r * 0.72))
        p.setBrush(QColor("#FBF5E8"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(cx - r * 0.16, cy + r * 0.18, r * 0.32, r * 0.48))
    p.restore()


class _LivingResultsBackdrop(QWidget):
    """Noir moonlit detective desk backdrop with lamp glow, coffee steam, moon & dust motes."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        bg_path = Path(__file__).resolve().parents[3] / "assets" / "backgrounds" / "A07_results_desk_backdrop.png"
        self._raw_bg = QPixmap(str(bg_path)) if bg_path.is_file() else QPixmap()
        self._scaled_bg: Optional[QPixmap] = None
        self._cached_sz = QSize(0, 0)
        self._phase: float = 0.0
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)

        self._motes: tuple[tuple[float, float, float, float, float, float], ...] = tuple(
            (
                (0.02 + ((i * 19) % 16) * 0.011) if (i % 2 == 0) else (0.82 + ((i * 17) % 16) * 0.010),
                0.05 + ((i * 31 + 11) % 88) / 100.0,
                0.45 + 0.55 * ((i % 4) / 3.0),
                0.50 + 0.65 * ((i % 3) / 2.0),
                (i * 1.47) % (2.0 * math.pi),
                1.4 + 2.3 * ((i % 3) / 2.0),
            )
            for i in range(28)
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

        # 1. Breathing warm brass desk lamp glow (top-left)
        lamp_pt = QPointF(w * 0.145, h * 0.285)
        lamp_p = 0.85 + 0.15 * math.sin(phase * 1.55)
        lamp_r = min(w, h) * 0.28
        lg = QRadialGradient(lamp_pt, lamp_r)
        lg.setColorAt(0.0, QColor(255, 232, 165, int(92 * lamp_p)))
        lg.setColorAt(0.45, QColor(242, 182, 86, int(38 * lamp_p)))
        lg.setColorAt(1.0, QColor(242, 182, 86, 0))
        p.setBrush(lg)
        p.drawEllipse(lamp_pt, lamp_r, lamp_r)

        # 2. Shimmering full moon corona (top-right)
        moon_pt = QPointF(w * 0.935, h * 0.135)
        moon_p = 0.84 + 0.16 * math.sin(phase * 1.1)
        moon_r = min(w, h) * 0.22
        mg = QRadialGradient(moon_pt, moon_r)
        mg.setColorAt(0.0, QColor(255, 246, 214, int(86 * moon_p)))
        mg.setColorAt(0.42, QColor(242, 212, 152, int(34 * moon_p)))
        mg.setColorAt(1.0, QColor(242, 212, 152, 0))
        p.setBrush(mg)
        p.drawEllipse(moon_pt, moon_r, moon_r)

        # 3. Curling rising steam wisps over the Sherlock mug (bottom-left)
        mug_x, mug_y = w * 0.215, h * 0.72
        for s_idx in range(3):
            prog = (phase * 0.22 + s_idx * 0.333) % 1.0
            fade = math.sin(prog * math.pi)
            if fade > 0.05:
                y0 = mug_y - prog * h * 0.03
                y1 = mug_y - (0.08 + prog * 0.14) * h
                w1 = math.sin(phase * 1.3 + s_idx * 2.0) * 9.0
                ox = (s_idx - 1) * 7.0
                st = QPainterPath(QPointF(mug_x + ox, y0))
                st.cubicTo(
                    QPointF(mug_x + ox + w1, (y0 + y1) * 0.5 + 12.0),
                    QPointF(mug_x + ox - w1, (y0 + y1) * 0.5 - 12.0),
                    QPointF(mug_x + ox + w1 * 0.5, y1),
                )
                p.setPen(QPen(QColor(255, 242, 216, int(42 * fade)), 2.8 - prog * 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(st)

        p.setPen(Qt.PenStyle.NoPen)

        # 4. Magnifying glass lens optical glint (bottom-left)
        lens_pt = QPointF(w * 0.174, h * 0.925)
        lr = min(w, h) * 0.065
        shift = math.sin(phase * 1.35) * lr * 0.5
        gl = QRadialGradient(lens_pt + QPointF(shift, -shift * 0.3), lr)
        la = int(68 + 38 * math.sin(phase * 1.8))
        gl.setColorAt(0.0, QColor(255, 250, 232, la))
        gl.setColorAt(1.0, QColor(246, 200, 118, 0))
        p.setBrush(gl)
        p.drawEllipse(lens_pt, lr * 1.25, lr * 0.65)

        # 5. Floating golden dust motes & 4-point star sparkles on left & right margins
        for x0, y0, depth, spd, p0, rad in self._motes:
            t = phase * spd + p0
            mx = (x0 * w + math.sin(t * 0.8) * 14.0 * depth) % w
            my = (y0 * h - ((phase * 7.5 * spd * depth) % h)) % h
            tw = 0.4 + 0.6 * math.sin(t * 2.1)
            al = int((56 + 108 * depth) * tw)
            dg = QRadialGradient(QPointF(mx, my), rad * 2.8)
            dg.setColorAt(0.0, QColor(255, 236, 178, al))
            dg.setColorAt(1.0, QColor(238, 188, 96, 0))
            p.setBrush(dg)
            p.drawEllipse(QPointF(mx, my), rad * 2.8, rad * 2.8)

        p.end()


class _LaurelHeading(QWidget):
    """Bold serif heading flanked by two hand-drawn antique gold laurel branches."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sr = QLabel(text, self)
        sr.setVisible(False)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = QFont(TYPOGRAPHY.font_family_display[0])
        font.setPixelSize(20)
        font.setBold(True)
        p.setFont(font)

        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        cx, cy = self.width() * 0.5, self.height() * 0.5

        p.setPen(QColor("#1A2738"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)

        # Symmetric golden laurel sprigs flanking title
        for sign in (-1.0, 1.0):
            bx = cx + sign * (tw * 0.5 + 14.0)
            if bx < 8.0 or bx > self.width() - 8.0:
                continue
            p.save()
            p.translate(bx, cy + 2.0)
            p.scale(sign, 1.0)
            p.setPen(QPen(QColor("#AD8339"), 1.3))
            stem = QPainterPath(QPointF(-2.0, 9.0))
            stem.quadTo(QPointF(7.0, 2.0), QPointF(4.0, -10.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(stem)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#C69B4D"))
            for lx, ly, rot in ((2.0, 4.0, -35), (5.5, -1.0, -45), (5.0, -6.0, -60), (0.0, -2.5, 45), (1.0, -7.5, 30)):
                p.save()
                p.translate(lx, ly)
                p.rotate(rot)
                p.drawEllipse(QPointF(0.0, 0.0), 4.2, 1.9)
                p.restore()
            p.restore()
        p.end()


class _OrnamentDivider(QWidget):
    """Fine antique-brass horizontal divider with a centered diamond flourish."""

    def __init__(self, max_span: float = 260.0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._max_span = max_span
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy = self.width() * 0.5, self.height() * 0.5
        half = min(self.width() * 0.45, self._max_span * 0.5)
        p.setPen(QPen(QColor("#CFAF76"), 1.1))
        p.drawLine(QPointF(cx - half, cy), QPointF(cx - 10.0, cy))
        p.drawLine(QPointF(cx + 10.0, cy), QPointF(cx + half, cy))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#BA8E44"))
        p.drawPolygon(
            QPolygonF(
                [QPointF(cx, cy - 4.0), QPointF(cx + 5.0, cy), QPointF(cx, cy + 4.0), QPointF(cx - 5.0, cy)]
            )
        )
        p.drawEllipse(QPointF(cx - 9.0, cy), 1.6, 1.6)
        p.drawEllipse(QPointF(cx + 9.0, cy), 1.6, 1.6)
        p.end()


class _CompletionSealPill(QFrame):
    """Notched archival pale-sage completion pill: [✓] HOÀN THÀNH 100%."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = "HOÀN THÀNH 100%"
        self.setFixedHeight(36)
        self.setMinimumWidth(210)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(1.5, 1.5, self.width() - 3.0, self.height() - 3.0)
        path = _notched_rect_path(r, 7.0)

        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, QColor("#EBF3E8"))
        grad.setColorAt(1.0, QColor("#DCEBD8"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#92B790"), 1.3))
        p.drawPath(path)

        # Tiny decorative brass dots left & right
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#92B790"))
        p.drawEllipse(QPointF(r.left() + 11.0, r.center().y()), 2.0, 2.0)
        p.drawEllipse(QPointF(r.right() - 11.0, r.center().y()), 2.0, 2.0)

        # Green circle checkmark
        font = QFont(TYPOGRAPHY.font_family_ui[0])
        font.setPixelSize(13)
        font.setBold(True)
        p.setFont(font)
        tw = p.fontMetrics().horizontalAdvance(self._text)
        total_w = 20.0 + 7.0 + tw
        sx = r.center().x() - total_w * 0.5
        cy = r.center().y()

        p.setBrush(QColor("#1F7A52"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(sx + 9.0, cy), 8.5, 8.5)
        p.setPen(QPen(QColor("#FFFFFF"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(sx + 5.2, cy + 0.3), QPointF(sx + 8.0, cy + 3.2))
        p.drawLine(QPointF(sx + 8.0, cy + 3.2), QPointF(sx + 13.0, cy - 2.8))

        p.setPen(QColor("#155C3D"))
        p.drawText(QRectF(sx + 25.0, r.top(), tw + 6.0, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)
        p.end()


class _NotchedStatCard(QFrame):
    """Antique brass-framed notched-corner KPI card with top-center floating vector icon."""

    def __init__(self, caption: str, *, icon_kind: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._icon_kind = icon_kind
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(188, 98)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        col = QVBoxLayout(self)
        col.setContentsMargins(14, 24, 14, 12)
        col.setSpacing(2)

        self.value_label = QLabel("—", self)
        self.value_label.setTextFormat(Qt.TextFormat.PlainText)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet(
            f"color: #162436; font-family: '{TYPOGRAPHY.font_family_display[0]}', Georgia, serif; "
            "font-size: 25px; font-weight: 800; background: transparent;"
        )
        col.addWidget(self.value_label)

        cap_lbl = QLabel(caption, self)
        cap_lbl.setTextFormat(Qt.TextFormat.PlainText)
        cap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap_lbl.setStyleSheet("color: #544636; font-size: 12.5px; font-weight: 500; background: transparent;")
        col.addWidget(cap_lbl)

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(4.0, 12.0, w - 8.0, h - 16.0)
        path = _notched_rect_path(outer, 9.0)

        # Subtle elevation shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(82, 56, 22, 24))
        p.drawPath(_notched_rect_path(outer.translated(0.0, 2.5), 9.0))

        # Soft ivory-parchment card body
        grad = QLinearGradient(outer.topLeft(), outer.bottomLeft())
        grad.setColorAt(0.0, QColor("#FDF9EF"))
        grad.setColorAt(1.0, QColor("#F5EBD6"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#C8AA74"), 1.35))
        p.drawPath(path)

        # Fine inner notched hairline
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(216, 192, 146, 150), 0.9))
        p.drawPath(_notched_rect_path(outer.adjusted(3.5, 3.5, -3.5, -3.5), 7.0))

        # Top-center circular cream mask + crisp antique-gold vector icon
        ic = QPointF(outer.center().x(), outer.top() + 2.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FBF5E8"))
        p.drawEllipse(ic, 16.0, 13.0)
        _draw_vector_glyph(p, self._icon_kind, ic, 22.0, QColor("#9C702A"))
        p.end()


class _MetaIconRow(QWidget):
    """Compact icon + caption + right-aligned bold value row for left-column metadata."""

    def __init__(self, caption: str, *, icon_kind: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._icon_kind = icon_kind
        self.setFixedHeight(26)
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 0, 4, 0)
        row.setSpacing(8)

        cap = QLabel(caption, self)
        cap.setTextFormat(Qt.TextFormat.PlainText)
        cap.setStyleSheet("color: #4D4032; font-size: 13px; background: transparent;")
        row.addWidget(cap, 1)

        self.value_label = QLabel("—", self)
        self.value_label.setTextFormat(Qt.TextFormat.PlainText)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setStyleSheet(
            f"color: #162436; font-family: '{TYPOGRAPHY.font_family_mono[0]}', monospace; "
            "font-size: 13.5px; font-weight: 700; background: transparent;"
        )
        row.addWidget(self.value_label, 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _draw_vector_glyph(p, self._icon_kind, QPointF(10.0, self.height() * 0.5), 16.0, QColor("#8F6930"))
        p.end()


class _ResultsActionButton(StyledButton):
    """Editorial button with crisp vector glyph & golden luminous emphasis for Next Case."""

    def __init__(
        self,
        text: str,
        *,
        variant: str = "paperSecondary",
        icon_kind: Optional[str] = None,
        min_height: int = 44,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, variant=variant, min_height=min_height, parent=parent)
        self._icon_kind = icon_kind
        if variant == "inkPrimary":
            self.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1D314B, stop:1 #111F32);"
                "  color: #FFFDF7;"
                "  border: 2px solid #D9B467;"
                "  border-radius: 8px;"
                "  font-weight: 700;"
                "  font-size: 15px;"
                "  padding: 0 18px;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #264062, stop:1 #172A44);"
                "  border: 2px solid #F0D088;"
                "}"
                "QPushButton:disabled {"
                "  background: #425062;"
                "  color: #B4BECB;"
                "  border: 1.5px solid #8A8170;"
                "}"
            )
        else:
            pad_l = "34px" if icon_kind else "14px"
            self.setStyleSheet(
                "QPushButton {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCF7EB, stop:1 #EFE2C7);"
                "  color: #202632;"
                "  border: 1.4px solid #C6AC7D;"
                "  border-radius: 8px;"
                "  font-weight: 600;"
                "  font-size: 14px;"
                f"  padding: 0 14px 0 {pad_l};"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFDF7, stop:1 #F5E9D0);"
                "  border: 1.4px solid #A88446;"
                "}"
                "QPushButton:pressed {"
                "  background: #E5D4B2;"
                "}"
            )

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.variant == "inkPrimary" and self.isEnabled():
            # Subtle inner gold rim shimmer
            p.setPen(QPen(QColor(246, 218, 152, 130), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(3.5, 3.5, self.width() - 7.0, self.height() - 7.0), 5.5, 5.5)
        elif self._icon_kind:
            col = QColor("#2D3440") if self._icon_kind != "folder" else QColor("#8D662C")
            _draw_vector_glyph(p, self._icon_kind, QPointF(22.0, self.height() * 0.5), 15.0, col)
        p.end()


class _ResultsDossierSheet(QFrame):
    """Wide horizontal 2-column archival parchment dossier with clip, filigree & twine wax seal."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultsArchivalDossier")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(46, 36, 46, 36)
        self.content_layout.setSpacing(18)

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        if w <= 50 or h <= 50:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(26.0, 22.0, w - 52.0, h - 42.0)

        # 1. Background kraft dossier folder & tilted vintage photo slips peeking out left/right
        p.save()
        p.translate(outer.center().x(), outer.center().y())
        p.rotate(-1.2)
        p.setPen(QPen(QColor("#8C6735"), 1.1))
        p.setBrush(QColor("#BA8F54"))
        p.drawRoundedRect(
            QRectF(-outer.width() * 0.508, -outer.height() * 0.518, outer.width() * 1.016, outer.height() * 1.028),
            6.0,
            6.0,
        )
        p.restore()

        # Soft tilted photo card peeking out bottom-left & right
        for cx, cy, rot, pw, ph in (
            (outer.left() + 6.0, outer.center().y() - 10.0, -7.0, 68.0, 140.0),
            (outer.right() - 6.0, outer.center().y() + 26.0, 6.5, 68.0, 130.0),
        ):
            p.save()
            p.translate(cx, cy)
            p.rotate(rot)
            p.setPen(QPen(QColor("#BFA47A"), 1.0))
            p.setBrush(QColor("#ECE0C8"))
            p.drawRoundedRect(QRectF(-pw * 0.5, -ph * 0.5, pw, ph), 3.0, 3.0)
            p.restore()

        # 2. Deep tabletop shadow beneath main parchment sheet
        for expand, dy, alpha in ((8.0, 10.0, 34), (4.0, 6.0, 52), (1.5, 3.0, 68)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(10, 6, 3, alpha))
            p.drawRoundedRect(outer.adjusted(-expand, dy - 2.0, expand, dy + 2.0), 6.0, 6.0)

        # 3. Main cream-parchment dossier body with gentle warm radial shading
        parch = QRadialGradient(outer.center(), max(outer.width(), outer.height()) * 0.65)
        parch.setColorAt(0.0, QColor("#FDF8EC"))
        parch.setColorAt(0.72, QColor("#F7ECD6"))
        parch.setColorAt(1.0, QColor("#EBDBB9"))
        p.setBrush(parch)
        p.setPen(QPen(QColor("#C6A469"), 2.0))
        p.drawRoundedRect(outer, 5.0, 5.0)

        # Inner fine double antique-gold border
        inner = outer.adjusted(7.5, 7.5, -7.5, -7.5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#C9AA72"), 1.2))
        p.drawRoundedRect(inner, 3.0, 3.0)

        # 4. Ornate corner filigree brackets at all 4 corners + faint postmark stamp at top-right
        self._draw_corner_filigree(p, inner)
        self._draw_postmark_watermark(p, QPointF(inner.right() - 42.0, inner.top() + 36.0))

        # 5. Top-left 3D dark-brass binder clip
        self._draw_binder_clip(p, QPointF(outer.left() + 62.0, outer.top()))

        # 6. Bottom-right braided twine & glossy crimson wax seal
        self._draw_twine_wax_seal(p, QPointF(outer.right() - 28.0, outer.bottom() - 88.0), outer.right())
        p.end()

    @staticmethod
    def _draw_corner_filigree(p: QPainter, rect: QRectF) -> None:
        pen = QPen(QColor("#BC9450"), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        corners = (
            (rect.left() + 3.0, rect.top() + 3.0, 1.0, 1.0),
            (rect.right() - 3.0, rect.top() + 3.0, -1.0, 1.0),
            (rect.left() + 3.0, rect.bottom() - 3.0, 1.0, -1.0),
            (rect.right() - 3.0, rect.bottom() - 3.0, -1.0, -1.0),
        )
        for cx, cy, sx, sy in corners:
            p.save()
            p.translate(cx, cy)
            p.scale(sx, sy)
            p.drawLine(QPointF(0.0, 0.0), QPointF(18.0, 0.0))
            p.drawLine(QPointF(0.0, 0.0), QPointF(0.0, 18.0))
            scroll = QPainterPath(QPointF(3.0, 14.0))
            scroll.quadTo(QPointF(4.0, 4.0), QPointF(14.0, 3.0))
            p.drawPath(scroll)
            p.drawEllipse(QPointF(7.5, 7.5), 2.0, 2.0)
            p.restore()

    @staticmethod
    def _draw_postmark_watermark(p: QPainter, center: QPointF) -> None:
        p.save()
        p.setPen(QPen(QColor(168, 136, 86, 42), 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(center, 36.0, 36.0)
        p.drawEllipse(center, 27.0, 27.0)
        p.setPen(QPen(QColor(168, 136, 86, 30), 1.0, Qt.PenStyle.DashLine))
        p.drawEllipse(center, 31.5, 31.5)
        p.restore()

    @staticmethod
    def _draw_binder_clip(p: QPainter, anchor: QPointF) -> None:
        p.save()
        p.translate(anchor)
        wire = QRectF(-8.5, -18.0, 17.0, 17.0)
        p.setPen(QPen(QColor("#5C3F18"), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(wire, 6.5, 6.5)
        p.setPen(QPen(QColor("#E3C27A"), 1.0))
        p.drawRoundedRect(wire.adjusted(0.5, 0.5, -0.5, -0.5), 6.0, 6.0)

        clamp = QRectF(-19.0, -4.0, 38.0, 17.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(16, 10, 4, 52))
        p.drawRoundedRect(clamp.translated(1.5, 3.0), 2.5, 2.5)
        grad = QLinearGradient(clamp.topLeft(), clamp.bottomLeft())
        grad.setColorAt(0.0, QColor("#6E5028"))
        grad.setColorAt(0.45, QColor("#362612"))
        grad.setColorAt(1.0, QColor("#22170B"))
        p.setPen(QPen(QColor("#C8A25B"), 1.1))
        p.setBrush(grad)
        p.drawRoundedRect(clamp, 2.5, 2.5)
        p.restore()

    @staticmethod
    def _draw_twine_wax_seal(p: QPainter, center: QPointF, right_edge: float) -> None:
        p.save()
        # Braided hemp twine loop extending from seal to right folder margin
        twine = QPainterPath(center)
        twine.cubicTo(
            center + QPointF(26.0, 14.0),
            QPointF(right_edge + 24.0, center.y() - 4.0),
            QPointF(right_edge + 12.0, center.y() - 34.0),
        )
        p.setPen(QPen(QColor("#8C6738"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(twine)
        p.setPen(QPen(QColor("#D8B982"), 1.2, Qt.PenStyle.DashLine))
        p.drawPath(twine)

        p.translate(center)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 8, 5, 70))
        p.drawEllipse(QPointF(2.0, 3.5), 27.0, 27.0)

        rim = QPainterPath()
        pts = 24
        for i in range(pts + 1):
            ang = (i / pts) * 2.0 * math.pi
            rad = 25.5 + 1.8 * math.sin(i * 3.0)
            pt = QPointF(math.cos(ang) * rad, math.sin(ang) * rad)
            if i == 0:
                rim.moveTo(pt)
            else:
                rim.lineTo(pt)
        rim.closeSubpath()

        wax = QRadialGradient(QPointF(-6.0, -6.0), 32.0)
        wax.setColorAt(0.0, QColor("#C64236"))
        wax.setColorAt(0.55, QColor("#94231B"))
        wax.setColorAt(1.0, QColor("#63140F"))
        p.setBrush(wax)
        p.setPen(QPen(QColor("#52100C"), 1.2))
        p.drawPath(rim)

        p.setBrush(QColor("#821D16"))
        p.setPen(QPen(QColor("#D59B7E"), 1.1))
        p.drawEllipse(QPointF(0.0, 0.0), 17.5, 17.5)

        # Embossed detective checkmark seal inside wax
        p.setPen(QPen(QColor("#EBB896"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(-6.0, 0.5), QPointF(-1.5, 5.2))
        p.drawLine(QPointF(-1.5, 5.2), QPointF(7.2, -5.0))
        p.restore()


class ResultsScreen(BackdropScreen):
    """Wide 2-column Archival Case-Closed Dossier screen over Living Noir Desk."""

    restart_requested = Signal()
    load_requested = Signal(str)
    next_puzzle_requested = Signal(str)
    level_selection_requested = Signal()
    back_requested = Signal()
    demo_gameplay_requested = Signal()
    demo_levels_requested = Signal()

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            AssetId.A05_GAMEPLAY_BACKGROUND,
            scrim_rgba=(18, 12, 8, 255),
            pixmap_loader=pixmap_loader,
            parent=parent,
        )
        self.setObjectName("ResultsScreen")
        self._results: Optional[ResultsView] = None
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)
        self._celebration_group: Optional[QParallelAnimationGroup] = None
        self._pending_celebration: bool = False

        # Living Noir Moonlit Detective Desk backdrop behind foreground layout
        self._living_bg = _LivingResultsBackdrop(self)
        stack_lay = self.layout()
        if stack_lay is not None:
            stack_lay.addWidget(self._living_bg, 0, 0)
            self._foreground.raise_()

        # 1. Unified Top Editorial Masthead
        top_back_btn = StyledButton("← Trang chủ", variant="ghost", min_height=44, parent=self)
        top_back_btn.clicked.connect(self.back_requested.emit)

        self._mode_badge = StatusLabel("TỔNG KẾT HỒ SƠ · CHƯA CÓ KẾT QUẢ", tone="accent", parent=self)
        header = PageHeader(
            "Biên Bản Khép Án",
            subtitle="Tổng kết hồ sơ điều tra & chỉ số suy luận công khai",
            left_widget=top_back_btn,
            right_widget=self._mode_badge,
            parent=self,
        )
        self.body_layout.addWidget(header)

        # 2. Centered Wide 2-Column Parchment Dossier
        outer = QVBoxLayout()
        outer.setContentsMargins(SPACING.space_5, SPACING.space_3, SPACING.space_5, SPACING.space_3)
        outer.setSpacing(0)
        self.body_layout.addLayout(outer, 1)

        outer.addStretch(1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)

        dossier = _ResultsDossierSheet(self)
        dossier.setMinimumWidth(880)
        dossier.setMaximumWidth(1040)

        # ---- TWO-COLUMN BODY ----
        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(26)

        # ==================== LEFT COLUMN: CREST, VERDICT, SEAL, CASE META ====================
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(8)

        emblem_wrap = QHBoxLayout()
        emblem_wrap.addStretch(1)

        custom_emblem_path = (
            Path(__file__).resolve().parents[3] / "assets" / "results" / "A07_case_closed_emblem_vi.png"
        )
        custom_pm = QPixmap(str(custom_emblem_path)) if custom_emblem_path.is_file() else QPixmap()
        has_custom_vi = not custom_pm.isNull()

        self._emblem_view = AssetImageView(
            AssetId.A07_CASE_CLOSED_EMBLEM,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            overlay_text=None if has_custom_vi else "ĐÃ PHÁ ÁN",
            overlay_rect_ratio=(0.17, 0.49, 0.66, 0.16),
            pixmap_loader=pixmap_loader,
            parent=dossier,
        )
        if has_custom_vi:
            self._emblem_view.set_custom_pixmap(custom_pm)
        self._emblem_view.set_interactive_tilt(True)
        self._emblem_view.setFixedSize(172, 168)
        emblem_wrap.addWidget(self._emblem_view)
        emblem_wrap.addStretch(1)
        left_col.addLayout(emblem_wrap)

        left_col.addWidget(_LaurelHeading("VỤ ÁN ĐÃ KHÉP LẠI", dossier))

        self._notice_label = QLabel("Chưa có dữ liệu tổng kết vụ án.", dossier)
        self._notice_label.setTextFormat(Qt.TextFormat.PlainText)
        self._notice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notice_label.setWordWrap(True)
        self._notice_label.setStyleSheet("color: #544636; font-style: italic; font-size: 13px; background: transparent;")
        self._notice_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        left_col.addWidget(self._notice_label)

        seal_wrap = QHBoxLayout()
        seal_wrap.addStretch(1)
        self._completion_seal = _CompletionSealPill(dossier)
        seal_wrap.addWidget(self._completion_seal)
        seal_wrap.addStretch(1)
        left_col.addLayout(seal_wrap)

        left_col.addWidget(_OrnamentDivider(240.0, dossier))

        puzzle_row = _MetaIconRow("Mã hồ sơ vụ án", icon_kind="folder", parent=dossier)
        grid_row = _MetaIconRow("Kích thước bàn cờ", icon_kind="grid", parent=dossier)
        left_col.addWidget(puzzle_row)
        left_col.addWidget(grid_row)
        left_col.addStretch(1)

        # Vertical hairline divider
        v_rule = QFrame(dossier)
        v_rule.setFixedWidth(1)
        v_rule.setStyleSheet("background-color: #D8C39C; border: none;")

        # ==================== RIGHT COLUMN: 2×2 STAT CARDS + SAT SUMMARY ====================
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 6, 0, 0)
        right_col.setSpacing(12)

        hero_sub = QLabel("Biên Bản Tổng Kết Điều Tra", dossier)
        hero_sub.setTextFormat(Qt.TextFormat.PlainText)
        hero_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_sub.setStyleSheet(
            f"color: #162436; font-family: '{TYPOGRAPHY.font_family_display[0]}', Georgia, serif; "
            "font-size: 21px; font-weight: 800; background: transparent;"
        )
        right_col.addWidget(hero_sub)
        right_col.addWidget(_OrnamentDivider(320.0, dossier))

        kpi_grid = QGridLayout()
        kpi_grid.setContentsMargins(0, 2, 0, 2)
        kpi_grid.setHorizontalSpacing(14)
        kpi_grid.setVerticalSpacing(12)

        revealed_card = _NotchedStatCard("Nghi phạm xác minh", icon_kind="team", parent=dossier)
        elapsed_card = _NotchedStatCard("Thời gian hoàn thành", icon_kind="clock", parent=dossier)
        steps_card = _NotchedStatCard("Bước suy luận hợp lệ", icon_kind="nodes", parent=dossier)
        hints_card = _NotchedStatCard("Lần sử dụng gợi ý", icon_kind="bulb", parent=dossier)

        kpi_grid.addWidget(revealed_card, 0, 0)
        kpi_grid.addWidget(elapsed_card, 0, 1)
        kpi_grid.addWidget(steps_card, 1, 0)
        kpi_grid.addWidget(hints_card, 1, 1)
        right_col.addLayout(kpi_grid)

        right_col.addSpacing(4)
        sat_rule = QFrame(dossier)
        sat_rule.setFixedHeight(1)
        sat_rule.setStyleSheet("background-color: #DAC59E; border: none;")
        right_col.addWidget(sat_rule)

        sat_row = _MetaIconRow("Số lần truy vấn suy diễn", icon_kind="gear", parent=dossier)
        sat_row.value_label.setStyleSheet(
            f"color: #162436; font-family: '{TYPOGRAPHY.font_family_display[0]}', Georgia, serif; "
            "font-size: 17px; font-weight: 800; background: transparent;"
        )
        right_col.addWidget(sat_row)
        right_col.addStretch(1)

        cols.addLayout(left_col, 42)
        cols.addWidget(v_rule)
        cols.addLayout(right_col, 58)
        dossier.content_layout.addLayout(cols)

        # Preserved canonical value_labels mapping (100% API & unit-test compatibility)
        self._value_labels: dict[str, QLabel] = {
            "puzzle_id": puzzle_row.value_label,
            "grid_size": grid_row.value_label,
            "revealed": revealed_card.value_label,
            "accepted_steps": steps_card.value_label,
            "hint_requests": hints_card.value_label,
            "elapsed_ms": elapsed_card.value_label,
            "sat_calls": sat_row.value_label,
        }

        # ---- BOTTOM FULL-WIDTH 4-BUTTON ACTION ROW ----
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(18, 4, 18, 0)
        btn_row.setSpacing(14)

        self._restart_btn = _ResultsActionButton(
            "Chơi lại", variant="paperSecondary", icon_kind="refresh", min_height=44, parent=dossier
        )
        self._restart_btn.setToolTip("Gửi yêu cầu chơi lại vụ án này")
        self._restart_btn.clicked.connect(self._on_restart_clicked)
        btn_row.addWidget(self._restart_btn, 10)

        self._next_btn = _ResultsActionButton(
            "Vụ án tiếp theo →", variant="inkPrimary", icon_kind=None, min_height=46, parent=dossier
        )
        self._next_btn.setEnabled(False)
        self._next_btn.setToolTip("Mở vụ án kế tiếp trong danh mục")
        self._next_btn.clicked.connect(self._on_next_clicked)
        btn_row.addWidget(self._next_btn, 15)

        self._levels_btn = _ResultsActionButton(
            "Kho hồ sơ", variant="paperSecondary", icon_kind="folder", min_height=44, parent=dossier
        )
        self._levels_btn.setToolTip("Quay lại màn hình chọn vụ án")
        self._levels_btn.clicked.connect(self._on_levels_clicked)
        btn_row.addWidget(self._levels_btn, 10)

        self._menu_btn = _ResultsActionButton(
            "Trang chủ", variant="paperGhost", icon_kind="home", min_height=44, parent=dossier
        )
        self._menu_btn.setToolTip("Quay lại màn hình chính")
        self._menu_btn.clicked.connect(self.back_requested.emit)
        btn_row.addWidget(self._menu_btn, 10)

        dossier.content_layout.addLayout(btn_row)

        row.addWidget(dossier, 1)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    # ------------------------------------------------------------------
    # Public API & Properties (100% preserved)
    # ------------------------------------------------------------------

    def set_results(self, raw_results: Any) -> None:
        results = normalize_results_view(raw_results)
        self._results = results

        if results.is_demo_preview:
            self._mode_badge.set_status("XEM TRƯỚC MẪU · DỮ LIỆU MINH HỌA", tone="warning")
            self._notice_label.setText("Chế độ xem trước giao diện với dữ liệu minh họa.")
        else:
            self._mode_badge.set_status("✓ ĐÃ PHÁ ÁN · CHỨNG MINH HOÀN TẤT", tone="success")
            self._notice_label.setText(
                "Tất cả nghi phạm đã được xác minh theo nguyên tắc không đoán mò."
            )

        pct = int(round((results.revealed / results.total) * 100.0)) if results.total > 0 else 100
        self._completion_seal.set_text(f"HOÀN THÀNH {pct}%")

        self._apply_final_metric_labels(results)

        has_next = results.next_puzzle_id is not None
        self._next_btn.setEnabled(has_next)
        if has_next:
            self._next_btn.setToolTip(f"Mở vụ án kế tiếp: {results.next_puzzle_id}")
        else:
            self._next_btn.setToolTip("Không có vụ án tiếp theo trong danh mục")

        self._stop_celebration()
        if not self._reduced_motion:
            self._pending_celebration = True
            if self.isVisible():
                QTimer.singleShot(16, self, self._maybe_start_celebration)

    def clear_results(self) -> None:
        self._stop_celebration()
        self._pending_celebration = False
        self._results = None
        self._mode_badge.set_status("TỔNG KẾT HỒ SƠ · CHƯA CÓ KẾT QUẢ", tone="accent")
        self._notice_label.setText("Chưa có dữ liệu tổng kết vụ án.")
        self._completion_seal.set_text("HOÀN THÀNH 0%")
        for lbl in self._value_labels.values():
            lbl.setText("—")
        self._next_btn.setEnabled(False)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        self._living_bg.set_reduced_motion(self._reduced_motion)
        self._emblem_view.set_reduced_motion(self._reduced_motion)
        if self._reduced_motion:
            self._pending_celebration = False
            self._stop_celebration()
            if self._results is not None:
                self._apply_final_metric_labels(self._results)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._pending_celebration and not self._reduced_motion:
            QTimer.singleShot(16, self, self._maybe_start_celebration)

    def play_celebration(self) -> None:
        """Play Expressive Case-Closed stamp (spring.checkPop), particles, and Counting Number."""
        if self._reduced_motion or self._results is None:
            return
        self._stop_celebration()
        results = self._results

        group = QParallelAnimationGroup(self)

        # 1. Case-Closed 3D Medallion Stamp (spring.checkPop: 0.74 -> 1.0 + 3D pitch -20° -> 0°)
        self._emblem_view.render_scale = SCALE_STAMP_START
        self._emblem_view.tilt_x_deg = -20.0
        stamp = QPropertyAnimation(self._emblem_view, b"render_scale", group)
        stamp.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.results_stamp_duration))
        stamp.setStartValue(SCALE_STAMP_START)
        stamp.setEndValue(1.0)
        stamp.setEasingCurve(build_easing(SPRING_CHECK_POP, tempo=DEFAULT_MOTION.tempo))
        group.addAnimation(stamp)

        tilt_stamp = QPropertyAnimation(self._emblem_view, b"tilt_x_deg", group)
        tilt_stamp.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.results_stamp_duration))
        tilt_stamp.setStartValue(-20.0)
        tilt_stamp.setEndValue(0.0)
        tilt_stamp.setEasingCurve(build_easing(SPRING_CHECK_POP, tempo=DEFAULT_MOTION.tempo))
        group.addAnimation(tilt_stamp)

        # 2. Finite Golden Brass Particles burst around medallion
        self._emblem_view.burst_progress = 0.0
        burst = QPropertyAnimation(self._emblem_view, b"burst_progress", group)
        burst.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.results_particles_duration))
        burst.setStartValue(0.0)
        burst.setEndValue(1.0)
        burst.setEasingCurve(build_easing(EASE_OUT))
        group.addAnimation(burst)

        # 3. Counting Number roll-up on spring.number (zero overshoot, lands on exact final values)
        counter = QVariantAnimation(group)
        counter.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.results_count_duration))
        counter.setStartValue(0.0)
        counter.setEndValue(1.0)
        counter.setEasingCurve(build_easing(SPRING_NUMBER, tempo=DEFAULT_MOTION.tempo))

        def _on_count_tick(value: object, res: ResultsView = results) -> None:
            p = max(0.0, min(1.0, float(value)))
            rev = int(round(res.revealed * p))
            steps = int(round(res.accepted_steps * p))
            hints = int(round(res.hint_requests * p))
            self._value_labels["revealed"].setText(f"{rev} / {res.total}")
            self._value_labels["accepted_steps"].setText(str(steps))
            self._value_labels["hint_requests"].setText(str(hints))
            if res.elapsed_ms is not None:
                self._value_labels["elapsed_ms"].setText(_format_elapsed_ms(res.elapsed_ms * p))
            if res.sat_calls is not None:
                self._value_labels["sat_calls"].setText(str(int(round(res.sat_calls * p))))

        counter.valueChanged.connect(_on_count_tick)
        group.addAnimation(counter)

        def _on_finished(res: ResultsView = results) -> None:
            self._emblem_view.render_scale = 1.0
            self._emblem_view.tilt_x_deg = 0.0
            self._emblem_view.burst_progress = 0.0
            if self._results is res:
                self._apply_final_metric_labels(res)

        group.finished.connect(_on_finished)
        self._celebration_group = group
        group.start()

    def _maybe_start_celebration(self) -> None:
        if self._pending_celebration and self.isVisible() and not self._reduced_motion:
            self._pending_celebration = False
            self.play_celebration()

    def _stop_celebration(self) -> None:
        if self._celebration_group is not None:
            if self._celebration_group.state() != QAbstractAnimation.State.Stopped:
                self._celebration_group.stop()
            self._celebration_group = None
        self._emblem_view.render_scale = 1.0
        self._emblem_view.tilt_x_deg = 0.0
        self._emblem_view.burst_progress = 0.0

    def _apply_final_metric_labels(self, results: ResultsView) -> None:
        self._value_labels["puzzle_id"].setText(results.puzzle_id)
        self._value_labels["grid_size"].setText(
            f"{results.grid_size}×{results.grid_size}" if results.grid_size else "—"
        )
        self._value_labels["revealed"].setText(f"{results.revealed} / {results.total}")
        self._value_labels["accepted_steps"].setText(str(results.accepted_steps))
        self._value_labels["hint_requests"].setText(str(results.hint_requests))
        self._value_labels["elapsed_ms"].setText(_format_elapsed_ms(results.elapsed_ms))
        self._value_labels["sat_calls"].setText(
            str(results.sat_calls) if results.sat_calls is not None else "—"
        )

    @property
    def results(self) -> Optional[ResultsView]:
        return self._results

    @property
    def emblem_view(self) -> AssetImageView:
        return self._emblem_view

    @property
    def restart_button(self) -> StyledButton:
        return self._restart_btn

    @property
    def next_puzzle_button(self) -> StyledButton:
        return self._next_btn

    @property
    def levels_button(self) -> StyledButton:
        return self._levels_btn

    @property
    def menu_button(self) -> StyledButton:
        return self._menu_btn

    @property
    def value_labels(self) -> dict[str, QLabel]:
        return dict(self._value_labels)

    @property
    def notice_label(self) -> QLabel:
        return self._notice_label

    def _on_restart_clicked(self) -> None:
        self.restart_requested.emit()
        self.demo_gameplay_requested.emit()

    def _on_next_clicked(self) -> None:
        if self._results is not None and self._results.next_puzzle_id is not None:
            self.load_requested.emit(self._results.next_puzzle_id)
            self.next_puzzle_requested.emit(self._results.next_puzzle_id)

    def _on_levels_clicked(self) -> None:
        self.level_selection_requested.emit()
        self.demo_levels_requested.emit()
