"""AboutScreen — Archival Notched Parchment Dossier over Living Detective Desk.

Presents GRIDUCTIVE SOLVER on a sunlit antique sepia office backdrop (courthouse
etching, city skyline, walnut desk with vintage books, brass magnifying glass,
and crimson wax-sealed envelope) with a centered 2-layer notched-corner archival
parchment dossier sheet, tilted sepia Polaroid clipped with a brass binder clip,
swallowtail ribbon section headers with vector icons, compact 5-member roster,
and GitHub / Video links.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QKeyEvent,
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
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.page_header import PageHeader
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.project_info import (
    COURSE_LABEL,
    GITHUB_REPO_URL,
    PROJECT_INTRO_PARAGRAPHS,
    PROJECT_SUBTITLE,
    PROJECT_TITLE,
    TEAM_MEMBERS,
    YOUTUBE_DEMO_URL,
    TeamMemberInfo,
    is_valid_external_url,
)
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.styles.tokens import SPACING, TYPOGRAPHY


def _default_open_url(url: str) -> bool:
    return bool(QDesktopServices.openUrl(QUrl(url)))


def _make_github_icon(color: QColor, size: int = 18) -> QIcon:
    """Render a crisp 2x HiDPI vector GitHub mark icon."""
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2.0)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cx, cy, r = size * 0.5, size * 0.5, size * 0.44
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(cx, cy), r, r)

    # Cutout classic cat-head & shoulders silhouette in dark ink
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    head = QPainterPath()
    head.addEllipse(QPointF(cx, cy - r * 0.05), r * 0.54, r * 0.44)
    ear_l = QPolygonF(
        [
            QPointF(cx - r * 0.44, cy - r * 0.22),
            QPointF(cx - r * 0.36, cy - r * 0.64),
            QPointF(cx - r * 0.12, cy - r * 0.42),
        ]
    )
    ear_r = QPolygonF(
        [
            QPointF(cx + r * 0.44, cy - r * 0.22),
            QPointF(cx + r * 0.36, cy - r * 0.64),
            QPointF(cx + r * 0.12, cy - r * 0.42),
        ]
    )
    head.addPolygon(ear_l)
    head.addPolygon(ear_r)
    head.addRoundedRect(QRectF(cx - r * 0.24, cy + r * 0.28, r * 0.48, r * 0.72), 2.0, 2.0)
    p.fillPath(head, Qt.GlobalColor.transparent)
    p.end()
    return QIcon(pm)


def _make_play_icon(color: QColor, size: int = 16) -> QIcon:
    """Render a crisp 2x HiDPI vector Play triangle icon."""
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2.0)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    tri = QPolygonF(
        [
            QPointF(size * 0.26, size * 0.16),
            QPointF(size * 0.84, size * 0.50),
            QPointF(size * 0.26, size * 0.84),
        ]
    )
    p.drawPolygon(tri)
    p.end()
    return QIcon(pm)


class _LivingAboutCanvas(QWidget):
    """Sunlit vintage detective desk backdrop with subtle breathing dust & lens glint."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._bg_path = (
            Path(__file__).resolve().parents[3] / "assets" / "backgrounds" / "A08_about_desk_backdrop.png"
        )
        self._raw_bg = QPixmap(str(self._bg_path)) if self._bg_path.is_file() else QPixmap()
        self._scaled_bg: Optional[QPixmap] = None
        self._cached_size = QSize(0, 0)
        self._phase: float = 0.0
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)

        self._motes: tuple[tuple[float, float, float, float, float, float], ...] = tuple(
            (
                ((i * 41 + 9) % 100) / 100.0,
                ((i * 57 + 17) % 85) / 100.0,
                0.35 + 0.65 * ((i % 4) / 3.0),
                0.45 + 0.55 * ((i % 3) / 2.0),
                (i * 1.37) % (2.0 * math.pi),
                1.4 + 2.0 * ((i % 3) / 2.0),
            )
            for i in range(18)
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
        w, h = self.width(), self.height()
        if w <= 2 or h <= 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if not self._raw_bg.isNull():
            sz = QSize(w, h)
            if self._scaled_bg is None or self._cached_size != sz:
                self._scaled_bg = self._raw_bg.scaled(
                    sz,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._cached_size = sz
            ox = (w - self._scaled_bg.width()) // 2
            oy = h - self._scaled_bg.height()
            p.drawPixmap(ox, oy, self._scaled_bg)
        else:
            p.fillRect(self.rect(), QColor("#EFE3CB"))

        phase = 0.0 if self._reduced_motion else self._phase
        p.setPen(Qt.PenStyle.NoPen)

        # 1. Soft breathing golden afternoon sunbeam across upper sepia sky
        sun_pulse = 0.80 + 0.20 * math.sin(phase * 0.9)
        sun = QRadialGradient(QPointF(w * 0.84, h * 0.24), max(w, h) * 0.42)
        sun.setColorAt(0.0, QColor(255, 240, 196, int(52 * sun_pulse)))
        sun.setColorAt(0.55, QColor(242, 206, 140, int(20 * sun_pulse)))
        sun.setColorAt(1.0, QColor(242, 206, 140, 0))
        p.setBrush(sun)
        p.drawRect(self.rect())

        # 2. Optical specular glint gliding across the bottom-left magnifying glass
        lens_pt = QPointF(w * 0.182, h * 0.912)
        lens_r = min(w, h) * 0.068
        shift = math.sin(phase * 1.25) * lens_r * 0.45
        lens_g = QRadialGradient(lens_pt + QPointF(shift, -shift * 0.35), lens_r)
        la = int(64 + 34 * math.sin(phase * 1.75))
        lens_g.setColorAt(0.0, QColor(255, 250, 232, la))
        lens_g.setColorAt(0.5, QColor(238, 200, 128, int(la * 0.38)))
        lens_g.setColorAt(1.0, QColor(238, 200, 128, 0))
        p.setBrush(lens_g)
        p.drawEllipse(lens_pt, lens_r, lens_r * 0.72)

        # 3. Subtle crimson warmth shimmer on the bottom-right wax seal
        wax_pt = QPointF(w * 0.896, h * 0.875)
        wax_r = min(w, h) * 0.055
        wa = int(28 + 18 * math.sin(phase * 1.3 + 1.0))
        wax_g = QRadialGradient(wax_pt, wax_r)
        wax_g.setColorAt(0.0, QColor(255, 220, 185, wa))
        wax_g.setColorAt(1.0, QColor(180, 50, 40, 0))
        p.setBrush(wax_g)
        p.drawEllipse(wax_pt, wax_r, wax_r)

        # 4. 18 delicate floating golden dust motes in the sunlight margins
        for x0, y0, depth, spd, p0, rad in self._motes:
            t = phase * spd + p0
            mx = (x0 * w + math.sin(t * 0.8) * 14.0 * depth) % max(1.0, float(w))
            my = (y0 * h - ((phase * 6.5 * spd * depth) % max(1.0, float(h)))) % max(1.0, float(h))
            tw = 0.42 + 0.58 * math.sin(t * 1.9)
            al = int((36 + 58 * depth) * tw)
            mg = QRadialGradient(QPointF(mx, my), rad * 2.8)
            mg.setColorAt(0.0, QColor(255, 236, 178, al))
            mg.setColorAt(1.0, QColor(232, 186, 102, 0))
            p.setBrush(mg)
            p.drawEllipse(QPointF(mx, my), rad * 2.8, rad * 2.8)

        p.end()


class _NotchedDossierSheet(QFrame):
    """2-layer antique parchment certificate sheet with 4 vintage concave notched corners."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ArchivalNotchedDossier")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(34, 24, 34, 28)
        self.content_layout.setSpacing(14)

    @staticmethod
    def _notched_path(rect: QRectF, notch: float) -> QPainterPath:
        """Build a vintage certificate rectangle with concave quarter-circle corners."""
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
        if w <= 24 or h <= 24:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(8.0, 4.0, w - 16.0, h - 14.0)

        # 1. Soft multi-layer elevation drop shadow onto the wooden desk
        for expand, dy, alpha in ((5.0, 7.0, 22), (2.5, 4.0, 38), (1.0, 2.0, 52)):
            sh_path = self._notched_path(outer.adjusted(-expand, dy - expand * 0.4, expand, dy + expand * 0.4), 14.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(36, 22, 10, alpha))
            p.drawPath(sh_path)

        # 2. Subtle underneath stacked parchment sheet peeking out along the bottom edge
        under_rect = outer.adjusted(4.0, 5.0, -4.0, 5.0)
        under_path = self._notched_path(under_rect, 13.0)
        p.setBrush(QColor("#F0E4CC"))
        p.setPen(QPen(QColor("#C6AD82"), 1.0))
        p.drawPath(under_path)

        # 3. Main top vintage ivory-parchment dossier sheet with concave notched corners
        main_path = self._notched_path(outer, 14.0)
        bg_grad = QLinearGradient(outer.topLeft(), outer.bottomLeft())
        bg_grad.setColorAt(0.0, QColor("#FDF9EF"))
        bg_grad.setColorAt(0.55, QColor("#FBF5E8"))
        bg_grad.setColorAt(1.0, QColor("#F6ECD7"))
        p.setBrush(bg_grad)
        p.setPen(QPen(QColor("#C8AE82"), 1.35))
        p.drawPath(main_path)

        # 4. Signature deep burgundy archival top accent bar clipped cleanly inside the notched contour
        p.save()
        p.setClipPath(main_path)
        bar_grad = QLinearGradient(outer.left(), outer.top(), outer.right(), outer.top())
        bar_grad.setColorAt(0.0, QColor("#7B1F1F"))
        bar_grad.setColorAt(0.5, QColor("#962B2B"))
        bar_grad.setColorAt(1.0, QColor("#7B1F1F"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bar_grad)
        p.drawRect(QRectF(outer.left(), outer.top(), outer.width(), 4.5))

        # Delicate warm gold inset border frame
        inner_path = self._notched_path(outer.adjusted(5.5, 6.5, -5.5, -5.5), 11.5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(198, 170, 120, 115), 1.0))
        p.drawPath(inner_path)

        # Subtle vintage warm bottom sheen
        foot_grad = QLinearGradient(outer.left(), outer.bottom() - 28.0, outer.left(), outer.bottom())
        foot_grad.setColorAt(0.0, QColor(218, 194, 152, 0))
        foot_grad.setColorAt(1.0, QColor(202, 174, 126, 38))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(foot_grad)
        p.drawRect(QRectF(outer.left(), outer.bottom() - 28.0, outer.width(), 28.0))
        p.restore()
        p.end()


class _ClippedPolaroidPhoto(QWidget):
    """Tilted archival sepia Polaroid photo fastened with a 3D brass binder clip.

    Hosts the required 82x82 ``AssetImageView`` child so existing test contracts
    remain 100% intact while rendering an authentic tilted Polaroid presentation.
    """

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(118, 116)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        photo_path = (
            Path(__file__).resolve().parents[3] / "assets" / "backgrounds" / "A08_about_photo_sepia.png"
        )
        self._sepia_pm = QPixmap(str(photo_path)) if photo_path.is_file() else QPixmap()

        self.emblem_view = AssetImageView(
            AssetId.A04_APP_EMBLEM,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=self,
        )
        if not self._sepia_pm.isNull():
            self.emblem_view.set_custom_pixmap(self._sepia_pm)
        self.emblem_view.setFixedSize(82, 82)
        self.emblem_view.move(18, 18)
        self.emblem_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        op = QGraphicsOpacityEffect(self.emblem_view)
        op.setOpacity(0.0)
        self.emblem_view.setGraphicsEffect(op)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        cx, cy = self.width() * 0.5, self.height() * 0.54

        # 1. Back stacked cream archival slip tilted slightly opposite (+4 deg)
        p.save()
        p.translate(cx + 3.0, cy + 2.0)
        p.rotate(4.0)
        back_rect = QRectF(-41.0, -42.0, 82.0, 84.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(46, 30, 14, 34))
        p.drawRoundedRect(back_rect.translated(2.0, 3.5), 2.5, 2.5)
        p.setBrush(QColor("#F3E7CE"))
        p.setPen(QPen(QColor("#CBB289"), 1.0))
        p.drawRoundedRect(back_rect, 2.5, 2.5)
        p.restore()

        # 2. Front tilted Polaroid photo (-6.5 deg) with sepia courthouse print
        p.save()
        p.translate(cx - 2.0, cy)
        p.rotate(-6.5)
        frame = QRectF(-42.0, -44.0, 84.0, 88.0)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(34, 20, 8, 52))
        p.drawRoundedRect(frame.translated(2.5, 4.0), 2.5, 2.5)

        p.setBrush(QColor("#FAF4E6"))
        p.setPen(QPen(QColor("#C6AC82"), 1.1))
        p.drawRoundedRect(frame, 2.5, 2.5)

        photo_rect = QRectF(frame.left() + 6.0, frame.top() + 6.0, frame.width() - 12.0, frame.height() - 19.0)
        if not self._sepia_pm.isNull():
            p.drawPixmap(photo_rect.toRect(), self._sepia_pm)
        else:
            p.fillRect(photo_rect, QColor("#C4A87E"))
        p.setPen(QPen(QColor(92, 66, 38, 120), 0.9))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(photo_rect)

        # 3. 3D Metallic Antique Brass Binder Clip clamping top-center of Polaroid
        clip_wire = QRectF(-6.0, frame.top() - 12.0, 12.0, 13.0)
        p.setPen(QPen(QColor("#7A5828"), 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(clip_wire, 5.0, 5.0)
        p.setPen(QPen(QColor("#E3C27E"), 0.9))
        p.drawRoundedRect(clip_wire.adjusted(0.4, 0.4, -0.4, -0.4), 4.5, 4.5)

        clamp = QRectF(-13.5, frame.top() - 4.0, 27.0, 10.5)
        brass = QLinearGradient(clamp.topLeft(), clamp.bottomLeft())
        brass.setColorAt(0.0, QColor("#DFB96E"))
        brass.setColorAt(0.45, QColor("#B4843A"))
        brass.setColorAt(1.0, QColor("#7C5622"))
        p.setPen(QPen(QColor("#5B3D16"), 1.0))
        p.setBrush(brass)
        p.drawRoundedRect(clamp, 2.2, 2.2)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 244, 214, 150))
        p.drawRect(QRectF(clamp.left() + 3.0, clamp.top() + 2.0, clamp.width() - 6.0, 1.8))
        p.restore()
        p.end()


class _RibbonSectionHeader(QWidget):
    """Vintage champagne-gold swallowtail ribbon section header with hand-drawn vector icon."""

    def __init__(
        self,
        title: str,
        *,
        icon_kind: str = "book",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._icon_kind = icon_kind
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._sr_label = QLabel(title, self)
        self._sr_label.setTextFormat(Qt.TextFormat.PlainText)
        self._sr_label.setVisible(False)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = QFont(TYPOGRAPHY.font_family_display[0])
        font.setPixelSize(13)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        p.setFont(font)

        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(self._title)
        icon_w = 24.0
        pad_l = 12.0
        pad_r = 24.0
        tail_w = 13.0
        ribbon_w = min(float(self.width()) - 2.0, max(190.0, pad_l + icon_w + 10.0 + text_w + pad_r))
        rh = 28.0
        top = (self.height() - rh) * 0.5

        poly = QPolygonF(
            [
                QPointF(1.0, top),
                QPointF(ribbon_w, top),
                QPointF(ribbon_w - tail_w, top + rh * 0.5),
                QPointF(ribbon_w, top + rh),
                QPointF(1.0, top + rh),
            ]
        )

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(82, 58, 28, 28))
        p.drawPolygon(poly.translated(1.0, 2.0))

        grad = QLinearGradient(0.0, top, ribbon_w, top)
        grad.setColorAt(0.0, QColor("#F0E1BE"))
        grad.setColorAt(0.75, QColor("#EAD8B0"))
        grad.setColorAt(1.0, QColor("#E2CD9F"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#D3B986"), 1.0))
        p.drawPolygon(poly)

        icon_rect = QRectF(pad_l, top + (rh - 18.0) * 0.5, 20.0, 18.0)
        self._draw_vector_icon(p, icon_rect)

        text_rect = QRectF(icon_rect.right() + 9.0, top, ribbon_w - icon_rect.right() - 18.0, rh)
        p.setPen(QColor("#241E17"))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._title)
        p.end()

    def _draw_vector_icon(self, p: QPainter, rect: QRectF) -> None:
        ink = QColor("#3A2B18")
        if self._icon_kind == "book":
            p.setPen(QPen(ink, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(QColor("#FBF5E7"))
            cx = rect.center().x()
            left_pg = QPainterPath(QPointF(cx, rect.top() + 3.0))
            left_pg.quadTo(QPointF(cx - 4.5, rect.top() + 1.0), QPointF(rect.left() + 1.0, rect.top() + 2.5))
            left_pg.lineTo(rect.left() + 1.0, rect.bottom() - 2.0)
            left_pg.quadTo(QPointF(cx - 4.5, rect.bottom() - 3.5), QPointF(cx, rect.bottom() - 1.0))
            left_pg.closeSubpath()
            right_pg = QPainterPath(QPointF(cx, rect.top() + 3.0))
            right_pg.quadTo(QPointF(cx + 4.5, rect.top() + 1.0), QPointF(rect.right() - 1.0, rect.top() + 2.5))
            right_pg.lineTo(rect.right() - 1.0, rect.bottom() - 2.0)
            right_pg.quadTo(QPointF(cx + 4.5, rect.bottom() - 3.5), QPointF(cx, rect.bottom() - 1.0))
            right_pg.closeSubpath()
            p.drawPath(left_pg)
            p.drawPath(right_pg)
        elif self._icon_kind == "team":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ink)
            cx, cy = rect.center().x(), rect.center().y()
            for ox in (-5.8, 5.8):
                p.drawEllipse(QPointF(cx + ox, cy - 3.5), 2.5, 2.5)
                body = QPainterPath()
                body.addRoundedRect(QRectF(cx + ox - 3.6, cy + 0.2, 7.2, 5.8), 3.0, 3.0)
                p.drawPath(body)
            p.setBrush(QColor("#231A10"))
            p.drawEllipse(QPointF(cx, cy - 4.6), 3.1, 3.1)
            mid_body = QPainterPath()
            mid_body.addRoundedRect(QRectF(cx - 4.6, cy - 0.5, 9.2, 7.4), 3.5, 3.5)
            p.drawPath(mid_body)
        else:
            p.save()
            p.translate(rect.center())
            p.rotate(-42.0)
            p.setPen(QPen(ink, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(-8.0, -3.2, 9.0, 6.4), 3.2, 3.2)
            p.drawRoundedRect(QRectF(-1.0, -3.2, 9.0, 6.4), 3.2, 3.2)
            p.restore()


class _TeamMemberRow(QFrame):
    """Compact single-line archival roster row: [01]  Full Name  [24122015]."""

    def __init__(
        self,
        index: int,
        member: TeamMemberInfo,
        *,
        is_last: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("widgetKind", "teamMemberRow")
        self.setProperty("isLast", "true" if is_last else "false")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(40)
        self.setToolTip(f"{member.full_name}\nVai trò: {member.stage2_role}\nMSSV: {member.student_id}")

        row = QHBoxLayout(self)
        row.setContentsMargins(2, 5, 2, 5)
        row.setSpacing(12)

        num_lbl = QLabel(f"{index:02d}", self)
        num_lbl.setTextFormat(Qt.TextFormat.PlainText)
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setFixedSize(30, 24)
        num_lbl.setStyleSheet(
            "background-color: #EFE1BF; color: #3D2E1A; "
            "border: 1px solid #D8BF8E; border-radius: 12px; "
            "font-weight: 700; font-size: 12px;"
        )
        row.addWidget(num_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        name_lbl = QLabel(member.full_name, self)
        name_lbl.setTextFormat(Qt.TextFormat.PlainText)
        name_lbl.setStyleSheet("color: #1F2633; font-weight: 700; font-size: 14px; background: transparent;")
        row.addWidget(name_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        mssv_lbl = QLabel(member.student_id, self)
        mssv_lbl.setTextFormat(Qt.TextFormat.PlainText)
        mssv_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mssv_lbl.setFixedSize(88, 26)
        mssv_lbl.setStyleSheet(
            "background-color: #E7D5AE; color: #4A381D; "
            "border: 1px solid #CFAF74; border-radius: 5px; "
            "font-family: monospace; font-weight: 700; font-size: 12px;"
        )
        row.addWidget(mssv_lbl, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class AboutScreen(QWidget):
    """Vintage Archival Case-Dossier About Screen on Living Detective Desk backdrop."""

    back_requested = Signal()
    external_link_opened = Signal(str)

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        github_url: str = GITHUB_REPO_URL,
        youtube_url: Optional[str] = YOUTUBE_DEMO_URL,
        url_opener: Optional[Callable[[str], bool]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AboutScreen")
        self.setProperty("surface", "paperCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._github_url = github_url
        self._youtube_url = youtube_url
        self._url_opener = url_opener or _default_open_url

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ------------------------------------------------------------------
        # 1. TOP EDITORIAL MASTHEAD
        # ------------------------------------------------------------------
        self._back_button = StyledButton("← Quay lại", variant="ghost", min_height=44, parent=self)
        self._back_button.setToolTip("Trở về Màn hình chính (Esc)")
        self._back_button.clicked.connect(self.back_requested.emit)

        header = PageHeader(
            "GIỚI THIỆU GRIDUCTIVE SOLVER",
            subtitle="Hồ Sơ Phá Án",
            left_widget=self._back_button,
            right_widget=StatusLabel(COURSE_LABEL, tone="accent", parent=self),
            parent=self,
        )
        root.addWidget(header)

        # ------------------------------------------------------------------
        # 2. LIVING SUNLIT DETECTIVE DESK CANVAS + CENTERED NOTCHED DOSSIER
        # ------------------------------------------------------------------
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._canvas = _LivingAboutCanvas(self._scroll_area)
        canvas_v = QVBoxLayout(self._canvas)
        canvas_v.setContentsMargins(SPACING.space_5, 18, SPACING.space_5, 28)
        canvas_v.setSpacing(0)
        canvas_v.addStretch(1)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch(1)

        dossier = _NotchedDossierSheet(self._canvas)
        dossier.setMinimumWidth(780)
        dossier.setMaximumWidth(960)

        # ==================== DOSSIER HEADER ====================
        brand_header = QWidget(dossier)
        brand_header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        brand_row = QHBoxLayout(brand_header)
        brand_row.setContentsMargins(0, 2, 0, 2)
        brand_row.setSpacing(16)

        self._polaroid = _ClippedPolaroidPhoto(pixmap_loader=pixmap_loader, parent=brand_header)
        self._emblem_view = self._polaroid.emblem_view
        brand_row.addWidget(self._polaroid, 0, Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 4, 0, 4)
        title_col.setSpacing(4)

        kicker_row = QHBoxLayout()
        kicker_row.setContentsMargins(0, 0, 0, 0)
        kicker_row.setSpacing(8)
        kicker_top = QLabel("HỒ SƠ ĐỒ ÁN TRINH THÁM", brand_header)
        kicker_top.setStyleSheet(
            "color: #9A4136; font-weight: 700; font-size: 11px; letter-spacing: 1px; background: transparent;"
        )
        kicker_row.addWidget(kicker_top, 0, Qt.AlignmentFlag.AlignVCenter)
        kicker_line = QFrame(brand_header)
        kicker_line.setFixedHeight(1)
        kicker_line.setStyleSheet("background-color: #D9C39A; border: none;")
        kicker_row.addWidget(kicker_line, 1, Qt.AlignmentFlag.AlignVCenter)
        title_col.addLayout(kicker_row)

        self._project_title_label = QLabel(PROJECT_TITLE, brand_header)
        self._project_title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._project_title_label.setProperty("role", "paperTitle")
        self._project_title_label.setStyleSheet(
            f"color: #162336; font-family: '{TYPOGRAPHY.font_family_display[0]}', Georgia, serif; "
            "font-size: 30px; font-weight: 800; letter-spacing: 0.6px; background: transparent;"
        )
        title_col.addWidget(self._project_title_label)

        self._project_subtitle_label = QLabel(PROJECT_SUBTITLE, brand_header)
        self._project_subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        self._project_subtitle_label.setStyleSheet(
            "color: #544636; font-style: italic; font-size: 13.5px; background: transparent;"
        )
        title_col.addWidget(self._project_subtitle_label)

        brand_row.addLayout(title_col, 1)

        self._logo_view = AssetImageView(
            AssetId.A04_LOGO_WIDE,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=brand_header,
        )
        self._logo_view.setMinimumSize(218, 86)
        self._logo_view.setMaximumSize(252, 96)
        self._logo_view.set_interactive_tilt(True)
        brand_row.addWidget(self._logo_view, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        dossier.content_layout.addWidget(brand_header)

        header_rule = QFrame(dossier)
        header_rule.setFixedHeight(1)
        header_rule.setStyleSheet("background-color: #DFCCA8; border: none;")
        dossier.content_layout.addWidget(header_rule)

        # ==================== 2-COLUMN EDITORIAL SPREAD ====================
        spread = QHBoxLayout()
        spread.setContentsMargins(0, 4, 0, 2)
        spread.setSpacing(24)

        # ---- LEFT COLUMN: TỔNG QUAN ĐỒ ÁN ----
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(12)

        left_col.addWidget(_RibbonSectionHeader("TỔNG QUAN ĐỒ ÁN", icon_kind="book", parent=dossier))

        lead_frame = QFrame(dossier)
        lead_frame.setObjectName("AboutLeadQuote")
        lead_frame.setStyleSheet(
            "QFrame#AboutLeadQuote { background-color: #F4EAD3; border: none; "
            "border-left: 4px solid #8A2424; border-radius: 3px; }"
        )
        lead_lay = QVBoxLayout(lead_frame)
        lead_lay.setContentsMargins(14, 11, 14, 11)
        lead_lbl = QLabel(PROJECT_INTRO_PARAGRAPHS[0], lead_frame)
        lead_lbl.setTextFormat(Qt.TextFormat.PlainText)
        lead_lbl.setWordWrap(True)
        lead_lbl.setStyleSheet(
            "color: #201A14; font-weight: 700; font-size: 13.5px; line-height: 1.45; background: transparent; border: none;"
        )
        lead_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lead_lay.addWidget(lead_lbl)
        left_col.addWidget(lead_frame)

        self._intro_labels: list[QLabel] = [lead_lbl]
        for para in PROJECT_INTRO_PARAGRAPHS[1:]:
            lbl = QLabel(para, dossier)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #342B20; font-size: 13px; background: transparent;")
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            left_col.addWidget(lbl)
            self._intro_labels.append(lbl)

        left_col.addStretch(1)

        v_rule = QFrame(dossier)
        v_rule.setFixedWidth(1)
        v_rule.setStyleSheet("background-color: #E2D1B2; border: none;")

        # ---- RIGHT COLUMN: NHÓM THỰC HIỆN & LIÊN KẾT DỰ ÁN ----
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(8)

        right_col.addWidget(_RibbonSectionHeader("NHÓM THỰC HIỆN · CSC14003", icon_kind="team", parent=dossier))

        self._member_cards: list[_TeamMemberRow] = []
        total_members = len(TEAM_MEMBERS)
        for idx, member in enumerate(TEAM_MEMBERS, start=1):
            row_card = _TeamMemberRow(
                idx,
                member,
                is_last=(idx == total_members),
                parent=dossier,
            )
            right_col.addWidget(row_card)
            self._member_cards.append(row_card)

        right_col.addSpacing(10)
        right_col.addWidget(_RibbonSectionHeader("LIÊN KẾT DỰ ÁN", icon_kind="link", parent=dossier))
        right_col.addSpacing(2)

        links_row = QHBoxLayout()
        links_row.setContentsMargins(0, 0, 0, 0)
        links_row.setSpacing(10)

        self._github_button = StyledButton(
            "Mã nguồn GitHub",
            variant="inkPrimary",
            min_height=42,
            parent=dossier,
        )
        self._github_button.setIcon(_make_github_icon(QColor("#FBF6EC"), 17))
        self._github_button.setIconSize(QSize(17, 17))
        self._github_button.setProperty("compactLinks", "true")
        self._github_button.clicked.connect(self._on_github_clicked)
        links_row.addWidget(self._github_button, 4)

        self._youtube_button = StyledButton(
            "Video minh họa",
            variant="paperSecondary",
            min_height=42,
            parent=dossier,
        )
        self._youtube_button.setIcon(_make_play_icon(QColor("#5C4D3B"), 14))
        self._youtube_button.setIconSize(QSize(14, 14))
        self._youtube_button.setProperty("compactLinks", "true")
        self._youtube_button.clicked.connect(self._on_youtube_clicked)
        links_row.addWidget(self._youtube_button, 6)
        right_col.addLayout(links_row)

        self._github_caption = QLabel(f"GitHub: {self._github_url}", dossier)
        self._github_caption.setTextFormat(Qt.TextFormat.PlainText)
        self._github_caption.setStyleSheet("color: #6B5B46; font-size: 11.5px; background: transparent;")
        self._github_caption.setWordWrap(True)
        right_col.addWidget(self._github_caption)

        right_col.addStretch(1)

        spread.addLayout(left_col, 49)
        spread.addWidget(v_rule)
        spread.addLayout(right_col, 51)
        dossier.content_layout.addLayout(spread, 1)

        center_row.addWidget(dossier, 1)
        center_row.addStretch(1)
        canvas_v.addLayout(center_row)
        canvas_v.addStretch(1)

        self._scroll_area.setWidget(self._canvas)
        root.addWidget(self._scroll_area, 1)

        self._sync_link_buttons()

    # ------------------------------------------------------------------
    # Public API & Properties (100% preserved)
    # ------------------------------------------------------------------

    @property
    def back_button(self) -> StyledButton:
        return self._back_button

    @property
    def github_button(self) -> StyledButton:
        return self._github_button

    @property
    def youtube_button(self) -> StyledButton:
        return self._youtube_button

    @property
    def github_url(self) -> str:
        return self._github_url

    @property
    def youtube_url(self) -> Optional[str]:
        return self._youtube_url

    @property
    def emblem_view(self) -> AssetImageView:
        return self._emblem_view

    @property
    def logo_view(self) -> AssetImageView:
        return self._logo_view

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    @property
    def member_cards(self) -> tuple[_TeamMemberRow, ...]:
        return tuple(self._member_cards)

    def set_youtube_url(self, url: Optional[str]) -> None:
        self._youtube_url = url
        self._sync_link_buttons()

    def set_reduced_motion(self, enabled: bool) -> None:
        self._canvas.set_reduced_motion(bool(enabled))
        self._logo_view.set_reduced_motion(bool(enabled))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.back_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Internal Handlers
    # ------------------------------------------------------------------

    def _sync_link_buttons(self) -> None:
        gh_valid = is_valid_external_url(self._github_url)
        self._github_button.setEnabled(gh_valid)
        self._github_button.setToolTip(
            f"Mở kho mã nguồn trên trình duyệt mặc định:\n{self._github_url}"
            if gh_valid
            else "Liên kết GitHub chưa hợp lệ"
        )

        yt_valid = is_valid_external_url(self._youtube_url)
        if yt_valid:
            self._youtube_button.setText("Video minh họa")
            self._youtube_button.setEnabled(True)
            self._youtube_button.setIcon(_make_play_icon(QColor("#241E17"), 14))
            self._youtube_button.setToolTip(
                f"Mở video minh họa trên trình duyệt mặc định:\n{self._youtube_url}"
            )
        else:
            self._youtube_button.setText("Video minh họa — Chưa cập nhật")
            self._youtube_button.setEnabled(False)
            self._youtube_button.setIcon(_make_play_icon(QColor("#7D6E5C"), 14))
            self._youtube_button.setToolTip(
                "Video minh họa chưa được cập nhật (chỉnh tại src/gui/project_info.py)."
            )

    def _on_github_clicked(self) -> None:
        if is_valid_external_url(self._github_url):
            self._url_opener(self._github_url)
            self.external_link_opened.emit(self._github_url)

    def _on_youtube_clicked(self) -> None:
        if is_valid_external_url(self._youtube_url):
            assert self._youtube_url is not None
            self._url_opener(self._youtube_url)
            self.external_link_opened.emit(self._youtube_url)
