"""Rule-specific visual effects layer for the GameBoard (Phase 5 extension).

Presentation-only: receives *cell ids* and a clue *kind* from the board and
draws overlay QGraphicsItems on the shared scene. It NEVER parses
``Clue.parameters``, NEVER touches GameEngine / SAT, and works purely on
card geometry (``card.pos()`` / ``card.card_rect()`` / ``card.public_data``).

Supported effects
-----------------
GLOBAL      whole-board rule  : dashed board frame + scan beam + luminous wave rings
PROFESSION  group by job      : teal rings + marching-ants chain + profession tag
PARITY      even / odd        : pulsing rings (paired for even, travelling wave for odd)
COMPARE     COUNT_COMPARE     : group A / group B rings pulsing in anti-phase + operator link
IMPLIES     IF A THEN B       : curved arrow A -> B with travelling energy dot

Animation is driven by ``tick(phase)`` which GameBoard calls from its ambient
timer (~30 FPS). With ``animate=False`` (reduced motion) only static frames are drawn.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPolygonItem, QGraphicsScene

from src.gui.styles.tokens import TYPOGRAPHY

FX_COLORS: dict[str, str] = {
    "global": "#C8A96B",      # antique brass
    "profession": "#4F8C8D",  # evidence teal
    "parity": "#B97E24",      # warm amber
    "group_a": "#2B6BA0",     # detective blue
    "group_b": "#A14B33",     # rust
    "compare": "#223248",     # deep ink
    "implies": "#6C4BA6",     # violet cord
    "source": "#C48728",
}

COUNTING_TYPES = frozenset({"EXACTLY", "AT_LEAST", "AT_MOST", "NO"})
_IVORY = QColor(252, 248, 240)


# ----------------------------------------------------------------------
# Pure helpers shared with GameBoard (badges / scope inference)
# ----------------------------------------------------------------------


def detect_parity(label: str) -> Optional[str]:
    up = (label or "").upper()
    if "LẺ" in up or "ODD" in up:
        return "odd"
    if "CHẴN" in up or "EVEN" in up:
        return "even"
    return None


def infer_scope(ctype: str, scope: str, n_primary: int, n_secondary: int, n_cards: int) -> str:
    """Return 'ALL', 'PROFESSION' or ''. Falls back to board coverage when scope is unknown."""
    sc = (scope or "").strip().upper()
    if sc in {"ALL", "PROFESSION"}:
        return sc
    if (
        ctype.upper() in COUNTING_TYPES
        and n_secondary == 0
        and n_cards > 0
        and n_primary == n_cards
    ):
        return "ALL"
    return ""


def primary_badge(ctype: str, scope: str, label: str, default: str) -> str:
    ctype = ctype.upper()
    if ctype == "IMPLIES":
        return "NẾU"
    if ctype == "COUNT_COMPARE":
        return "NHÓM A"
    if ctype == "PARITY":
        parity = detect_parity(label)
        return "LẺ" if parity == "odd" else ("CHẴN" if parity == "even" else "CHẴN/LẺ")
    if scope == "PROFESSION":
        return "NGHỀ"
    if scope == "ALL":
        return "TOÀN BÀN"
    return default


def secondary_badge(ctype: str, default: str) -> str:
    ctype = ctype.upper()
    if ctype == "IMPLIES":
        return "THÌ"
    if ctype == "COUNT_COMPARE":
        return "NHÓM B"
    return default


# ----------------------------------------------------------------------
# Graphics items
# ----------------------------------------------------------------------


class _FxPill(QGraphicsItem):
    """Non-interactive rounded label pill."""

    def __init__(self, text: str, bg_hex: str, center: QPointF) -> None:
        super().__init__()
        self._text = text
        self._bg = QColor(bg_hex)
        self._font = QFont(TYPOGRAPHY.font_family_ui[0])
        self._font.setPixelSize(10)
        self._font.setBold(True)
        fm = QFontMetricsF(self._font)
        w = max(58.0, fm.horizontalAdvance(text) + 20.0)
        h = 22.0
        self._rect = QRectF(-w * 0.5, -h * 0.5, w, h)
        self.setPos(center)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._rect.adjusted(-4.0, -4.0, 4.0, 6.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802, ARG002
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self._rect.height() * 0.5
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 16, 28, 130))
        painter.drawRoundedRect(self._rect.translated(0.0, 2.2), r, r)
        painter.setBrush(self._bg)
        painter.setPen(QPen(QColor(252, 248, 240, 248), 1.6))
        painter.drawRoundedRect(self._rect, r, r)
        painter.setFont(self._font)
        painter.setPen(QColor(255, 252, 246))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.restore()


class _RingItem(QGraphicsItem):
    """Rounded ring hugging a card. ``mode='steady'`` or ``'pulse'`` (sin-driven)."""

    def __init__(self, rect: QRectF, color: str, *, mode: str = "steady", offset: float = 0.0) -> None:
        super().__init__()
        self._rect = QRectF(rect)
        self._color = QColor(color)
        self._mode = mode
        self._offset = float(offset)
        self._level = 1.0 if mode == "steady" else 0.6
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._rect.adjusted(-12.0, -12.0, 12.0, 12.0)

    def set_phase(self, phase: float) -> None:
        if self._mode == "steady":
            return
        self._level = 0.5 + 0.5 * math.sin(phase * 3.2 + self._offset)
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802, ARG002
        lvl = self._level
        grow = 3.0 if self._mode == "steady" else 2.0 + 4.0 * lvl
        width = 2.4 if self._mode == "steady" else 2.0 + 1.4 * lvl
        rect = self._rect.adjusted(-grow, -grow, grow, grow)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(252, 248, 240, 150), width + 2.4))
        painter.drawRoundedRect(rect, 12.0, 12.0)
        core = QColor(self._color)
        core.setAlpha(int(150 + 105 * lvl))
        painter.setPen(QPen(core, width))
        painter.drawRoundedRect(rect, 12.0, 12.0)
        painter.restore()


class _MarchingPath(QGraphicsItem):
    """Dashed path with ivory halo; dash offset advances with phase (marching ants)."""

    def __init__(
        self,
        path: QPainterPath,
        color: str,
        *,
        width: float = 2.4,
        dash: tuple[float, float] = (6.0, 4.0),
        speed: float = 4.0,
    ) -> None:
        super().__init__()
        self._path = QPainterPath(path)
        self._color = QColor(color)
        self._width = width
        self._dash = list(dash)
        self._speed = speed
        self._offset = 0.0
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._path.boundingRect().adjusted(-10.0, -10.0, 10.0, 10.0)

    def set_phase(self, phase: float) -> None:
        self._offset = -phase * self._speed
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802, ARG002
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        halo = QPen(QColor(252, 248, 240, 215), self._width + 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(halo)
        painter.drawPath(self._path)
        core = QPen(self._color, self._width)
        core.setCapStyle(Qt.PenCapStyle.RoundCap)
        core.setDashPattern(self._dash)
        core.setDashOffset(self._offset)
        painter.setPen(core)
        painter.drawPath(self._path)
        painter.restore()


class _ScanBeam(QGraphicsItem):
    """One-shot luminous vertical beam sweeping left -> right across ``rect``."""

    DURATION = 1.5  # phase units (~1.2 s at ambient speed)

    def __init__(self, rect: QRectF, start_phase: float, color: str) -> None:
        super().__init__()
        self._rect = QRectF(rect)
        self._start = start_phase
        self._color = QColor(color)
        self._u = 0.0
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._rect

    def set_phase(self, phase: float) -> None:
        u = (phase - self._start) / self.DURATION
        self._u = 1.0 if u < 0.0 else min(1.0, u)  # phase wrap-around -> treat as finished
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802, ARG002
        u = self._u
        if u <= 0.0 or u >= 1.0:
            return
        band = max(70.0, self._rect.width() * 0.18)
        x = self._rect.left() - band + u * (self._rect.width() + 2.0 * band)
        grad = QLinearGradient(x - band, 0.0, x + band, 0.0)
        fade = math.sin(u * math.pi)
        c0 = QColor(self._color)
        c0.setAlpha(0)
        c1 = QColor(255, 244, 206)
        c1.setAlpha(int(120 * fade))
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.5, c1)
        grad.setColorAt(1.0, c0)
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(self._rect, 14.0, 14.0)
        painter.setClipPath(clip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRect(QRectF(x - band, self._rect.top(), band * 2.0, self._rect.height()))
        painter.restore()


class _TravelDot(QGraphicsItem):
    """Energy dot with a short comet tail looping along a quadratic Bezier."""

    def __init__(self, p0: QPointF, ctrl: QPointF, p2: QPointF, color: str, speed: float = 0.55) -> None:
        super().__init__()
        self._p0, self._c, self._p2 = p0, ctrl, p2
        self._color = QColor(color)
        self._speed = speed
        self._t = 0.0
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:  # noqa: N802
        xs = (self._p0.x(), self._c.x(), self._p2.x())
        ys = (self._p0.y(), self._c.y(), self._p2.y())
        return QRectF(min(xs) - 14, min(ys) - 14, max(xs) - min(xs) + 28, max(ys) - min(ys) + 28)

    def set_phase(self, phase: float) -> None:
        self._t = (phase * self._speed) % 1.0
        self.update()

    def _point(self, t: float) -> QPointF:
        inv = 1.0 - t
        return QPointF(
            inv * inv * self._p0.x() + 2 * inv * t * self._c.x() + t * t * self._p2.x(),
            inv * inv * self._p0.y() + 2 * inv * t * self._c.y() + t * t * self._p2.y(),
        )

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802, ARG002
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(5):
            tt = self._t - i * 0.035
            if tt < 0.0:
                continue
            pt = self._point(tt)
            col = QColor(self._color if i else QColor(255, 250, 232))
            col.setAlpha(int(235 * (1.0 - i / 5.0)))
            r = 5.2 - i * 0.7
            painter.setBrush(col)
            painter.drawEllipse(pt, r, r)
        painter.restore()


# ----------------------------------------------------------------------
# Layer
# ----------------------------------------------------------------------


class RuleEffectsLayer:
    """Owns every overlay item created for the currently focused clue."""

    def __init__(
        self,
        scene: QGraphicsScene,
        cards_getter: Callable[[], Mapping[str, Any]],
    ) -> None:
        self._scene = scene
        self._cards = cards_getter
        self._items: list[QGraphicsItem] = []
        self._animated: list[Any] = []
        self._phase = 0.0

    # -- lifecycle -----------------------------------------------------

    def clear(self) -> None:
        for item in self._items:
            try:
                if item.scene() is self._scene:
                    self._scene.removeItem(item)
            except RuntimeError:
                pass
        self._items.clear()
        self._animated.clear()

    def tick(self, phase: float) -> None:
        self._phase = phase
        for item in self._animated:
            try:
                item.set_phase(phase)
            except RuntimeError:
                pass

    def _add(self, item: QGraphicsItem, *, animated: bool = False, z: float = 30.0) -> None:
        item.setZValue(z)
        self._scene.addItem(item)
        self._items.append(item)
        if animated:
            self._animated.append(item)
            item.set_phase(self._phase)  # type: ignore[attr-defined]

    # -- geometry ------------------------------------------------------

    def _rect(self, cid: str) -> QRectF:
        card = self._cards()[cid]
        r = card.card_rect()
        return QRectF(card.pos() + r.topLeft(), r.size())

    def _union(self, cids: Sequence[str]) -> QRectF:
        rect = self._rect(cids[0])
        for cid in cids[1:]:
            rect = rect.united(self._rect(cid))
        return rect

    def _pin(self, cid: str) -> QPointF:
        r = self._rect(cid)
        return QPointF(r.center().x(), r.top() + 8.5)

    def _order(self, cids: Sequence[str]) -> list[str]:
        cards = self._cards()
        return sorted(cids, key=lambda c: (cards[c].public_data.row, cards[c].public_data.col))

    # -- public entry --------------------------------------------------

    def show(
        self,
        clue_type: str,
        *,
        scope: str = "",
        scope_label: str = "",
        owner_id: Optional[str] = None,
        primary_ids: Iterable[str] = (),
        secondary_ids: Iterable[str] = (),
        label: str = "",
        animate: bool = True,
    ) -> bool:
        """Draw the effect for a focused clue. Returns False if this layer does not handle it."""
        self.clear()
        cards = self._cards()
        ctype = (clue_type or "").strip().upper()
        prim = [c for c in dict.fromkeys(primary_ids) if c in cards]
        sec = [c for c in dict.fromkeys(secondary_ids) if c in cards and c not in prim]

        if ctype == "IMPLIES" and prim and sec:
            self._fx_implies(prim[0], sec[0], label, animate)
            return True
        if ctype == "COUNT_COMPARE" and prim and sec:
            self._fx_compare(prim, sec, label, animate)
            return True
        if ctype == "PARITY" and (prim or sec):
            self._fx_parity(list(dict.fromkeys(prim + sec)), label, animate)
            return True
        sc = infer_scope(ctype, scope, len(prim), len(sec), len(cards))
        if sc == "PROFESSION" and prim:
            self._fx_profession(prim + sec, scope_label or label, animate)
            return True
        if sc == "ALL":
            self._fx_global(label, animate)
            return True
        return False

    # -- effects -------------------------------------------------------

    def _fx_global(self, label: str, animate: bool) -> None:
        ids = list(self._cards())
        box = self._union(ids).adjusted(-12.0, -26.0, 12.0, 16.0)
        path = QPainterPath()
        path.addRoundedRect(box, 14.0, 14.0)
        self._add(
            _MarchingPath(path, FX_COLORS["global"], width=2.6, dash=(7.0, 4.0), speed=3.0),
            animated=animate,
            z=26,
        )
        for cid in ids:
            rect = self._rect(cid)
            rel = (rect.center().x() - box.left()) / max(1.0, box.width())
            self._add(
                _RingItem(
                    rect,
                    FX_COLORS["global"],
                    mode="pulse" if animate else "steady",
                    offset=-rel * 2.0 * math.pi * 0.9,
                ),
                animated=animate,
                z=27,
            )
        if animate:
            self._add(_ScanBeam(box, self._phase, FX_COLORS["global"]), animated=True, z=33)
        self._add(
            _FxPill(label or "TOÀN BÀN", FX_COLORS["global"], QPointF(box.center().x(), box.top())),
            z=35,
        )

    def _fx_profession(self, cids: list[str], label: str, animate: bool) -> None:
        ordered = self._order(cids)
        for cid in ordered:
            self._add(_RingItem(self._rect(cid), FX_COLORS["profession"]), z=27)
        if len(ordered) >= 2:
            chain = QPainterPath(self._rect(ordered[0]).center())
            for cid in ordered[1:]:
                chain.lineTo(self._rect(cid).center())
            self._add(
                _MarchingPath(chain, FX_COLORS["profession"], width=2.2, dash=(5.0, 4.0), speed=5.0),
                animated=animate,
                z=26,
            )
        union = self._union(ordered)
        text = f"NGHỀ · {label.upper()}" if label else "CÙNG NGHỀ"
        self._add(
            _FxPill(text, FX_COLORS["profession"], QPointF(union.center().x(), union.top() - 6.0)),
            z=35,
        )

    def _fx_parity(self, cids: list[str], label: str, animate: bool) -> None:
        parity = detect_parity(label)
        for idx, cid in enumerate(self._order(cids)):
            offset = math.pi * (idx % 2) if parity == "even" else idx * 0.9
            self._add(
                _RingItem(
                    self._rect(cid),
                    FX_COLORS["parity"],
                    mode="pulse" if animate else "steady",
                    offset=offset,
                ),
                animated=animate,
                z=27,
            )
        union = self._union(cids)
        text = label or ("SỐ LẺ" if parity == "odd" else ("SỐ CHẴN" if parity == "even" else "CHẴN / LẺ"))
        self._add(
            _FxPill(text, FX_COLORS["parity"], QPointF(union.center().x(), union.top() - 6.0)),
            z=35,
        )

    def _fx_compare(self, group_a: list[str], group_b: list[str], label: str, animate: bool) -> None:
        for cid in group_a:
            self._add(
                _RingItem(self._rect(cid), FX_COLORS["group_a"], mode="pulse" if animate else "steady", offset=0.0),
                animated=animate,
                z=27,
            )
        for cid in group_b:
            self._add(
                _RingItem(self._rect(cid), FX_COLORS["group_b"], mode="pulse" if animate else "steady", offset=math.pi),
                animated=animate,
                z=27,
            )
        ua, ub = self._union(group_a), self._union(group_b)
        for box_rect, hexcol, tag in ((ua, FX_COLORS["group_a"], "A"), (ub, FX_COLORS["group_b"], "B")):
            frame = QPainterPath()
            frame.addRoundedRect(box_rect.adjusted(-8.0, -16.0, 8.0, 10.0), 12.0, 12.0)
            self._add(_MarchingPath(frame, hexcol, width=2.0, dash=(6.0, 4.0), speed=2.5), animated=animate, z=25)
            self._add(
                _FxPill(f"NHÓM {tag} · {len(group_a) if tag == 'A' else len(group_b)} Ô", hexcol,
                        QPointF(box_rect.center().x(), box_rect.top() - 18.0)),
                z=35,
            )
        ca, cb = ua.center(), ub.center()
        mid = QPointF((ca.x() + cb.x()) * 0.5, (ca.y() + cb.y()) * 0.5)
        ctrl = QPointF(mid.x(), mid.y() - max(36.0, min(64.0, abs(ca.y() - cb.y()) * 0.25 + 36.0)))
        link = QPainterPath(ca)
        link.quadTo(ctrl, cb)
        self._add(_MarchingPath(link, FX_COLORS["compare"], width=2.6, dash=(5.0, 4.0), speed=6.0), animated=animate, z=29)
        bez_mid = QPointF(
            0.25 * ca.x() + 0.5 * ctrl.x() + 0.25 * cb.x(),
            0.25 * ca.y() + 0.5 * ctrl.y() + 0.25 * cb.y(),
        )
        self._add(_FxPill(label or "SO SÁNH", FX_COLORS["compare"], bez_mid), z=36)

    def _fx_implies(self, antecedent: str, consequent: str, label: str, animate: bool) -> None:
        self._add(_RingItem(self._rect(antecedent), FX_COLORS["group_a"]), z=27)
        self._add(_RingItem(self._rect(consequent), FX_COLORS["group_b"]), z=27)
        p0, p2 = self._pin(antecedent), self._pin(consequent)
        mid_x, mid_y = (p0.x() + p2.x()) * 0.5, (p0.y() + p2.y()) * 0.5
        if abs(p2.x() - p0.x()) < 28.0:
            ctrl = QPointF(mid_x + 64.0, mid_y)  # same column: arch into the gutter
        else:
            ctrl = QPointF(mid_x, mid_y - max(38.0, min(66.0, abs(p2.y() - p0.y()) * 0.25 + 38.0)))
        cord = QPainterPath(p0)
        cord.quadTo(ctrl, p2)
        self._add(_MarchingPath(cord, FX_COLORS["implies"], width=2.8, dash=(9.0, 3.0), speed=3.0), animated=animate, z=29)

        dx, dy = p2.x() - ctrl.x(), p2.y() - ctrl.y()
        length = math.hypot(dx, dy)
        if length > 1e-3:
            ux, uy = dx / length, dy / length
            px, py = -uy, ux
            head = QGraphicsPolygonItem(
                QPolygonF([
                    p2,
                    QPointF(p2.x() - ux * 10.0 + px * 5.0, p2.y() - uy * 10.0 + py * 5.0),
                    QPointF(p2.x() - ux * 10.0 - px * 5.0, p2.y() - uy * 10.0 - py * 5.0),
                ])
            )
            head.setBrush(QBrush(QColor(FX_COLORS["implies"])))
            head.setPen(QPen(_IVORY, 1.0))
            head.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._add(head, z=31)
        if animate:
            self._add(_TravelDot(p0, ctrl, p2, FX_COLORS["implies"]), animated=True, z=34)
        mid = QPointF(
            0.25 * p0.x() + 0.5 * ctrl.x() + 0.25 * p2.x(),
            0.25 * p0.y() + 0.5 * ctrl.y() + 0.25 * p2.y(),
        )
        self._add(_FxPill(label or "NẾU → THÌ", FX_COLORS["implies"], mid), z=36)