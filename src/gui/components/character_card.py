"""CharacterCard QGraphicsObject rendering A01/A02 Suspect Dossier Cards (Phase 3–5).

Strict presentation rules:
    - Displays ONLY public information from ``PublicCharacterView``.
    - HIDDEN cards use ``A01_card_back.png`` (shared scaled pixmap) with a dark
      scrim behind public Cell ID, Name, Profession, and neutral status. NEVER
      uses crimson/teal or leaks hidden verdict/clue.
    - REVEALED cards use ``A02_card_front_template.png`` (shared scaled pixmap).
      CRITICAL Phase 1 rule: A02's bottom-left plaque is pre-painted crimson red,
      so INNOCENT cards ALWAYS paint an opaque ``INNOCENT_TEAL`` (#41B99A) badge
      completely covering that plaque, paired with a geometric check icon and
      bold navy ``INNOCENT`` text.
    - Phase 5 Motion Extensions:
        * Physical 3D projective Y-axis card flip (lift + perspective trapezoid +
          metallic card rim + directional tilt lighting + dynamic shadow +
          non-mirrored front face switching strictly at 90°).
        * 3-layer luminous cyan evidence highlight (localized outer halo +
          crisp cyan accent border + brackets) coexisting cleanly with Gold
          selection frame and Crimson/Teal verdict badges.
        * Smooth 150ms hover elevation & 210ms selection transitions respecting
          ``reduced_motion`` without ever altering grid ``pos()``.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    Property,
    QAbstractAnimation,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from src.gui.styles.tokens import COLORS, GEOMETRY, TYPOGRAPHY
from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.view_models import CardVisibility, PublicCharacterView

if TYPE_CHECKING:
    from src.gui.animations.card_flip import FlipFrameState


class CardDisplayMode(str, Enum):
    """Density presets matching 3x3 (EXPANDED), 4x4 (STANDARD), and 5x5 (COMPACT)."""

    EXPANDED = "EXPANDED"   # 3x3 — 150x200 (3:4)
    STANDARD = "STANDARD"   # 4x4 — 132x176 (3:4)
    COMPACT = "COMPACT"     # 5x5 — 114x152 (3:4)


CARD_DIMENSIONS_BY_MODE: dict[CardDisplayMode, tuple[int, int]] = {
    CardDisplayMode.EXPANDED: (150, 200),  # exact 3:4
    CardDisplayMode.STANDARD: (132, 176),  # exact 3:4
    CardDisplayMode.COMPACT: (114, 152),   # exact 3:4
}


class CharacterCard(QGraphicsObject):
    """Reusable interactive suspect card rendered inside ``GameBoard``."""

    card_selected = Signal(str)  # Emits cell_id on user click or keyboard Enter/Space

    def __init__(
        self,
        data: PublicCharacterView,
        *,
        display_mode: CardDisplayMode = CardDisplayMode.STANDARD,
        card_back_pixmap: Optional[QPixmap] = None,
        card_front_pixmap: Optional[QPixmap] = None,
        portrait_pixmap: Optional[QPixmap] = None,
        portrait_path: Optional[str] = None,
        reduced_motion: bool = False,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self._data: PublicCharacterView = data
        self._mode: CardDisplayMode = display_mode
        self._width, self._height = CARD_DIMENSIONS_BY_MODE[display_mode]
        self._card_back_pixmap: Optional[QPixmap] = card_back_pixmap
        self._card_front_pixmap: Optional[QPixmap] = card_front_pixmap
        self._portrait_pixmap: Optional[QPixmap] = (
            portrait_pixmap if (portrait_pixmap is not None and not portrait_pixmap.isNull()) else None
        )
        self._portrait_path: Optional[str] = portrait_path

        # Independent visual presentation flags
        self._selected: bool = False
        self._highlighted: bool = False
        self._evidence_role: str = "primary"
        self._focus_dimmed = False
        self._focus_anim = QPropertyAnimation(self, b"opacity", self)
        self._focus_anim.setDuration(DEFAULT_MOTION.focus_dim_duration)
        self._shake_offset = 0.0
        self._shake_anim = QPropertyAnimation(self, b"shake_offset", self)
        self._hovered: bool = False
        self._interactive: bool = True
        self._reduced_motion: bool = bool(reduced_motion)

        # Phase 5 smooth visual properties (never mutate grid pos() or domain data)
        self._flip_progress: float = 1.0
        self._hover_level: float = 0.0
        self._selection_level: float = 0.0
        self._glow_intensity: float = 0.0
        self._glow_pulse: float = 0.0

        # Active 3D flip transient state (never exposed as committed data before finish)
        self._flip_frame: Optional["FlipFrameState"] = None
        self._flip_target_data: Optional[PublicCharacterView] = None

        # Lightweight property animations for hover & selection feedback
        self._hover_anim = QPropertyAnimation(self, b"hover_level", self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._select_anim = QPropertyAnimation(self, b"selection_level", self)
        self._select_anim.setDuration(210)
        self._select_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_tooltip()

    # ------------------------------------------------------------------
    # Properties & Public API (GĐ3 preserved + GĐ5 extensions)
    # ------------------------------------------------------------------

    @property
    def cell_id(self) -> str:
        return self._data.cell_id

    @property
    def public_data(self) -> PublicCharacterView:
        return self._data

    @property
    def display_mode(self) -> CardDisplayMode:
        return self._mode

    @property
    def is_revealed(self) -> bool:
        return self._data.is_revealed

    @property
    def is_selected(self) -> bool:
        return self._selected

    @property
    def is_highlighted(self) -> bool:
        return self._highlighted

    @property
    def is_hovered(self) -> bool:
        return self._hovered

    @property
    def is_interactive(self) -> bool:
        return self._interactive

    @property
    def is_animating_flip(self) -> bool:
        return self._flip_frame is not None

    @property
    def flip_frame(self) -> Optional["FlipFrameState"]:
        return self._flip_frame

    @property
    def glow_intensity(self) -> float:
        return self._glow_intensity

    @property
    def glow_pulse(self) -> float:
        return self._glow_pulse

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @property
    def has_portrait(self) -> bool:
        return self._portrait_pixmap is not None and not self._portrait_pixmap.isNull()

    @property
    def portrait_pixmap(self) -> Optional[QPixmap]:
        return self._portrait_pixmap

    @property
    def portrait_path(self) -> Optional[str]:
        return self._portrait_path

    def set_portrait_pixmap(
        self,
        pixmap: Optional[QPixmap],
        *,
        portrait_path: Optional[str] = None,
    ) -> None:
        """Assign or clear the cached character portrait pixmap."""
        self._portrait_pixmap = (
            pixmap if (pixmap is not None and not pixmap.isNull()) else None
        )
        self._portrait_path = portrait_path if self._portrait_pixmap is not None else None
        self.update()

    def _get_flip_progress(self) -> float:
        return self._flip_progress

    def _set_flip_progress(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if clamped != self._flip_progress:
            self._flip_progress = clamped
            self.update()

    flip_progress = Property(float, _get_flip_progress, _set_flip_progress)

    def _get_hover_level(self) -> float:
        return self._hover_level

    def _set_hover_level(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if clamped != self._hover_level:
            self._hover_level = clamped
            self.update()

    hover_level = Property(float, _get_hover_level, _set_hover_level)

    def _get_selection_level(self) -> float:
        return self._selection_level

    def _set_selection_level(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if clamped != self._selection_level:
            self._selection_level = clamped
            self.update()

    selection_level = Property(float, _get_selection_level, _set_selection_level)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            self._stop_transition_anims()
            self._focus_anim.stop()
            self._shake_anim.stop()
            self._shake_offset = 0.0
            self.setOpacity(DEFAULT_MOTION.focus_dim_opacity if self._focus_dimmed else 1.0)
            self._hover_level = 1.0 if self._hovered else 0.0
            self._selection_level = 1.0 if self._selected else 0.0
            self.update()

    def set_public_data(self, data: PublicCharacterView) -> None:
        """Update card presentation data in-place (programmatic — emits no signal)."""
        if data.cell_id != self._data.cell_id:
            raise ValueError(
                f"Cannot reassign CharacterCard {self._data.cell_id!r} to {data.cell_id!r}"
            )
        self._data = data
        self._refresh_tooltip()
        self.update()

    def set_shared_pixmaps(
        self,
        *,
        card_back_pixmap: Optional[QPixmap],
        card_front_pixmap: Optional[QPixmap],
    ) -> None:
        self._card_back_pixmap = card_back_pixmap
        self._card_front_pixmap = card_front_pixmap
        self.update()

    def set_selected(self, selected: bool) -> None:
        flag = bool(selected)
        if flag != self._selected:
            self._selected = flag
            self._sync_z_order()
            self._animate_selection(1.0 if flag else 0.0)
            self.update()

    def set_highlighted(self, highlighted: bool) -> None:
        flag = bool(highlighted)
        if flag != self._highlighted:
            self._highlighted = flag
            if flag and self._glow_intensity <= 0.0:
                self._glow_intensity = 0.86
            elif not flag and self._reduced_motion:
                self._glow_intensity = 0.0
                self._glow_pulse = 0.0
            self.update()

    def set_focus_context(self, dimmed: bool, role: str = "reference") -> None:
        self._focus_dimmed = dimmed
        self._evidence_role = role
        self._focus_anim.stop()
        target = DEFAULT_MOTION.focus_dim_opacity if dimmed else 1.0
        if self._reduced_motion:
            self.setOpacity(target)
        else:
            self._focus_anim.setStartValue(self.opacity())
            self._focus_anim.setEndValue(target)
            self._focus_anim.start()
        self.update()

    def _set_shake_offset(self, value: float) -> None:
        self._shake_offset = value
        self.update()

    shake_offset = Property(float, lambda self: self._shake_offset, _set_shake_offset)

    def shake(self) -> None:
        if self._reduced_motion:
            return
        self._shake_anim.stop()
        self._shake_anim.setDuration(DEFAULT_MOTION.contradiction_shake_duration)
        for t, value in ((0, 0), (.18, -3), (.36, 3), (.54, -2), (.72, 2), (1, 0)):
            self._shake_anim.setKeyValueAt(t, value)
        self._shake_anim.start()

    def reset_interaction_visuals(self) -> None:
        self._focus_anim.stop()
        self._shake_anim.stop()
        self._shake_offset = 0.0
        self._focus_dimmed = False
        self.setOpacity(1.0)
        self.update()

    def set_glow_state(self, intensity: float, pulse: float = 0.0) -> None:
        """Update localized luminous cyan glow intensity & pulse amplitude."""
        ni = max(0.0, min(1.0, float(intensity)))
        np = max(0.0, min(1.0, float(pulse)))
        if ni != self._glow_intensity or np != self._glow_pulse:
            self._glow_intensity = ni
            self._glow_pulse = np
            self.update()

    def set_interactive(self, enabled: bool) -> None:
        flag = bool(enabled)
        if flag != self._interactive:
            self._interactive = flag
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, flag)
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if flag else Qt.CursorShape.ArrowCursor
            )
            if not flag and self._hovered:
                self._hovered = False
                self._animate_hover(0.0)
                self._sync_z_order()
            self.update()

    # ------------------------------------------------------------------
    # Phase 5 3D Flip Lifecycle Hooks (called by CardFlipAnimation)
    # ------------------------------------------------------------------

    def begin_flip_animation(self, target_data: PublicCharacterView) -> None:
        """Prepare transient flip target without prematurely changing ``public_data``."""
        if target_data.cell_id != self._data.cell_id:
            raise ValueError(
                f"Flip target mismatch: {self._data.cell_id!r} vs {target_data.cell_id!r}"
            )
        self._flip_target_data = target_data
        self._flip_progress = 0.0
        self.setZValue(20.0)  # Elevate strictly above all neighboring cards during flip
        self.update()

    def set_flip_frame(self, frame: "FlipFrameState") -> None:
        """Apply one physical 3D frame and schedule localized repaint."""
        self._flip_frame = frame
        self._flip_progress = frame.t
        self.update()

    def finish_flip_animation(self, committed_data: PublicCharacterView) -> None:
        """Commit final REVEALED public data and restore resting transform & z-order."""
        self._flip_frame = None
        self._flip_target_data = None
        self._flip_progress = 1.0
        self._data = committed_data
        self._sync_z_order()
        self._refresh_tooltip()
        self.update()

    def cancel_flip_animation(
        self,
        *,
        restore_data: Optional[PublicCharacterView] = None,
    ) -> None:
        """Abort transient flip state cleanly and restore normal z-order."""
        self._flip_frame = None
        self._flip_target_data = None
        self._flip_progress = 1.0
        if restore_data is not None and restore_data.cell_id == self._data.cell_id:
            self._data = restore_data
            self._refresh_tooltip()
        self._sync_z_order()
        self.update()

    def reset_motion_visuals(self) -> None:
        """Stop all local animations and reset transient motion state."""
        self._stop_transition_anims()
        self._flip_frame = None
        self._flip_target_data = None
        self._flip_progress = 1.0
        self._hover_level = 1.0 if self._hovered else 0.0
        self._selection_level = 1.0 if self._selected else 0.0
        self._glow_intensity = 0.86 if self._highlighted else 0.0
        self._glow_pulse = 0.0
        self._sync_z_order()
        self.update()

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _sync_z_order(self) -> None:
        if self._flip_frame is not None or self._flip_target_data is not None:
            self.setZValue(20.0)
        elif self._selected:
            self.setZValue(3.0)
        elif self._hovered:
            self.setZValue(2.0)
        elif self._highlighted:
            self.setZValue(1.0)
        else:
            self.setZValue(0.0)

    def _stop_transition_anims(self) -> None:
        if self._hover_anim.state() != QAbstractAnimation.State.Stopped:
            self._hover_anim.stop()
        if self._select_anim.state() != QAbstractAnimation.State.Stopped:
            self._select_anim.stop()

    def _animate_hover(self, target: float) -> None:
        if self._hover_anim.state() != QAbstractAnimation.State.Stopped:
            self._hover_anim.stop()
        if self._reduced_motion:
            self._hover_level = target
            self.update()
            return
        self._hover_anim.setStartValue(self._hover_level)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def _animate_selection(self, target: float) -> None:
        if self._select_anim.state() != QAbstractAnimation.State.Stopped:
            self._select_anim.stop()
        if self._reduced_motion:
            self._selection_level = target
            self.update()
            return
        self._select_anim.setStartValue(self._selection_level)
        self._select_anim.setEndValue(target)
        self._select_anim.start()

    def _refresh_tooltip(self) -> None:
        d = self._data
        if d.visibility is CardVisibility.HIDDEN:
            tip = (
                f"{d.cell_id} — {d.name}\n"
                f"Nghề nghiệp: {d.profession}\n"
                f"Trạng thái: Chưa chứng minh (HIDDEN)"
            )
        else:
            verdict_vi = "Tội phạm (CRIMINAL)" if d.verdict == "CRIMINAL" else "Vô tội (INNOCENT)"
            clue_line = "\nManh mối: Đã công khai" if d.has_public_clue else ""
            tip = (
                f"{d.cell_id} — {d.name}\n"
                f"Nghề nghiệp: {d.profession}\n"
                f"Kết luận: {verdict_vi}{clue_line}"
            )
        self.setToolTip(tip)

    # ------------------------------------------------------------------
    # Qt Graphics Geometry & Events
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802
        # Generous padding for 3D perspective lift, offset drop shadow & luminous cyan glow
        return QRectF(-22.0, -26.0, self._width + 44.0, self._height + 52.0)

    def card_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, float(self._width), float(self._height))

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        if self._interactive:
            self._hovered = True
            self._sync_z_order()
            self._animate_hover(1.0)
            self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        if self._hovered:
            self._hovered = False
            self._sync_z_order()
            self._animate_hover(0.0)
            self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._interactive and event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.card_selected.emit(self._data.cell_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._interactive and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.card_selected.emit(self._data.cell_id)
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Painting (100% Token-Driven, Cached Artwork, True 3D Flip + Glow)
    # ------------------------------------------------------------------

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,  # noqa: ARG002
        widget: Optional[QWidget] = None,  # noqa: ARG002
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.translate(self._shake_offset, 0)

        rect = self.card_rect()
        radius = 8.0 if self._mode is CardDisplayMode.COMPACT else 10.0

        if self._flip_frame is not None:
            self._paint_with_3d_flip(painter, rect, radius, self._flip_frame)
            painter.restore()
            return

        # Subtle physical hover lift (visual paint offset ONLY — never mutates pos())
        hover_lift_px = (
            2.0 if self._mode is CardDisplayMode.COMPACT
            else (3.5 if self._mode is CardDisplayMode.EXPANDED else 3.0)
        )
        lift_dy = -hover_lift_px * self._hover_level

        # Resting / Hover ground shadow beneath card
        if self._hover_level > 0.01 or self._selection_level > 0.01:
            shadow_dy = 3.0 + 4.5 * self._hover_level
            shadow_alpha = int(52 + 48 * self._hover_level + 22 * self._selection_level)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(4, 8, 18, min(145, shadow_alpha)))
            painter.drawRoundedRect(
                rect.translated(1.5 * self._hover_level, shadow_dy),
                radius + 1.0,
                radius + 1.0,
            )

        if abs(lift_dy) > 0.01:
            painter.translate(0.0, lift_dy)

        self._paint_card_surface(painter, rect, radius, self._data)
        self._paint_state_overlays(painter, rect, radius)
        painter.restore()

    def _paint_with_3d_flip(
        self,
        painter: QPainter,
        rect: QRectF,
        radius: float,
        frame: "FlipFrameState",
    ) -> None:
        """Render physical lifted shadow + 3D projective Y-rotated card + metallic rim."""
        from src.gui.animations.card_flip import build_perspective_y_transform

        w, h = rect.width(), rect.height()

        # 1. Dynamic soft drop shadow resting on the board table beneath lifted card
        sw = max(8.0, w * frame.shadow_scale_x)
        sh = h * (0.96 + 0.03 * frame.lift_factor)
        sx = (w - sw) * 0.5 + frame.shadow_offset_x
        sy = (h - sh) * 0.5 + frame.shadow_offset_y
        base_alpha = int(max(0, min(180, round(frame.shadow_alpha * 255))))
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        # Soft 2-layer shadow without heavy QGraphicsBlurEffect
        painter.setBrush(QColor(4, 8, 18, int(base_alpha * 0.45)))
        painter.drawRoundedRect(QRectF(sx - 4.0, sy - 3.0, sw + 8.0, sh + 6.0), radius + 4.0, radius + 4.0)
        painter.setBrush(QColor(4, 8, 18, base_alpha))
        painter.drawRoundedRect(QRectF(sx, sy, sw, sh), radius + 1.0, radius + 1.0)
        painter.restore()

        # 2. Choose active face strictly at 90° midpoint (never leaks front before 90°)
        face_data = (
            self._flip_target_data
            if (frame.show_front and self._flip_target_data is not None)
            else self._data
        )

        # 3. Physical beveled card-stock edge near 90° (eliminates paper-thin disappearance)
        if frame.edge_visibility > 0.05:
            edge_w = max(2.2, 4.5 * frame.edge_visibility)
            edge_h = h * frame.lift_scale
            cx = w * 0.5
            cy = h * 0.5 + frame.lift_y
            edge_rect = QRectF(cx - edge_w * 0.5, cy - edge_h * 0.5, edge_w, edge_h)
            edge_grad = QLinearGradient(edge_rect.topLeft(), edge_rect.bottomLeft())
            edge_grad.setColorAt(0.0, QColor(COLORS.accent_primary))
            edge_grad.setColorAt(0.5, QColor(COLORS.primary_text))
            edge_grad.setColorAt(1.0, QColor(COLORS.accent_primary_pressed))
            painter.save()
            painter.setPen(QPen(QColor(COLORS.backdrop_deep), 0.8))
            painter.setBrush(QBrush(edge_grad))
            painter.drawRoundedRect(edge_rect, 2.0, 2.0)
            painter.restore()

        # 4. Apply TRUE 3D projective perspective QTransform around card center Y-axis
        tx = build_perspective_y_transform(
            w,
            h,
            frame.effective_angle_deg,
            lift_y=frame.lift_y,
            lift_scale=frame.lift_scale,
        )
        painter.save()
        painter.setTransform(tx, combine=True)

        self._paint_card_surface(painter, rect, radius, face_data)

        # 5. Subtle directional angle lighting (depth shading + warm metallic gold highlight)
        tilt = frame.lighting_tilt
        if abs(tilt) > 0.04:
            clip_path = QPainterPath()
            clip_path.addRoundedRect(rect, radius, radius)
            painter.save()
            painter.setClipPath(clip_path)
            grad = QLinearGradient(rect.left(), 0.0, rect.right(), 0.0)
            shade_alpha = int(min(54, abs(tilt) * 58))
            sheen_alpha = int(min(34, abs(tilt) * 36))
            if tilt > 0.0:
                grad.setColorAt(0.0, QColor(228, 185, 109, sheen_alpha))
                grad.setColorAt(0.5, QColor(0, 0, 0, 0))
                grad.setColorAt(1.0, QColor(4, 8, 18, shade_alpha))
            else:
                grad.setColorAt(0.0, QColor(4, 8, 18, shade_alpha))
                grad.setColorAt(0.5, QColor(0, 0, 0, 0))
                grad.setColorAt(1.0, QColor(228, 185, 109, sheen_alpha))
            painter.fillRect(rect, grad)
            painter.restore()

        # Subtle gold rim glint during flip
        rim_alpha = int(90 + 130 * frame.lift_factor)
        painter.setPen(QPen(QColor(228, 185, 109, min(230, rim_alpha)), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        painter.restore()

    def _paint_card_surface(
        self,
        painter: QPainter,
        rect: QRectF,
        radius: float,
        data: PublicCharacterView,
    ) -> None:
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, radius, radius)

        painter.save()
        painter.setClipPath(clip_path)

        if data.visibility is CardVisibility.HIDDEN:
            self._paint_hidden_face(painter, rect, data)
        else:
            self._paint_revealed_face(painter, rect, data)

        # Hover subtle warm illumination sheen (never reveals hidden verdict)
        if self._hover_level > 0.01 and self._interactive and self._flip_frame is None:
            painter.fillRect(rect, QColor(242, 245, 250, int(20 * self._hover_level)))

        painter.restore()  # End rounded clip

        # Base border (smoothly transitions toward warm gold on hover)
        if self._hover_level > 0.01 and self._interactive:
            border_color = self._lerp_color(
                QColor(COLORS.card_border),
                QColor(COLORS.accent_primary),
                self._hover_level,
            )
            border_w = 1.5 + 0.5 * self._hover_level
        else:
            border_color = QColor(COLORS.card_border)
            border_w = 1.5
        painter.setPen(QPen(border_color, border_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

    def _paint_state_overlays(
        self,
        painter: QPainter,
        rect: QRectF,
        radius: float,
    ) -> None:
        """Render independent SELECTED (Gold), HIGHLIGHTED (Luminous Cyan), and FOCUS layers."""
        # Overlay 1 (Outer Halo): LUMINOUS CLUE HIGHLIGHT (Clue Cyan — localized 3-layer glow)
        effective_glow = self._glow_intensity if self._glow_intensity > 0.01 else (0.86 if self._highlighted else 0.0)
        accent = QColor(COLORS.clue_highlight if self._evidence_role == "primary" else COLORS.info_clue_semantic)
        if effective_glow > 0.01:
            tint = QColor(accent)
            tint.setAlpha(int(20 * effective_glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(rect, radius, radius)
            pulse_boost = 0.72 + 0.28 * self._glow_pulse
            lum = effective_glow * pulse_boost
            # Outer offset keeps Cyan glow strictly outside Gold selected border
            outer_pad = 5.5 if self._selection_level > 0.05 else 4.0
            hl_rect = rect.adjusted(-outer_pad, -outer_pad, outer_pad, outer_pad)

            # Layer 2: Soft localized concentric outer glow (bounded <= 9px; no heavy blur)
            for expand, alpha_mul, pen_w in (
                (3.5, 38, 4.5),
                (1.8, 72, 3.2),
            ):
                g_rect = hl_rect.adjusted(-expand, -expand, expand, expand)
                glow_color = QColor(accent)
                glow_color.setAlpha(int(alpha_mul * lum))
                g_pen = QPen(glow_color, pen_w)
                painter.setPen(g_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(g_rect, radius + outer_pad + expand * 0.5, radius + outer_pad + expand * 0.5)

            # Layer 1: Crisp Cyan accent border
            accent.setAlpha(int(235 * effective_glow))
            hl_pen = QPen(accent, 2.2)
            painter.setPen(hl_pen)
            painter.drawRoundedRect(hl_rect, radius + outer_pad * 0.65, radius + outer_pad * 0.65)

            # Layer 3: Luminous cyan corner brackets (color-blind & high-clarity evidence framing)
            self._paint_corner_brackets(
                painter,
                hl_rect,
                QColor(101, 185, 233, int(255 * min(1.0, lum * 1.1))),
                seg=11.0,
                thickness=2.8,
            )

        # Overlay 2 (Inner Frame): SELECTED (Evidence Gold border + inner corner markers)
        sel = self._selection_level if self._selection_level > 0.01 else (1.0 if self._selected else 0.0)
        if sel > 0.01:
            glow_pen = QPen(QColor(228, 185, 109, int(88 * sel)), 5.5)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1.5, radius + 1.5)

            sel_pen = QPen(QColor(228, 185, 109, int(255 * sel)), float(GEOMETRY.border_selected))
            painter.setPen(sel_pen)
            painter.drawRoundedRect(rect.adjusted(-0.5, -0.5, 0.5, 0.5), radius + 0.5, radius + 0.5)

            # Crisp gold corner markers (distinguishes Selected without relying on color alone)
            self._paint_corner_brackets(
                painter,
                rect.adjusted(-1.0, -1.0, 1.0, 1.0),
                QColor(246, 213, 142, int(255 * sel)),
                seg=9.0,
                thickness=2.6,
            )

        # Overlay 3: Keyboard FOCUS ring (always distinct & accessible)
        if self.hasFocus() and self._interactive:
            focus_pen = QPen(QColor(COLORS.focus_ring), 2.0, Qt.PenStyle.DashLine)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3.5, -3.5, 3.5, 3.5), radius + 2.0, radius + 2.0)

    def _compute_portrait_frame_rect(self, rect: QRectF) -> QRectF:
        """Return the upper portrait frame rect scaled proportionally for 3x3 / 4x4 / 5x5."""
        w = rect.width()
        if self._mode is CardDisplayMode.EXPANDED:
            # 150x200 -> 110x104 portrait frame (52% height)
            pw, ph, top_y = 110.0, 104.0, 8.0
        elif self._mode is CardDisplayMode.STANDARD:
            # 132x176 -> 96x89 portrait frame (51% height)
            pw, ph, top_y = 96.0, 89.0, 7.5
        else:
            # 114x152 (5x5 COMPACT) -> 80x72 portrait frame (47.5% height)
            pw, ph, top_y = 80.0, 72.0, 6.0
        px = rect.x() + (w - pw) * 0.5
        return QRectF(px, rect.y() + top_y, pw, ph)

    def _paint_portrait_or_fallback(
        self,
        painter: QPainter,
        rect: QRectF,
        data: PublicCharacterView,
        *,
        on_cream: bool,
        is_criminal: bool = False,
    ) -> None:
        """Render the 2D character portrait in the upper card zone, or initials fallback if missing."""
        p_rect = self._compute_portrait_frame_rect(rect)
        compact = self._mode is CardDisplayMode.COMPACT

        if self.has_portrait and self._portrait_pixmap is not None:
            painter.save()
            # Archival photo well backing so both cutout & contact-sheet portraits match seamlessly
            well_bg = QColor("#F3E8D5" if on_cream else "#EAE0CE")
            if on_cream:
                border_col = QColor(
                    COLORS.criminal_semantic if is_criminal else COLORS.innocent_semantic
                )
            else:
                border_col = QColor(COLORS.brass_accent)

            painter.setPen(QPen(border_col, 1.3 if not compact else 1.1))
            painter.setBrush(well_bg)
            frame_radius = 6.0 if not compact else 5.0
            painter.drawRoundedRect(p_rect, frame_radius, frame_radius)

            inner = p_rect.adjusted(1.5, 1.5, -1.5, -1.5)
            clip = QPainterPath()
            clip.addRoundedRect(inner, max(3.0, frame_radius - 1.0), max(3.0, frame_radius - 1.0))
            painter.setClipPath(clip)

            pm = self._portrait_pixmap
            pm_w, pm_h = float(pm.width()), float(pm.height())
            if pm_w > 0 and pm_h > 0:
                # Fit width/height while keeping 1:1 aspect ratio and prioritizing head/shoulders
                scale = max(inner.width() / pm_w, inner.height() / pm_h)
                draw_w = pm_w * scale
                draw_h = pm_h * scale
                dx = inner.x() + (inner.width() - draw_w) * 0.5
                # Slight top bias (0.22) keeps hat/hair/eyes centered and never clips forehead
                dy = inner.y() + (inner.height() - draw_h) * 0.22
                target_rect = QRectF(dx, dy, draw_w, draw_h)
                painter.drawPixmap(target_rect, pm, QRectF(0.0, 0.0, pm_w, pm_h))

            # Subtle dusk tint on HIDDEN cards so unrevealed cards feel slightly more mysterious
            # while keeping the face & profession outfit 100% clear and readable
            if not on_cream:
                painter.fillRect(inner, QColor(16, 27, 48, 22))

            painter.restore()
            return

        # Intentional Fallback when no portrait mapping exists (e.g. MOCK_* or missing PNG)
        initials = self._compute_initials(data.name)
        circle_d = min(p_rect.width(), p_rect.height()) * (0.72 if not compact else 0.68)
        circle_rect = QRectF(
            p_rect.center().x() - circle_d * 0.5,
            p_rect.center().y() - circle_d * 0.5,
            circle_d,
            circle_d,
        )
        if on_cream:
            ring_color = QColor(COLORS.criminal_semantic if is_criminal else COLORS.innocent_semantic)
            fill_color = QColor("#FBEBEE" if is_criminal else "#E6F4EE")
            init_color = QColor("#8C2D38" if is_criminal else COLORS.ink_primary)
        else:
            ring_color = QColor(COLORS.brass_accent)
            fill_color = QColor(16, 27, 48, 225)
            init_color = QColor(COLORS.primary_text)

        painter.setPen(QPen(ring_color, 2.0 if not compact else 1.7))
        painter.setBrush(fill_color)
        painter.drawEllipse(circle_rect)
        font_px = 13 if compact else (18 if self._mode is CardDisplayMode.EXPANDED else 15)
        painter.setFont(self._ui_font(font_px, bold=True))
        painter.setPen(init_color)
        painter.drawText(circle_rect, Qt.AlignmentFlag.AlignCenter, initials)

    def _paint_hidden_face(
        self,
        painter: QPainter,
        rect: QRectF,
        data: PublicCharacterView,
    ) -> None:
        w, h = rect.width(), rect.height()
        compact = self._mode is CardDisplayMode.COMPACT

        painter.fillRect(rect, QColor(COLORS.backdrop_deep))
        if self._card_back_pixmap is not None and not self._card_back_pixmap.isNull():
            if compact:
                painter.save()
                painter.setOpacity(0.45)
                painter.drawPixmap(rect.toRect(), self._card_back_pixmap)
                painter.restore()
            else:
                painter.drawPixmap(rect.toRect(), self._card_back_pixmap)

        # Upper zone: 2D Portrait (if mapped) or preserve A01 artwork on unmapped MOCK cards
        if self.has_portrait:
            self._paint_portrait_or_fallback(
                painter,
                rect,
                data,
                on_cream=False,
                is_criminal=False,
            )

        self._paint_cell_id_badge(painter, rect, data.cell_id, compact=compact, on_cream=False)

        p_rect = self._compute_portrait_frame_rect(rect)
        scrim_y = (p_rect.bottom() + 3.0) if self.has_portrait else (h * (0.44 if compact else 0.56))
        scrim_rect = QRectF(0.0, scrim_y, w, h - scrim_y)
        r, g, b, a = COLORS.scrim_card_text_rgba
        painter.fillRect(scrim_rect, QColor(r, g, b, 240 if compact else a))
        painter.setPen(QPen(QColor(COLORS.brass_accent if self.has_portrait else COLORS.border_subtle), 1.0))
        painter.drawLine(QPointF(6.0, scrim_y), QPointF(w - 6.0, scrim_y))

        pad_x = 5.5 if compact else 7.5
        name_h = 17.0 if compact else (21.0 if self._mode is CardDisplayMode.EXPANDED else 19.0)
        prof_h = 14.5 if compact else (17.5 if self._mode is CardDisplayMode.EXPANDED else 15.5)
        avail_h = max(1.0, h - scrim_y)
        total_text_h = name_h + prof_h + 2.0
        start_y = scrim_y + max(3.0, (avail_h - total_text_h) * 0.46)

        name_rect = QRectF(pad_x, start_y, w - 2 * pad_x, name_h)
        self._draw_elided_text(
            painter,
            name_rect,
            data.name,
            self._ui_font(11 if compact else (13 if self._mode is CardDisplayMode.STANDARD else 14), bold=True),
            QColor(COLORS.primary_text),
        )

        prof_rect = QRectF(pad_x, name_rect.bottom() + 1.5, w - 2 * pad_x, prof_h)
        self._draw_elided_text(
            painter,
            prof_rect,
            data.profession,
            self._ui_font(10 if compact else 11, bold=False),
            QColor(COLORS.secondary_text),
        )

    def _paint_revealed_face(
        self,
        painter: QPainter,
        rect: QRectF,
        data: PublicCharacterView,
    ) -> None:
        w, h = rect.width(), rect.height()
        compact = self._mode is CardDisplayMode.COMPACT
        is_criminal = data.verdict == "CRIMINAL"

        # 1. Outer ornamental brass frame from A02_card_front_template
        painter.fillRect(rect, QColor(COLORS.paper_beige))
        if self._card_front_pixmap is not None and not self._card_front_pixmap.isNull():
            painter.drawPixmap(rect.toRect(), self._card_front_pixmap)

        # 2. Inner Soft Ivory Suspect Dossier Sheet (Dark Back -> Cream Front on Flip!)
        inset = 4.5 if compact else 5.5
        sheet_rect = rect.adjusted(inset, inset, -inset, -inset)
        accent_border = QColor(COLORS.criminal_semantic if is_criminal else COLORS.innocent_semantic)

        painter.setPen(QPen(QColor(COLORS.brass_accent), 1.3))
        painter.setBrush(QColor(COLORS.paper_sheet))
        painter.drawRoundedRect(sheet_rect, 5.0, 5.0)

        # Top semantic dossier ribbon (Crimson for CRIMINAL, Teal for INNOCENT)
        ribbon_rect = QRectF(sheet_rect.x() + 1.0, sheet_rect.y() + 1.0, sheet_rect.width() - 2.0, 3.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent_border)
        painter.drawRoundedRect(ribbon_rect, 2.0, 2.0)

        # 3. Upper Portrait Window (or Initials Medallion fallback) — identical position to Hidden!
        self._paint_portrait_or_fallback(
            painter,
            rect,
            data,
            on_cream=True,
            is_criminal=is_criminal,
        )

        self._paint_cell_id_badge(painter, rect, data.cell_id, compact=compact, on_cream=True)

        if compact:
            self._paint_revealed_compact_content(painter, rect, data, is_criminal=is_criminal)
            return

        # 4. Warm Cream Nameplate Band below Portrait Window
        p_rect = self._compute_portrait_frame_rect(rect)
        band_y = p_rect.bottom() + 3.0
        band_rect = QRectF(sheet_rect.x() + 1.0, band_y, sheet_rect.width() - 2.0, sheet_rect.bottom() - band_y - 1.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.paper_canvas))
        painter.drawRoundedRect(band_rect, 4.0, 4.0)
        painter.setPen(QPen(QColor(COLORS.paper_border), 1.0))
        painter.drawLine(QPointF(sheet_rect.x() + 6.0, band_y), QPointF(sheet_rect.right() - 6.0, band_y))

        name_h = 20.0 if self._mode is CardDisplayMode.EXPANDED else 18.0
        prof_h = 16.0 if self._mode is CardDisplayMode.EXPANDED else 14.5
        name_rect = QRectF(w * 0.07, band_y + 3.0, w * 0.86, name_h)
        self._draw_elided_text(
            painter,
            name_rect,
            data.name,
            self._ui_font(13 if self._mode is CardDisplayMode.EXPANDED else 12, bold=True),
            QColor(COLORS.ink_primary),
        )

        prof_rect = QRectF(w * 0.07, name_rect.bottom() + 0.5, w * 0.86, prof_h)
        self._draw_elided_text(
            painter,
            prof_rect,
            data.profession,
            self._ui_font(11 if self._mode is CardDisplayMode.EXPANDED else 10, bold=False),
            QColor(COLORS.ink_secondary),
        )

        verdict_h = 22.0 if self._mode is CardDisplayMode.EXPANDED else 20.0
        verdict_y = h - verdict_h - (7.5 if self._mode is CardDisplayMode.EXPANDED else 6.5)
        verdict_rect = QRectF(w * 0.09, verdict_y, w * 0.82, verdict_h)
        self._paint_verdict_pill(painter, verdict_rect, is_criminal=is_criminal, compact=False)

    def _paint_revealed_compact_content(
        self,
        painter: QPainter,
        rect: QRectF,
        data: PublicCharacterView,
        *,
        is_criminal: bool,
    ) -> None:
        w, h = rect.width(), rect.height()
        pad_x = 6.5

        if data.has_public_clue:
            clue_badge = QRectF(w - 39.0, 6.0, 33.0, 16.0)
            painter.setPen(QPen(QColor(COLORS.brass_ink), 1.0))
            painter.setBrush(QColor(COLORS.paper_linen))
            painter.drawRoundedRect(clue_badge, 3.5, 3.5)
            self._draw_elided_text(
                painter,
                clue_badge,
                "CLUE",
                self._ui_font(8, bold=True),
                QColor(COLORS.brass_ink),
            )

        p_rect = self._compute_portrait_frame_rect(rect)
        scrim_y = p_rect.bottom() + 2.5
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS.paper_canvas))
        painter.drawRoundedRect(QRectF(5.5, scrim_y, w - 11.0, h - scrim_y - 5.5), 4.0, 4.0)
        painter.setPen(QPen(QColor(COLORS.paper_border), 1.0))
        painter.drawLine(QPointF(8.0, scrim_y), QPointF(w - 8.0, scrim_y))

        name_rect = QRectF(pad_x, scrim_y + 2.5, w - 2 * pad_x, 16.5)
        self._draw_elided_text(
            painter,
            name_rect,
            data.name,
            self._ui_font(11, bold=True),
            QColor(COLORS.ink_primary),
        )

        prof_rect = QRectF(pad_x, name_rect.bottom() + 0.5, w - 2 * pad_x, 14.0)
        self._draw_elided_text(
            painter,
            prof_rect,
            data.profession,
            self._ui_font(10, bold=False),
            QColor(COLORS.ink_secondary),
        )

        verdict_rect = QRectF(pad_x + 0.5, h - 26.5, w - 2 * (pad_x + 0.5), 20.0)
        self._paint_verdict_pill(painter, verdict_rect, is_criminal=is_criminal, compact=True)

    def _paint_verdict_pill(
        self,
        painter: QPainter,
        rect: QRectF,
        *,
        is_criminal: bool,
        compact: bool,
    ) -> None:
        bg = QColor(COLORS.criminal_verdict if is_criminal else COLORS.innocent_verdict)
        fg = QColor(COLORS.text_on_crimson if is_criminal else COLORS.text_on_innocent)
        border = QColor(COLORS.criminal_text if is_criminal else COLORS.innocent_text)

        painter.setPen(QPen(border, 1.2))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 4.0, 4.0)

        icon_size = min(rect.height() - 6.0, 11.0 if compact else 12.0)
        icon_x = rect.x() + 5.0
        icon_y = rect.center().y() - icon_size / 2.0
        icon_rect = QRectF(icon_x, icon_y, icon_size, icon_size)

        painter.save()
        if is_criminal:
            tri = QPolygonF(
                [
                    QPointF(icon_rect.center().x(), icon_rect.top()),
                    QPointF(icon_rect.right(), icon_rect.bottom()),
                    QPointF(icon_rect.left(), icon_rect.bottom()),
                ]
            )
            painter.setPen(QPen(fg, 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(tri)
        else:
            painter.setPen(QPen(fg, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(
                QPointF(icon_rect.left(), icon_rect.center().y()),
                QPointF(icon_rect.left() + icon_size * 0.38, icon_rect.bottom() - 1.0),
            )
            painter.drawLine(
                QPointF(icon_rect.left() + icon_size * 0.38, icon_rect.bottom() - 1.0),
                QPointF(icon_rect.right(), icon_rect.top() + 1.0),
            )
        painter.restore()

        label = "CRIMINAL" if is_criminal else "INNOCENT"
        text_rect = QRectF(icon_rect.right() + 3.0, rect.y(), rect.right() - icon_rect.right() - 5.0, rect.height())
        self._draw_elided_text(
            painter,
            text_rect,
            label,
            self._ui_font(9 if compact else (10 if self._mode is CardDisplayMode.EXPANDED else 9), bold=True),
            fg,
            align=Qt.AlignmentFlag.AlignCenter,
        )

    def _paint_cell_id_badge(
        self,
        painter: QPainter,
        rect: QRectF,
        cell_id: str,
        *,
        compact: bool,
        on_cream: bool = False,
    ) -> None:
        bw = 29.0 if compact else 35.0
        bh = 17.0 if compact else 20.0
        offset = 7.0 if on_cream else 6.0
        badge = QRectF(rect.x() + offset, rect.y() + offset, bw, bh)
        if on_cream:
            painter.setPen(QPen(QColor(COLORS.ink_primary), 1.1))
            painter.setBrush(QColor(COLORS.paper_linen))
            text_color = QColor(COLORS.ink_primary)
        else:
            painter.setPen(QPen(QColor(COLORS.accent_primary), 1.1))
            painter.setBrush(QColor(16, 27, 48, 232))
            text_color = QColor(COLORS.accent_primary)
        painter.drawRoundedRect(badge, 3.5, 3.5)
        font = QFont(TYPOGRAPHY.font_family_mono[0])
        font.setPixelSize(10 if compact else 11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, cell_id)

    @staticmethod
    def _paint_corner_brackets(
        painter: QPainter,
        rect: QRectF,
        color: QColor,
        *,
        seg: float = 12.0,
        thickness: float = 3.0,
    ) -> None:
        pen = QPen(color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        painter.drawLine(QPointF(l, t + seg), QPointF(l, t))
        painter.drawLine(QPointF(l, t), QPointF(l + seg, t))
        painter.drawLine(QPointF(r - seg, t), QPointF(r, t))
        painter.drawLine(QPointF(r, t), QPointF(r, t + seg))
        painter.drawLine(QPointF(l, b - seg), QPointF(l, b))
        painter.drawLine(QPointF(l, b), QPointF(l + seg, b))
        painter.drawLine(QPointF(r - seg, b), QPointF(r, b))
        painter.drawLine(QPointF(r, b), QPointF(r, b - seg))

    @staticmethod
    def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        return QColor(
            int(round(c1.red() + (c2.red() - c1.red()) * t)),
            int(round(c1.green() + (c2.green() - c1.green()) * t)),
            int(round(c1.blue() + (c2.blue() - c1.blue()) * t)),
            int(round(c1.alpha() + (c2.alpha() - c1.alpha()) * t)),
        )

    @staticmethod
    def _ui_font(pixel_size: int, *, bold: bool) -> QFont:
        font = QFont(TYPOGRAPHY.font_family_ui[0])
        font.setPixelSize(pixel_size)
        font.setBold(bold)
        return font

    @staticmethod
    def _draw_elided_text(
        painter: QPainter,
        rect: QRectF,
        text: str,
        font: QFont,
        color: QColor,
        *,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ) -> None:
        painter.setFont(font)
        painter.setPen(color)
        fm = QFontMetricsF(font)
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, max(4.0, rect.width()))
        painter.drawText(rect, align, elided)

    @staticmethod
    def _compute_initials(name: str) -> str:
        parts = [p for p in name.strip().split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
