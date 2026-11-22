"""AmbientStardustOverlay — Global click-through Shooting Stars, Golden Stardust & Cursor Mist.

Renders three harmonious atmospheric layers across the entire MainWindow without
modifying any existing screen or card animations:
  1. Shooting stars with luminous tapered tails, 4-point star heads, and sparks.
  2. Drifting golden sand / stardust motes with smart edge-weighted luminance.
  3. Silky circular warm mist / cloud aura ("sương mây vòng tròn") with gentle
     swirling cloud lobes and dissolving wispy trail puffs gliding behind the
     cursor across all 5 screens.

Quality & Accessibility:
- 100% mouse-transparent (``WA_TransparentForMouseEvents``) and non-focusable.
- Uses a lightweight ``QApplication`` eventFilter only while visible & active
  (cleanly removed on ``hideEvent`` / ``reduced_motion=True``).
- Strictly presentation-only: zero domain imports.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QCursor,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget

from src.gui.animations.motion_config import DEFAULT_MOTION


@dataclass
class _ShootingStar:
    """Single active meteor streak in normalized viewport coordinates."""

    x0: float
    y0: float
    dx: float
    dy: float
    progress: float = 0.0
    speed: float = 0.024
    tail_len: float = 0.16
    scale: float = 1.0
    warm_gold: bool = True


@dataclass
class _MistPuff:
    """Soft expanding circular mist cloud left behind a gliding cursor."""

    x: float
    y: float
    base_radius: float
    progress: float = 0.0
    speed: float = 0.055


# Deterministic curated meteor flight paths across upper/side skies
_METEOR_PRESETS: tuple[tuple[float, float, float, float, float, float, bool], ...] = (
    (0.88, 0.06, -0.34, 0.20, 0.024, 0.17, True),
    (0.14, 0.08, 0.30, 0.16, 0.026, 0.15, False),
    (0.94, 0.14, -0.28, 0.24, 0.022, 0.16, True),
    (0.72, 0.04, -0.32, 0.15, 0.025, 0.18, False),
    (0.06, 0.18, 0.26, 0.22, 0.023, 0.14, True),
    (0.92, 0.26, -0.24, 0.22, 0.024, 0.15, True),
)


class AmbientStardustOverlay(QWidget):
    """Global click-through overlay painting shooting stars, golden stardust & circular cursor mist."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveAmbientStardustOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)
        self._phase: float = 0.0
        self._meteor_cursor: int = 0
        self._ticks_until_meteor: int = 24
        self._meteors: list[_ShootingStar] = []

        # Smooth fluid circular mist / cloud aura state
        self._cursor_target: Optional[QPointF] = None
        self._cursor_pos: Optional[QPointF] = None
        self._cursor_alpha: float = 0.0
        self._cursor_idle_ticks: int = 0
        self._last_puff_pos: Optional[QPointF] = None
        self._mist_puffs: list[_MistPuff] = []
        self._filter_installed: bool = False

        # 48 deterministic golden sand / stardust motes
        self._grains: tuple[tuple[float, float, float, float, float, float, float, bool], ...] = tuple(
            (
                ((i * 37 + 7) % 100) / 100.0,
                ((i * 59 + 13) % 100) / 100.0,
                0.30 + 0.70 * ((i % 5) / 4.0),
                0.00055 + 0.00085 * ((i % 4) / 3.0),
                0.006 + 0.012 * ((i % 3) / 2.0),
                (i * 1.31) % (2.0 * math.pi),
                1.0 + 2.1 * ((i % 4) / 3.0),
                (i % 4) == 0,
            )
            for i in range(48)
        )

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS silky low-CPU loop
        self._timer.timeout.connect(self._on_tick)

        if self._reduced_motion:
            self.setVisible(False)

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @property
    def active_meteor_count(self) -> int:
        return len(self._meteors)

    @property
    def active_mist_puff_count(self) -> int:
        return len(self._mist_puffs)

    def set_reduced_motion(self, enabled: bool) -> None:
        flag = bool(enabled)
        self._reduced_motion = flag
        if flag:
            self._timer.stop()
            self._uninstall_event_filter()
            self._meteors.clear()
            self._mist_puffs.clear()
            self._cursor_target = None
            self._cursor_pos = None
            self._cursor_alpha = 0.0
            self.setVisible(False)
        else:
            self.setVisible(True)
            self.raise_()
            if self.parentWidget() is not None and self.parentWidget().isVisible():
                self._install_event_filter()
                self._timer.start()

    def set_cursor_preview(self, pos: Optional[QPointF], *, spawn_trail: bool = False) -> None:
        """Set cursor mist position explicitly (used for headless QA & tests)."""
        if pos is None or self._reduced_motion:
            self._cursor_target = None
            self._cursor_pos = None
            self._cursor_alpha = 0.0
            self._mist_puffs.clear()
            return
        self._cursor_target = QPointF(pos)
        self._cursor_pos = QPointF(pos)
        self._cursor_alpha = 1.0
        self._cursor_idle_ticks = 0
        if spawn_trail:
            self._mist_puffs = [
                _MistPuff(pos.x() - i * 24.0, pos.y() + i * 9.0, 26.0 + i * 3.0, progress=i * 0.16)
                for i in range(1, 5)
            ]
        self.update()

    def trigger_shooting_star(self) -> None:
        """Spawn one shooting star immediately."""
        if self._reduced_motion or len(self._meteors) >= 2:
            return
        x0, y0, dx, dy, spd, tlen, warm = _METEOR_PRESETS[self._meteor_cursor % len(_METEOR_PRESETS)]
        self._meteor_cursor += 1
        self._meteors.append(
            _ShootingStar(
                x0=x0,
                y0=y0,
                dx=dx,
                dy=dy,
                progress=0.0,
                speed=spd,
                tail_len=tlen,
                scale=0.92 + 0.20 * ((self._meteor_cursor % 3) / 2.0),
                warm_gold=warm,
            )
        )

    def _install_event_filter(self) -> None:
        if self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._filter_installed = True

    def _uninstall_event_filter(self) -> None:
        if not self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._filter_installed = False

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if self._reduced_motion or not self.isVisible():
            return False
        etype = event.type()
        if etype in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            local = self.mapFromGlobal(QCursor.pos())
            if self.rect().contains(local):
                pt = QPointF(float(local.x()), float(local.y()))
                self._cursor_target = pt
                if self._cursor_pos is None:
                    self._cursor_pos = QPointF(pt)
                self._cursor_idle_ticks = 0
                if self._last_puff_pos is None:
                    self._last_puff_pos = QPointF(pt)
                else:
                    dist = math.hypot(pt.x() - self._last_puff_pos.x(), pt.y() - self._last_puff_pos.y())
                    if dist >= 22.0:
                        self._mist_puffs.append(
                            _MistPuff(pt.x(), pt.y(), 24.0 + min(14.0, dist * 0.18), progress=0.0)
                        )
                        if len(self._mist_puffs) > 10:
                            self._mist_puffs.pop(0)
                        self._last_puff_pos = QPointF(pt)
        elif etype == QEvent.Type.Leave and watched is self.window():
            self._cursor_target = None
        return False

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._reduced_motion:
            self._install_event_filter()
            if not self._timer.isActive():
                self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        self._uninstall_event_filter()
        super().hideEvent(event)

    def _on_tick(self) -> None:
        if self._reduced_motion or not self.isVisible():
            self._timer.stop()
            return
        self._phase = (self._phase + 0.04) % (200.0 * math.pi)

        # 1. Advance smooth fluid circular mist tracking
        if self._cursor_target is not None:
            self._cursor_idle_ticks += 1
            if self._cursor_pos is None:
                self._cursor_pos = QPointF(self._cursor_target)
            else:
                self._cursor_pos = QPointF(
                    self._cursor_pos.x() + (self._cursor_target.x() - self._cursor_pos.x()) * 0.24,
                    self._cursor_pos.y() + (self._cursor_target.y() - self._cursor_pos.y()) * 0.24,
                )
            # Stay luminous while gliding; soften gently if cursor rests still for > 2s
            target_a = 1.0 if self._cursor_idle_ticks < 65 else 0.42
            self._cursor_alpha += (target_a - self._cursor_alpha) * 0.14
        else:
            self._cursor_alpha *= 0.86
            if self._cursor_alpha < 0.01:
                self._cursor_alpha = 0.0
                self._cursor_pos = None

        # 2. Advance & dissolve trailing mist clouds
        live_puffs: list[_MistPuff] = []
        for pf in self._mist_puffs:
            pf.progress += pf.speed
            if pf.progress < 1.0:
                live_puffs.append(pf)
        self._mist_puffs = live_puffs

        # 3. Advance active shooting stars
        alive: list[_ShootingStar] = []
        for m in self._meteors:
            m.progress += m.speed
            if m.progress <= 1.25:
                alive.append(m)
        self._meteors = alive

        self._ticks_until_meteor -= 1
        if self._ticks_until_meteor <= 0:
            self.trigger_shooting_star()
            self._ticks_until_meteor = 82 + (self._meteor_cursor * 23) % 48

        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._reduced_motion:
            return
        w, h = float(self.width()), float(self.height())
        if w <= 8.0 or h <= 8.0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        phase = self._phase

        # 1. Circular Warm Mist & Swirling Cloud Halo following the cursor
        self._paint_cursor_mist(p, phase)

        # 2. Drifting Golden Sand & Stardust Motes
        p.setPen(Qt.PenStyle.NoPen)
        for x0, y0, depth, vx, vy_amp, p0, radius, is_sparkle in self._grains:
            nx = (x0 + phase * vx * 14.0 * depth + math.sin(phase * 0.45 + p0) * 0.012) % 1.0
            ny = (y0 - phase * vx * 6.5 * depth + math.cos(phase * 0.65 + p0) * vy_amp) % 1.0
            mx, my = nx * w, ny * h

            dx_c = (nx - 0.5) * 2.0
            dy_c = (ny - 0.5) * 2.0
            edge_dist = min(1.0, math.hypot(dx_c * 0.92, dy_c * 0.85))
            edge_weight = 0.36 + 0.64 * (edge_dist * edge_dist)

            twinkle = 0.38 + 0.62 * (0.5 + 0.5 * math.sin(phase * (1.7 + depth) + p0))
            alpha = int((46 + 98 * depth) * twinkle * edge_weight)
            if alpha <= 5:
                continue

            r_eff = radius * (0.78 + 0.42 * depth)
            if is_sparkle:
                core_col = QColor(255, 248, 222, min(225, int(alpha * 1.25)))
                halo_col = QColor(244, 204, 122, int(alpha * 0.45))
            else:
                core_col = QColor(246, 206, 124, alpha)
                halo_col = QColor(232, 182, 92, int(alpha * 0.36))

            halo = QRadialGradient(QPointF(mx, my), r_eff * 2.9)
            halo.setColorAt(0.0, core_col)
            halo.setColorAt(0.42, halo_col)
            halo.setColorAt(1.0, QColor(halo_col.red(), halo_col.green(), halo_col.blue(), 0))
            p.setBrush(halo)
            p.drawEllipse(QPointF(mx, my), r_eff * 2.9, r_eff * 2.9)

            if is_sparkle and twinkle > 0.64 and edge_dist > 0.42:
                self._draw_star_burst(
                    p,
                    QPointF(mx, my),
                    r_eff * (2.0 + 1.2 * twinkle),
                    QColor(255, 250, 234, min(220, int(alpha * 1.2))),
                )

        # 3. Shooting Stars (Sao băng)
        for m in self._meteors:
            self._paint_shooting_star(p, m, w, h)

        p.end()

    def _paint_cursor_mist(self, p: QPainter, phase: float) -> None:
        p.setPen(Qt.PenStyle.NoPen)

        # A. Trailing expanding circular mist puffs left along the cursor's glide path
        for pf in self._mist_puffs:
            fade = (1.0 - pf.progress) * (1.0 - pf.progress)
            rad = pf.base_radius * (0.85 + 1.15 * pf.progress)
            pt = QPointF(pf.x, pf.y)
            pg = QRadialGradient(pt, rad)
            pg.setColorAt(0.0, QColor(255, 247, 226, int(36 * fade)))
            pg.setColorAt(0.55, QColor(240, 206, 146, int(18 * fade)))
            pg.setColorAt(1.0, QColor(240, 206, 146, 0))
            p.setBrush(pg)
            p.drawEllipse(pt, rad, rad)

        if self._cursor_pos is None or self._cursor_alpha <= 0.02:
            return

        c = self._cursor_pos
        a = self._cursor_alpha
        breathe = 1.0 + 0.06 * math.sin(phase * 1.8)

        # B. Broad soft circular golden-ivory mist aura (matches detective lantern mist!)
        outer_r = 132.0 * breathe
        aura = QRadialGradient(c, outer_r)
        aura.setColorAt(0.0, QColor(255, 248, 228, int(48 * a)))
        aura.setColorAt(0.38, QColor(244, 212, 152, int(28 * a)))
        aura.setColorAt(0.72, QColor(228, 186, 114, int(10 * a)))
        aura.setColorAt(1.0, QColor(228, 186, 114, 0))
        p.setBrush(aura)
        p.drawEllipse(c, outer_r, outer_r)

        # C. 6 gently orbiting translucent mist-cloud lobes creating a billowing circular cloud wreath
        for i in range(6):
            ang = phase * (0.72 if i % 2 == 0 else -0.48) + i * (math.pi / 3.0)
            orbit_r = (34.0 + 7.0 * math.sin(phase * 1.3 + i * 1.1)) * breathe
            lobe_c = QPointF(c.x() + math.cos(ang) * orbit_r, c.y() + math.sin(ang) * orbit_r)
            lobe_r = (42.0 + 8.0 * math.cos(phase * 0.9 + i)) * breathe
            lg = QRadialGradient(lobe_c, lobe_r)
            lg.setColorAt(0.0, QColor(255, 249, 232, int(28 * a)))
            lg.setColorAt(0.48, QColor(236, 196, 128, int(16 * a)))
            lg.setColorAt(1.0, QColor(226, 180, 104, 0))
            p.setBrush(lg)
            p.drawEllipse(lobe_c, lobe_r, lobe_r)

        # D. Feathered circular mist-cloud halo ring (soft radial band, no harsh bubble stroke)
        ring_outer = 62.0 * breathe
        ring_grad = QRadialGradient(c, ring_outer)
        ring_grad.setColorAt(0.0, QColor(255, 250, 236, 0))
        ring_grad.setColorAt(0.56, QColor(255, 248, 226, 0))
        ring_grad.setColorAt(0.76, QColor(246, 214, 152, int(34 * a)))
        ring_grad.setColorAt(0.84, QColor(255, 250, 234, int(44 * a)))
        ring_grad.setColorAt(0.92, QColor(226, 182, 108, int(20 * a)))
        ring_grad.setColorAt(1.0, QColor(226, 182, 108, 0))
        p.setBrush(ring_grad)
        p.drawEllipse(c, ring_outer, ring_outer)

    def _paint_shooting_star(self, p: QPainter, m: _ShootingStar, w: float, h: float) -> None:
        t_head = min(1.0, m.progress)
        t_tail = max(0.0, m.progress - m.tail_len)
        if t_head <= t_tail:
            return

        env = min(1.0, m.progress * 4.5) * max(0.0, min(1.0, (1.22 - m.progress) * 3.8))
        if env <= 0.02:
            return

        def _eval(t: float) -> QPointF:
            arc = math.sin(t * math.pi) * 0.022
            return QPointF((m.x0 + m.dx * t) * w, (m.y0 + m.dy * t - arc) * h)

        head = _eval(t_head)
        tail = _eval(t_tail)

        bloom_grad = QLinearGradient(head, tail)
        if m.warm_gold:
            bloom_grad.setColorAt(0.0, QColor(255, 232, 168, int(135 * env)))
            bloom_grad.setColorAt(0.45, QColor(238, 186, 94, int(58 * env)))
            bloom_grad.setColorAt(1.0, QColor(238, 186, 94, 0))
        else:
            bloom_grad.setColorAt(0.0, QColor(255, 248, 224, int(135 * env)))
            bloom_grad.setColorAt(0.45, QColor(240, 212, 152, int(55 * env)))
            bloom_grad.setColorAt(1.0, QColor(240, 212, 152, 0))

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(bloom_grad, 6.0 * m.scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(head, tail)

        core_grad = QLinearGradient(head, tail)
        core_grad.setColorAt(0.0, QColor(255, 253, 244, int(245 * env)))
        core_grad.setColorAt(0.32, QColor(255, 226, 154, int(175 * env)))
        core_grad.setColorAt(1.0, QColor(246, 198, 108, 0))
        p.setPen(QPen(core_grad, 2.2 * m.scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(head, tail)

        p.setPen(Qt.PenStyle.NoPen)
        h_rad = 13.0 * m.scale
        hg = QRadialGradient(head, h_rad)
        hg.setColorAt(0.0, QColor(255, 254, 246, int(245 * env)))
        hg.setColorAt(0.35, QColor(255, 228, 158, int(145 * env)))
        hg.setColorAt(1.0, QColor(246, 196, 102, 0))
        p.setBrush(hg)
        p.drawEllipse(head, h_rad, h_rad)

        self._draw_star_burst(
            p,
            head,
            9.5 * m.scale,
            QColor(255, 253, 242, int(240 * env)),
        )

        for i in range(1, 6):
            frac = i / 6.0
            sp = QPointF(
                head.x() + (tail.x() - head.x()) * frac + math.sin(m.progress * 18.0 + i * 2.1) * 3.8,
                head.y() + (tail.y() - head.y()) * frac + math.cos(m.progress * 15.0 + i * 1.7) * 3.2,
            )
            sa = int(165 * (1.0 - frac) * env)
            sr = (2.1 - frac * 1.1) * m.scale
            p.setBrush(QColor(255, 238, 186, sa))
            p.drawEllipse(sp, sr, sr)

    @staticmethod
    def _draw_star_burst(p: QPainter, center: QPointF, arm: float, color: QColor) -> None:
        if arm <= 1.0 or color.alpha() <= 4:
            return
        w = max(0.8, arm * 0.18)
        cx, cy = center.x(), center.y()
        star = QPolygonF(
            [
                QPointF(cx, cy - arm),
                QPointF(cx + w, cy - w),
                QPointF(cx + arm, cy),
                QPointF(cx + w, cy + w),
                QPointF(cx, cy + arm),
                QPointF(cx - w, cy + w),
                QPointF(cx - arm, cy),
                QPointF(cx - w, cy - w),
            ]
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPolygon(star)
