"""Dynamic N×N GameBoard built on QGraphicsView & QGraphicsScene (Phase 3–5).

Canonical file preserved from ``docs/STAGE2_SHARED_BASELINE.md`` §5.
Supports 3×3 (EXPANDED), 4×4 (STANDARD), and 5×5 (COMPACT) boards constructed
strictly from public snapshots without hardcoding cell counts, without reading
puzzle JSON files, and without running any SAT/DPLL/Controller logic.

Phase 5 adds ``MotionCoordinator`` integration for:
    - Physical 3D projective card reveal flips (``reveal_card`` / ``cancel_animations``)
    - Luminous cyan clue highlight with pulse & smooth fade-out
    - Reduced-motion support with queued completion handshake
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPauseAnimation,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
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
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QSizePolicy,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.animations.motion_coordinator import MotionCoordinator
from src.gui.animations.motion_tokens import (
    EASE_AWAY,
    EASE_OUT,
    EASE_SOFT,
    SCALE_ENTRANCE,
    SPRING_ENTRANCE,
    STAGGER_STACK_MS,
    build_easing,
)
from src.gui.asset_registry import AssetId
from src.gui.assets.portrait_registry import PortraitRegistry, default_portrait_registry
from src.gui.clue_highlighter import ClueHighlighter
from src.gui.components.character_card import (
    CARD_DIMENSIONS_BY_MODE,
    CardDisplayMode,
    CharacterCard,
)
from src.gui.resources.pixmap_loader import PixmapLoader, default_pixmap_loader
from src.gui.styles.tokens import COLORS, GEOMETRY, TYPOGRAPHY
from src.gui.view_models import (
    PublicBoardSnapshot,
    PublicCharacterView,
    normalize_board_snapshot,
    normalize_character_view,
)

logger = logging.getLogger(__name__)

_MODE_BY_GRID_SIZE: dict[int, CardDisplayMode] = {
    3: CardDisplayMode.EXPANDED,
    4: CardDisplayMode.STANDARD,
    5: CardDisplayMode.COMPACT,
}

_GAP_BY_MODE: dict[CardDisplayMode, int] = {
    CardDisplayMode.EXPANDED: 14,
    CardDisplayMode.STANDARD: 10,
    CardDisplayMode.COMPACT: 8,
}

_GAP_X_BY_MODE: dict[CardDisplayMode, int] = {
    CardDisplayMode.EXPANDED: 18,
    CardDisplayMode.STANDARD: 14,
    CardDisplayMode.COMPACT: 12,
}

_GAP_Y_BY_MODE: dict[CardDisplayMode, int] = {
    CardDisplayMode.EXPANDED: 12,
    CardDisplayMode.STANDARD: 8,
    CardDisplayMode.COMPACT: 6,
}

_MIN_SCALE_BY_MODE: dict[CardDisplayMode, float] = {
    CardDisplayMode.EXPANDED: 0.72,
    CardDisplayMode.STANDARD: 0.66,
    CardDisplayMode.COMPACT: 0.66,
}


class _RelationBadgeItem(QGraphicsItem):
    """Floating non-interactive detective relation pill placed at the midpoint of a 3D cord."""

    def __init__(self, text: str, bg_hex: str, center: QPointF) -> None:
        super().__init__()
        self._text = text
        self._bg = QColor(bg_hex)
        self._font = QFont(TYPOGRAPHY.font_family_ui[0])
        self._font.setPixelSize(10)
        self._font.setBold(True)
        fm = QFontMetricsF(self._font)
        w = max(62.0, fm.horizontalAdvance(text) + 18.0)
        h = 22.0
        self._rect = QRectF(-w * 0.5, -h * 0.5, w, h)
        self.setPos(center)
        self.setZValue(35)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._rect.adjusted(-4.0, -4.0, 4.0, 6.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802, ARG002
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self._rect.height() * 0.5
        # Soft drop shadow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 16, 28, 130))
        painter.drawRoundedRect(self._rect.translated(0.0, 2.2), r, r)
        # Crisp pill fill + ivory outline
        painter.setBrush(self._bg)
        painter.setPen(QPen(QColor(252, 248, 240, 248), 1.6))
        painter.drawRoundedRect(self._rect, r, r)
        painter.setFont(self._font)
        painter.setPen(QColor(255, 252, 246))
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.restore()


class GameBoard(QGraphicsView):
    """Interactive PySide6 board hosting dynamic N×N ``CharacterCard`` items."""

    card_selected = Signal(str)               # Emits cell_id on user click or keyboard selection
    background_clicked = Signal()
    animation_finished = Signal(str, object)  # (cell_id, token) — ONLY on successful flip finish
    animation_cancelled = Signal(str, object) # (cell_id, token) — ONLY on explicit cancel

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        portrait_registry: Optional[PortraitRegistry] = None,
        motion_config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveGameBoard")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_loader = pixmap_loader or default_pixmap_loader()
        self._portrait_registry = portrait_registry or default_portrait_registry()
        self._motion_coordinator = MotionCoordinator(config=motion_config, parent=self)
        self._highlighter = ClueHighlighter(
            glow_controller=self._motion_coordinator.glow_controller,
            config=motion_config,
            parent=self,
        )
        self._motion_coordinator.animation_finished.connect(self.animation_finished.emit)
        self._motion_coordinator.animation_cancelled.connect(self.animation_cancelled.emit)

        # Shared pre-scaled artwork cache keyed by (AssetId, width, height)
        self._scaled_art_cache: dict[tuple[AssetId, int, int], QPixmap] = {}

        # Current public render state (cache only — never authoritative game state)
        self._snapshot: Optional[PublicBoardSnapshot] = None
        self._cards_by_id: dict[str, CharacterCard] = {}
        self._cards_by_coord: dict[tuple[int, int], CharacterCard] = {}
        self._selected_cell_id: Optional[str] = None
        self._interactive: bool = True
        self._display_mode: CardDisplayMode = CardDisplayMode.STANDARD
        self._current_scale: float = 1.0
        self._board_transition = None
        self._hint_flow = None
        self._hint_particles: list[QGraphicsItem] = []
        self._evidence_threads: list[QGraphicsItem] = []

        # Living 3D Detective Office & Archival Tabletop Ambient Engine
        self._ambient_phase: float = 0.0
        self._ripple_progress: float = 1.0  # 0.0 -> 1.0 expanding deduction wave on desk mat
        self._cursor_norm: QPointF = QPointF(0.0, 0.0)  # [-1..1, -1..1] for 3D background parallax
        self._cursor_vp: Optional[QPointF] = None
        self._bg_cached_pm: Optional[QPixmap] = None
        self._bg_cached_size: QSize = QSize(0, 0)
        self._mat_tex_cached: Optional[QPixmap] = None
        self._mat_tex_size: QSize = QSize(0, 0)

        # 40 deterministic 3D floating golden dust motes, bokeh & 4-point starlight sparkles
        # tuple: (x0, y0, depth, speed, phase, radius, kind) where kind: 0=warm gold, 1=moon pearl, 2=star sparkle
        base_motes = tuple(
            (
                ((i * 37 + 11) % 100) / 100.0,
                ((i * 53 + 23) % 100) / 100.0,
                0.32 + 0.68 * ((i % 5) / 4.0),
                0.48 + 0.72 * ((i % 4) / 3.0),
                (i * 1.29) % (2.0 * math.pi),
                1.3 + 2.5 * ((i % 3) / 2.0),
                2 if (i % 3 == 0) else (0 if (i % 3 == 1) else 1),
            )
            for i in range(36)
        )
        # 18 extra shimmering fireflies & star glints framed in the visible left lamp & right moonlit margins
        margin_sparkles = tuple(
            (
                (0.025 + ((j * 19) % 14) * 0.011) if (j % 2 == 0) else (0.835 + ((j * 17) % 15) * 0.010),
                0.06 + ((j * 29 + 7) % 86) / 100.0,
                0.55 + 0.45 * ((j % 4) / 3.0),
                0.58 + 0.62 * ((j % 3) / 2.0),
                (j * 1.63) % (2.0 * math.pi),
                1.5 + 2.2 * ((j % 3) / 2.0),
                2 if (j % 2 == 1) else 0,
            )
            for j in range(18)
        )
        self._dust_motes: tuple[tuple[float, float, float, float, float, float, int], ...] = (
            base_motes + margin_sparkles
        )
        # Twinkling skyline windows & tower lights on A05_board_mat_noir.png (x_ratio, y_ratio, speed, phase, radius)
        self._skyline_lights: tuple[tuple[float, float, float, float, float], ...] = (
            (0.974, 0.365, 1.9, 0.2, 6.2),   # Eiffel-style spire beacon tip
            (0.974, 0.445, 1.4, 1.1, 4.5),   # Upper spire lantern
            (0.972, 0.535, 1.2, 2.3, 4.2),   # Mid tower glow
            (0.880, 0.675, 1.7, 0.8, 4.0),   # Mid building window L
            (0.900, 0.675, 1.3, 2.7, 4.0),   # Mid building window R
            (0.942, 0.655, 1.6, 1.5, 4.4),   # Right tower upper window
            (0.968, 0.655, 2.0, 3.1, 4.2),   # Far right upper window
            (0.835, 0.725, 1.5, 0.4, 3.8),   # Lower-left skyline window
            (0.872, 0.765, 1.8, 2.1, 4.2),   # Warm cafe window
            (0.916, 0.755, 1.1, 3.6, 4.0),   # Mid-lower glowing window
            (0.808, 0.808, 1.6, 1.8, 4.2),   # Left bottom golden window
            (0.832, 0.808, 1.4, 0.9, 4.0),   # Left bottom pair window
            (0.902, 0.818, 1.9, 2.9, 3.8),   # Lower right window
            (0.118, 0.330, 1.2, 1.4, 5.2),   # Distant window light outside left blinds
        )

        self._ambient_timer = QTimer(self)
        self._ambient_timer.setInterval(33)  # ~30 FPS silky low-CPU ambient loop
        self._ambient_timer.timeout.connect(self._on_ambient_tick)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        # View configuration: transparent over Gameplay A05 backdrop, smooth rendering
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QGraphicsView#GriductiveGameBoard { background: transparent; border: none; }")
        self.viewport().setAutoFillBackground(False)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(360, 300)

    # ------------------------------------------------------------------
    # Read-Only Properties
    # ------------------------------------------------------------------

    @property
    def snapshot(self) -> Optional[PublicBoardSnapshot]:
        return self._snapshot

    @property
    def grid_size(self) -> int:
        return self._snapshot.grid_size if self._snapshot is not None else 0

    @property
    def puzzle_id(self) -> str:
        return self._snapshot.puzzle_id if self._snapshot is not None else ""

    @property
    def display_mode(self) -> CardDisplayMode:
        return self._display_mode

    @property
    def card_count(self) -> int:
        return len(self._cards_by_id)

    @property
    def cards_by_id(self) -> Mapping[str, CharacterCard]:
        return MappingProxyType(self._cards_by_id)

    @property
    def selected_cell_id(self) -> Optional[str]:
        return self._selected_cell_id

    @property
    def highlighted_cell_ids(self) -> tuple[str, ...]:
        return self._highlighter.active_cell_ids

    @property
    def current_scale(self) -> float:
        return self._current_scale

    @property
    def is_interactive(self) -> bool:
        return self._interactive

    @property
    def motion_coordinator(self) -> MotionCoordinator:
        return self._motion_coordinator

    @property
    def is_animating(self) -> bool:
        return self._motion_coordinator.is_animating

    @property
    def reduced_motion(self) -> bool:
        return self._motion_coordinator.reduced_motion

    @property
    def portrait_registry(self) -> PortraitRegistry:
        return self._portrait_registry

    # ------------------------------------------------------------------
    # Public Controller / ViewPort API
    # ------------------------------------------------------------------

    def set_board(self, snapshot: Any) -> None:
        """Validate and render a complete public N×N board snapshot.

        Cancels any in-flight card flip cleanly before synchronizing committed
        cards. Preserves existing ``CharacterCard`` items in-place when
        topology matches; rebuilds the scene when grid size or character set
        changes.
        """
        normalized = normalize_board_snapshot(snapshot)
        new_mode = _MODE_BY_GRID_SIZE[normalized.grid_size]

        # Ensure no stale animation can overwrite newly committed snapshot
        self._motion_coordinator.cancel_active_animation(revert_to_original=False)

        same_topology = (
            self._snapshot is not None
            and self._snapshot.grid_size == normalized.grid_size
            and set(self._cards_by_id.keys()) == {c.cell_id for c in normalized.characters}
            and all(
                self._cards_by_id[c.cell_id].public_data.row == c.row
                and self._cards_by_id[c.cell_id].public_data.col == c.col
                for c in normalized.characters
            )
        )

        self._snapshot = normalized
        self._display_mode = new_mode

        if same_topology:
            for ch in normalized.characters:
                card = self._cards_by_id[ch.cell_id]
                prev = card.public_data
                if prev != ch:
                    card.set_public_data(ch)
                if not card.has_portrait or prev.name != ch.name or prev.profession != ch.profession:
                    self._sync_card_portrait(card, normalized.puzzle_id, ch, new_mode)
            return

        self._rebuild_scene(normalized, new_mode)

    def update_character(self, public_character: Any) -> bool:
        """Update one character card in-place from a public DTO (emits no signal)."""
        char = normalize_character_view(public_character)
        card = self._cards_by_id.get(char.cell_id)
        if card is None:
            logger.warning("Ignoring update_character for unknown cell_id %r", char.cell_id)
            return False
        prev = card.public_data
        card.set_public_data(char)
        if (prev.name != char.name or prev.profession != char.profession) and self._snapshot is not None:
            self._sync_card_portrait(card, self._snapshot.puzzle_id, char, self._display_mode)
        return True

    def reveal_card(
        self,
        cell_id: str,
        public_data: Any,
        token: object = None,
    ) -> bool:
        """Start an authorized physical 3D reveal flip for one card (ViewPort §D)."""
        return self._motion_coordinator.animate_card_reveal(
            self._cards_by_id,
            cell_id,
            public_data,
            token=token,
        )

    def animate_card_reveal(
        self,
        cell_id: str,
        public_character: Any,
        token: object = None,
    ) -> bool:
        """Alias of ``reveal_card`` matching Phase 5 §9 naming."""
        return self.reveal_card(cell_id, public_character, token=token)

    def cancel_animations(self, *, revert_to_original: bool = True) -> bool:
        """Stop active card flip animations safely without emitting ``animation_finished``."""
        return self._motion_coordinator.cancel_active_animation(
            revert_to_original=revert_to_original
        )

    def cancel_active_animation(self, *, revert_to_original: bool = True) -> bool:
        """Alias of ``cancel_animations`` matching Phase 5 §9 naming."""
        return self.cancel_animations(revert_to_original=revert_to_original)

    def set_reduced_motion(self, enabled: bool) -> None:
        """Toggle reduced-motion mode across board coordinator, highlighter & cards."""
        flag = bool(enabled)
        if flag:
            self._clear_evidence_threads()
            self._ambient_timer.stop()
            self._ripple_progress = 1.0
        elif self.isVisible():
            self._ambient_timer.start()
        self._motion_coordinator.set_reduced_motion(flag)
        for card in self._cards_by_id.values():
            card.set_reduced_motion(flag)
        self.viewport().update()

    def set_animation_enabled(self, enabled: bool) -> None:
        """Inverse alias of ``set_reduced_motion`` (Phase 5 §9 API)."""
        self.set_reduced_motion(not bool(enabled))

    def set_selection(self, cell_id: Optional[str]) -> bool:
        """Programmatically set selected cell (does NOT emit ``card_selected``)."""
        if cell_id is None:
            self.clear_selection()
            return True
        if cell_id not in self._cards_by_id:
            logger.warning("Ignoring programmatic selection for unknown cell_id %r", cell_id)
            return False

        if self._selected_cell_id is not None and self._selected_cell_id in self._cards_by_id:
            self._cards_by_id[self._selected_cell_id].set_selected(False)
        self._selected_cell_id = cell_id
        self._cards_by_id[cell_id].set_selected(True)
        return True

    def set_selected_card(self, cell_id: Optional[str]) -> bool:
        return self.set_selection(cell_id)

    def clear_selection(self) -> None:
        """Clear selected state programmatically (does NOT emit ``card_selected``)."""
        if self._selected_cell_id is not None and self._selected_cell_id in self._cards_by_id:
            self._cards_by_id[self._selected_cell_id].set_selected(False)
        self._selected_cell_id = None

    def highlight_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        """Apply luminous cyan highlight overlay to the specified cell IDs."""
        self._clear_evidence_threads()
        valid = self._highlighter.apply_highlight(self._cards_by_id, cell_ids)
        active = set(valid)
        for cid, card in self._cards_by_id.items():
            card.set_focus_context(bool(active) and cid not in active, "primary")
        return valid

    def focus_evidence(
        self,
        primary: Iterable[str],
        references: Iterable[str] = (),
        *,
        source_owners: Iterable[str] = (),
        target_cell_id: Optional[str] = None,
    ) -> tuple[str, ...]:
        primary_seq = [cid for cid in dict.fromkeys(primary) if cid in self._cards_by_id]
        ref_seq = [cid for cid in dict.fromkeys(references) if cid in self._cards_by_id]
        owner_set = {cid for cid in source_owners if cid in self._cards_by_id}
        main = set(primary_seq)
        targets = tuple(dict.fromkeys((*primary_seq, *ref_seq, *owner_set)))
        valid = self._highlighter.apply_highlight(self._cards_by_id, targets)
        active = set(valid)
        for cid, card in self._cards_by_id.items():
            if cid not in active:
                card.set_focus_context(bool(active), "reference", "")
            elif target_cell_id and cid == target_cell_id:
                card.set_focus_context(False, "primary", "MỤC TIÊU")
            elif cid in owner_set:
                card.set_focus_context(False, "source", "NGUỒN")
            elif cid in main:
                card.set_focus_context(False, "primary", "CĂN CỨ" if target_cell_id else "CHÍNH")
            else:
                card.set_focus_context(False, "secondary", "CĂN CỨ")
        self._draw_3d_evidence_threads(
            primary_seq,
            ref_seq,
            hub_override=target_cell_id,
        )
        if not self.reduced_motion:
            self._ripple_progress = 0.0
        return valid

    def focus_clue_relation(
        self,
        *,
        owner_id: Optional[str],
        primary_cells: Iterable[str],
        secondary_cells: Iterable[str] = (),
        clue_type: str = "",
        relation_label: str = "",
    ) -> tuple[str, ...]:
        """Highlight a selected public clue with clear Source / Primary / Secondary role tags & 3D connectors."""
        prim_seq = [cid for cid in dict.fromkeys(primary_cells) if cid in self._cards_by_id]
        sec_seq = [
            cid for cid in dict.fromkeys(secondary_cells)
            if cid in self._cards_by_id and cid not in prim_seq
        ]
        owner = owner_id if (owner_id and owner_id in self._cards_by_id) else None
        all_targets = tuple(dict.fromkeys(([owner] if owner else []) + prim_seq + sec_seq))
        valid = self._highlighter.apply_highlight(self._cards_by_id, all_targets)
        active = set(valid)

        ctype = clue_type.strip().upper()
        is_comparative = ctype in {"SAME", "DIFFERENT", "COUNT_COMPARE"} and bool(sec_seq)
        prim_badge = "CHÍNH" if is_comparative else ("MỤC TIÊU" if ctype == "FACT" else "VÙNG XÉT")

        for cid, card in self._cards_by_id.items():
            if cid not in active:
                card.set_focus_context(bool(active), "reference", "")
            elif owner and cid == owner and cid in prim_seq:
                card.set_focus_context(False, "source", "NGUỒN · CHÍNH")
            elif owner and cid == owner:
                card.set_focus_context(False, "source", "NGUỒN")
            elif cid in prim_seq:
                card.set_focus_context(False, "primary", prim_badge)
            else:
                card.set_focus_context(False, "secondary", "ĐỐI CHIẾU")

        self._draw_semantic_clue_connectors(
            owner_id=owner,
            primary_ids=prim_seq,
            secondary_ids=sec_seq,
            clue_type=ctype,
            relation_label=relation_label,
        )
        if not self.reduced_motion:
            self._ripple_progress = 0.0
        return valid

    def set_highlighted_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        """Alias of ``highlight_cells`` matching Phase 5 §6.3."""
        return self.highlight_cells(cell_ids)

    def clear_highlights(self) -> None:
        """Fade out / clear all visual highlight overlays."""
        self._clear_evidence_threads()
        self._highlighter.clear_highlight(self._cards_by_id)
        for card in self._cards_by_id.values():
            card.set_focus_context(False, "reference", "")

    def _clear_evidence_threads(self) -> None:
        for item in self._evidence_threads:
            if item.scene() is self._scene:
                self._scene.removeItem(item)
        self._evidence_threads.clear()

    def _card_pin_point(self, cell_id: str) -> Optional[QPointF]:
        card = self._cards_by_id.get(cell_id)
        if card is None:
            return None
        r = card.card_rect()
        # Anchored just below the floating top-edge role pill so pin & text never collide
        return card.pos() + QPointF(r.width() * 0.5, 8.5)

    def _add_thread_item(self, item: QGraphicsItem) -> None:
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._scene.addItem(item)
        self._evidence_threads.append(item)

    def _add_pushpin(self, pt: QPointF, color_hex: str) -> None:
        pin = QGraphicsEllipseItem(-3.3, -3.3, 6.6, 6.6)
        pin.setPos(pt)
        pin.setBrush(QBrush(QColor(color_hex)))
        pin.setPen(QPen(QColor(252, 248, 240), 1.5))
        pin.setZValue(32)
        self._add_thread_item(pin)

    def _add_arrowhead(self, tip: QPointF, ctrl: QPointF, color: QColor) -> None:
        dx = tip.x() - ctrl.x()
        dy = tip.y() - ctrl.y()
        length = math.hypot(dx, dy)
        if length < 1e-3:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        size = 9.0
        half_w = 4.6
        p1 = tip
        p2 = QPointF(tip.x() - ux * size + px * half_w, tip.y() - uy * size + py * half_w)
        p3 = QPointF(tip.x() - ux * size - px * half_w, tip.y() - uy * size - py * half_w)
        head = QGraphicsPolygonItem(QPolygonF([p1, p2, p3]))
        head.setBrush(QBrush(color))
        head.setPen(QPen(QColor(252, 248, 240), 1.0))
        head.setZValue(31)
        self._add_thread_item(head)

    def _add_curved_connector(
        self,
        p0: QPointF,
        p2: QPointF,
        ctrl: QPointF,
        *,
        core_color: QColor,
        dashed: bool = False,
        arrow: bool = False,
        core_width: float = 2.4,
    ) -> QPointF:
        """Draw a high-contrast elevated 3D Bezier cord (drop shadow + ivory halo + rich core)."""
        # 1. Soft tabletop drop shadow
        sh_path = QPainterPath(p0 + QPointF(1.5, 5.0))
        sh_path.quadTo(ctrl + QPointF(2.5, 9.0), p2 + QPointF(1.5, 5.0))
        sh_item = QGraphicsPathItem(sh_path)
        sh_item.setPen(
            QPen(QColor(14, 22, 36, 52), core_width + 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        sh_item.setZValue(26)
        self._add_thread_item(sh_item)

        # 2. High-contrast ivory outer outline (ensures visibility on both cream parchment & dark cards)
        arc_path = QPainterPath(p0)
        arc_path.quadTo(ctrl, p2)
        halo_item = QGraphicsPathItem(arc_path)
        halo_item.setPen(
            QPen(QColor(252, 248, 240, 225), core_width + 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        halo_item.setZValue(28)
        self._add_thread_item(halo_item)

        # 3. Crisp semantic core cord
        core_pen = QPen(
            core_color,
            core_width,
            Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
        )
        if dashed:
            core_pen.setDashPattern([6.0, 4.0])
        core_item = QGraphicsPathItem(arc_path)
        core_item.setPen(core_pen)
        core_item.setZValue(29)
        self._add_thread_item(core_item)

        if arrow:
            self._add_arrowhead(p2, ctrl, core_color)

        # Evaluate Bezier midpoint (t = 0.5) for relation badge placement
        mid = QPointF(
            0.25 * p0.x() + 0.5 * ctrl.x() + 0.25 * p2.x(),
            0.25 * p0.y() + 0.5 * ctrl.y() + 0.25 * p2.y(),
        )
        return mid

    def _draw_semantic_clue_connectors(
        self,
        *,
        owner_id: Optional[str],
        primary_ids: list[str],
        secondary_ids: list[str],
        clue_type: str,
        relation_label: str,
    ) -> None:
        """Render clear semantic detective connectors tailored to the clue type."""
        self._clear_evidence_threads()
        if self.reduced_motion:
            return

        owner_pt = self._card_pin_point(owner_id) if owner_id else None

        # CASE A — Comparative pair/groups (SAME / DIFFERENT / COUNT_COMPARE)
        if clue_type in {"SAME", "DIFFERENT", "COUNT_COMPARE"} and primary_ids and secondary_ids:
            p0 = self._card_pin_point(primary_ids[0])
            p2 = self._card_pin_point(secondary_ids[0])
            if p0 is not None and p2 is not None:
                # Curve intelligently away from intervening card faces!
                dx = abs(p2.x() - p0.x())
                dy = abs(p2.y() - p0.y())
                mid_x = (p0.x() + p2.x()) * 0.5
                mid_y = (p0.y() + p2.y()) * 0.5
                if dx < 28.0:
                    # Same column (e.g. B5 <-> B3): arch cleanly into the inter-column gutter
                    side = 1.0 if (owner_pt is not None and owner_pt.x() >= mid_x) else -1.0
                    ctrl = QPointF(mid_x + side * 68.0, mid_y)
                else:
                    ctrl = QPointF(mid_x, mid_y - max(38.0, min(66.0, dy * 0.25 + 38.0)))

                cord_hex = (
                    "#1E706E" if clue_type == "SAME"
                    else ("#A03535" if clue_type == "DIFFERENT" else "#223248")
                )
                mid_pt = self._add_curved_connector(
                    p0, p2, ctrl,
                    core_color=QColor(cord_hex),
                    dashed=False,
                    arrow=False,
                    core_width=2.8,
                )
                self._add_pushpin(p0, "#2B6BA0")
                self._add_pushpin(p2, "#A14B33")

                # Dashed brass pointer from Clue Source (owner) -> edge of midpoint relation badge
                if owner_pt is not None and owner_id not in (primary_ids[0], secondary_ids[0]):
                    o_ctrl = QPointF(
                        (owner_pt.x() + mid_pt.x()) * 0.5,
                        min(owner_pt.y(), mid_pt.y()) - 28.0,
                    )
                    # Stop arrowhead cleanly at the outer rim of the relation pill so it's 100% visible
                    tdx = mid_pt.x() - o_ctrl.x()
                    tdy = mid_pt.y() - o_ctrl.y()
                    tlen = math.hypot(tdx, tdy)
                    if tlen > 26.0:
                        ux, uy = tdx / tlen, tdy / tlen
                        # Elliptical pullback matching pill aspect (~36px wide, ~13px tall)
                        pull = 1.0 / math.hypot(ux / 34.0, uy / 13.0)
                        target_pt = QPointF(mid_pt.x() - ux * pull, mid_pt.y() - uy * pull)
                    else:
                        target_pt = mid_pt
                    self._add_curved_connector(
                        owner_pt,
                        target_pt,
                        o_ctrl,
                        core_color=QColor("#B97E24"),
                        dashed=True,
                        arrow=True,
                        core_width=2.2,
                    )
                    self._add_pushpin(owner_pt, "#C48728")

                badge_txt = relation_label or (
                    "= CÙNG PHE" if clue_type == "SAME"
                    else ("≠ KHÁC PHE" if clue_type == "DIFFERENT" else "SO SÁNH")
                )
                self._add_thread_item(_RelationBadgeItem(badge_txt, cord_hex, mid_pt))
            return

        # CASE B — Group/Region clues (EXACTLY / AT_LEAST / AT_MOST / PARITY) with >= 2 target cards
        all_group = list(dict.fromkeys(primary_ids + secondary_ids))
        if len(all_group) >= 2 and clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", ""}:
            cards = [self._cards_by_id[cid] for cid in all_group if cid in self._cards_by_id]
            rows = {c.public_data.row for c in cards}
            cols = {c.public_data.col for c in cards}
            # Contiguous single row or single column -> clean dashed region frame box (zero spaghetti!)
            if len(rows) == 1 or len(cols) == 1:
                min_x = min(c.pos().x() for c in cards)
                min_y = min(c.pos().y() for c in cards)
                max_x = max(c.pos().x() + c.card_rect().width() for c in cards)
                max_y = max(c.pos().y() + c.card_rect().height() for c in cards)
                box = QRectF(min_x - 8.0, min_y - 16.0, (max_x - min_x) + 16.0, (max_y - min_y) + 24.0)

                frame_path = QPainterPath()
                frame_path.addRoundedRect(box, 12.0, 12.0)

                halo = QGraphicsPathItem(frame_path)
                halo.setPen(QPen(QColor(252, 248, 240, 215), 4.6))
                halo.setBrush(QColor(43, 107, 160, 22))
                halo.setZValue(26)
                self._add_thread_item(halo)

                pen = QPen(QColor("#2B6BA0"), 2.4, Qt.PenStyle.DashLine)
                pen.setDashPattern([7.0, 4.0])
                frame_item = QGraphicsPathItem(frame_path)
                frame_item.setPen(pen)
                frame_item.setZValue(27)
                self._add_thread_item(frame_item)

                tag_pt = QPointF(box.center().x(), box.top() - 1.0)
                if owner_pt is not None and owner_id not in all_group:
                    o_ctrl = QPointF((owner_pt.x() + tag_pt.x()) * 0.5, min(owner_pt.y(), tag_pt.y()) - 32.0)
                    self._add_curved_connector(
                        owner_pt, tag_pt, o_ctrl,
                        core_color=QColor("#B97E24"),
                        dashed=True,
                        arrow=True,
                        core_width=2.2,
                    )
                    self._add_pushpin(owner_pt, "#C48728")

                if relation_label:
                    self._add_thread_item(_RelationBadgeItem(relation_label, "#2B6BA0", tag_pt))
                return

        # CASE C — Direct FACT or scattered targets: clean dashed brass arrows from source to each target
        if owner_pt is not None:
            targets = [cid for cid in all_group if cid != owner_id][:6]
            if targets:
                self._add_pushpin(owner_pt, "#C48728")
            for idx, cid in enumerate(targets):
                dst_pt = self._card_pin_point(cid)
                if dst_pt is None:
                    continue
                bend = -34.0 - (idx % 3) * 10.0
                if abs(dst_pt.x() - owner_pt.x()) < 28.0:
                    # Same-column arrow: curve gently sideways so it doesn't slice straight across faces
                    ctrl = QPointF((owner_pt.x() + dst_pt.x()) * 0.5 + 38.0, (owner_pt.y() + dst_pt.y()) * 0.5)
                else:
                    ctrl = QPointF((owner_pt.x() + dst_pt.x()) * 0.5, (owner_pt.y() + dst_pt.y()) * 0.5 + bend)
                mid_pt = self._add_curved_connector(
                    owner_pt, dst_pt, ctrl,
                    core_color=QColor("#B97E24"),
                    dashed=(clue_type != "FACT"),
                    arrow=True,
                    core_width=2.4,
                )
                self._add_pushpin(dst_pt, "#2B6BA0")
                if clue_type == "FACT" and idx == 0 and relation_label:
                    self._add_thread_item(_RelationBadgeItem(relation_label, "#2B6BA0", mid_pt))

    def _draw_3d_evidence_threads(
        self,
        primary_ids: list[str],
        reference_ids: list[str],
        *,
        hub_override: Optional[str] = None,
    ) -> None:
        """Render high-contrast elevated 3D detective thread arcs with arrowheads to the conclusion cell."""
        self._clear_evidence_threads()
        if self.reduced_motion:
            return
        all_ordered = list(dict.fromkeys((*primary_ids, *reference_ids)))
        if len(all_ordered) < 2:
            return
        hub_id = hub_override or (primary_ids[-1] if primary_ids else all_ordered[0])
        hub_pt = self._card_pin_point(hub_id)
        if hub_pt is None:
            return
        spokes = [cid for cid in all_ordered if cid != hub_id][:6]
        if spokes:
            self._add_pushpin(hub_pt, "#2B6BA0")

        for idx, cid in enumerate(spokes):
            p0 = self._card_pin_point(cid)
            if p0 is None:
                continue
            bend = -34.0 - (idx % 3) * 10.0
            ctrl = QPointF((p0.x() + hub_pt.x()) * 0.5, (p0.y() + hub_pt.y()) * 0.5 + bend)
            self._add_curved_connector(
                p0, hub_pt, ctrl,
                core_color=QColor("#B97E24"),
                dashed=True,
                arrow=True,
                core_width=2.2,
            )
            self._add_pushpin(p0, "#C48728")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and not isinstance(item, CharacterCard):
            self.background_clicked.emit()
        super().mousePressEvent(event)

    def clear_highlight(self) -> None:
        """Alias of ``clear_highlights`` matching Phase 5 §6.3."""
        self.clear_highlights()

    def animate_hint_flow(
        self,
        source_cell_ids: Iterable[str],
        target_cell_id: str,
    ) -> bool:
        """Send luminous evidence particles from public source cards to a target."""
        target = self._cards_by_id.get(target_cell_id)
        sources = [
            self._cards_by_id[cid]
            for cid in dict.fromkeys(source_cell_ids)
            if cid in self._cards_by_id and cid != target_cell_id
        ]
        if target is None:
            return False
        if not sources:
            sources = [target]
        self._clear_hint_particles()
        if self.reduced_motion:
            target.set_glow_state(1.0, 1.0)
            return True

        target_center = target.pos() + target.card_rect().center()
        group = QParallelAnimationGroup(self)
        colors = (QColor(101, 185, 233), QColor(228, 185, 109), QColor(255, 247, 216))
        for source_index, source in enumerate(sources[:5]):
            start = source.pos() + source.card_rect().center()
            for particle_index in range(3):
                size = 5.0 + particle_index * 1.7
                particle = QGraphicsEllipseItem(-size / 2, -size / 2, size, size)
                color = QColor(colors[(source_index + particle_index) % len(colors)])
                color.setAlpha(230)
                particle.setBrush(QBrush(color))
                particle.setPen(QPen(Qt.PenStyle.NoPen))
                particle.setZValue(50)
                particle.setPos(start)
                self._scene.addItem(particle)
                self._hint_particles.append(particle)

                sequence = QSequentialAnimationGroup(group)
                sequence.addAnimation(
                    QPauseAnimation((source_index * (STAGGER_STACK_MS * 2)) + (particle_index * STAGGER_STACK_MS))
                )
                anim = QVariantAnimation(sequence)
                anim.setDuration(DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.hint_particle_duration))
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.setEasingCurve(build_easing(EASE_SOFT))
                arc = -42.0 - (particle_index * 14.0) + (source_index * 8.0)

                def move(value, item=particle, p0=start, p2=target_center, bend=arc):
                    t = float(value)
                    mid = QPointF((p0.x() + p2.x()) / 2.0, (p0.y() + p2.y()) / 2.0 + bend)
                    inv = 1.0 - t
                    point = QPointF(
                        inv * inv * p0.x() + 2 * inv * t * mid.x() + t * t * p2.x(),
                        inv * inv * p0.y() + 2 * inv * t * mid.y() + t * t * p2.y(),
                    )
                    item.setPos(point)
                    item.setOpacity(min(1.0, t * 5.0) * min(1.0, (1.0 - t) * 6.0))
                    item.setScale(0.75 + 0.85 * t)

                anim.valueChanged.connect(move)
                sequence.addAnimation(anim)
                group.addAnimation(sequence)

        def on_flow_finished(target_card=target) -> None:
            self._finish_hint_flow()
            try:
                target_card.trigger_hint_arrival_pulse()
            except RuntimeError:
                pass

        group.finished.connect(on_flow_finished)
        self._hint_flow = group
        group.start()
        return True

    def _finish_hint_flow(self) -> None:
        self._clear_hint_particles()
        self._hint_flow = None

    def _clear_hint_particles(self) -> None:
        if self._hint_flow is not None:
            self._hint_flow.stop()
        for item in self._hint_particles:
            if item.scene() is self._scene:
                self._scene.removeItem(item)
        self._hint_particles.clear()

    def animate_board_rebuild(self, snapshot: Any, finished=None) -> None:
        """Collapse the old dossier grid, rebuild it, then deal cards back in."""
        normalized = normalize_board_snapshot(snapshot)
        self._motion_coordinator.cancel_active_animation(revert_to_original=False)
        self._clear_hint_particles()
        if self._board_transition is not None:
            self._board_transition.stop()
        if self.reduced_motion or not self._cards_by_id:
            self.set_board(normalized)
            if callable(finished):
                finished()
            return

        self.set_interactive(False)
        out_group = QParallelAnimationGroup(self)
        ordered = sorted(self._cards_by_id.values(), key=lambda c: (c.public_data.row + c.public_data.col, c.public_data.row))
        collapse_ms = DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.board_collapse_duration)
        wave_ms = DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.stagger_wave_ms)
        for card in ordered:
            card.setTransformOriginPoint(card.card_rect().center())
            diag = card.public_data.row + card.public_data.col
            sequence = QSequentialAnimationGroup(out_group)
            sequence.addAnimation(QPauseAnimation(diag * max(12, wave_ms // 2)))
            pair = QParallelAnimationGroup(sequence)
            fade = QPropertyAnimation(card, b"opacity", pair)
            fade.setDuration(collapse_ms)
            fade.setStartValue(card.opacity())
            fade.setEndValue(0.0)
            fade.setEasingCurve(build_easing(EASE_AWAY))
            shrink = QPropertyAnimation(card, b"scale", pair)
            shrink.setDuration(collapse_ms)
            shrink.setStartValue(card.scale())
            shrink.setEndValue(SCALE_ENTRANCE)
            shrink.setEasingCurve(build_easing(EASE_AWAY))
            pair.addAnimation(fade)
            pair.addAnimation(shrink)
            sequence.addAnimation(pair)
            out_group.addAnimation(sequence)

        self._board_transition = out_group

        def rebuild() -> None:
            self.set_board(normalized)
            in_group = QParallelAnimationGroup(self)
            new_cards = sorted(
                self._cards_by_id.values(),
                key=lambda c: (c.public_data.row + c.public_data.col, c.public_data.row),
            )
            enter_ms = DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.board_rebuild_duration)
            spring_curve = build_easing(SPRING_ENTRANCE, tempo=DEFAULT_MOTION.tempo)
            fade_curve = build_easing(EASE_OUT)
            for card in new_cards:
                card.setTransformOriginPoint(card.card_rect().center())
                card.setOpacity(0.0)
                card.setScale(SCALE_ENTRANCE)
                diag = card.public_data.row + card.public_data.col
                sequence = QSequentialAnimationGroup(in_group)
                sequence.addAnimation(QPauseAnimation(diag * wave_ms))
                pair = QParallelAnimationGroup(sequence)
                fade = QPropertyAnimation(card, b"opacity", pair)
                fade.setDuration(max(1, int(enter_ms * 0.72)))
                fade.setStartValue(0.0)
                fade.setEndValue(1.0)
                fade.setEasingCurve(fade_curve)
                settle = QPropertyAnimation(card, b"scale", pair)
                settle.setDuration(enter_ms)
                settle.setStartValue(SCALE_ENTRANCE)
                settle.setEndValue(1.0)
                settle.setEasingCurve(spring_curve)
                pair.addAnimation(fade)
                pair.addAnimation(settle)
                sequence.addAnimation(pair)
                in_group.addAnimation(sequence)

            def complete() -> None:
                self._board_transition = None
                if callable(finished):
                    finished()

            in_group.finished.connect(complete)
            self._board_transition = in_group
            in_group.start()

        out_group.finished.connect(rebuild)
        out_group.start()

    def set_interactive(self, enabled: bool) -> None:
        """Enable or disable mouse/keyboard card interaction."""
        self._interactive = bool(enabled)
        for card in self._cards_by_id.values():
            card.set_interactive(self._interactive)

    # ------------------------------------------------------------------
    # Internal Scene Construction & Shared Pixmap Caching
    # ------------------------------------------------------------------

    def _get_scaled_card_pixmap(self, asset_id: AssetId, width: int, height: int) -> QPixmap:
        key = (asset_id, width, height)
        cached = self._scaled_art_cache.get(key)
        if cached is not None:
            return cached
        raw = self._pixmap_loader.load_pixmap(asset_id, prefer_derived=False)
        if raw.isNull():
            self._scaled_art_cache[key] = raw
            return raw
        scaled = PixmapLoader.scale_contain(raw, QSize(width, height), allow_upscale=False)
        self._scaled_art_cache[key] = scaled
        return scaled

    def _portrait_target_size(self, mode: CardDisplayMode) -> tuple[int, int]:
        # 2x HiDPI pre-scaled target matching CharacterCard._compute_portrait_frame_rect
        if mode is CardDisplayMode.EXPANDED:
            return (220, 220)
        if mode is CardDisplayMode.STANDARD:
            return (192, 192)
        return (160, 160)

    def _sync_card_portrait(
        self,
        card: CharacterCard,
        puzzle_id: str,
        ch: PublicCharacterView,
        mode: CardDisplayMode,
    ) -> None:
        target_sz = self._portrait_target_size(mode)
        p_path = self._portrait_registry.get_portrait_path(
            puzzle_id,
            ch.cell_id,
            expected_name=ch.name,
            expected_profession=ch.profession,
        )
        p_pm = (
            self._portrait_registry.get_portrait(
                puzzle_id,
                ch.cell_id,
                size=target_sz,
                expected_name=ch.name,
                expected_profession=ch.profession,
            )
            if p_path is not None
            else None
        )
        card.set_portrait_pixmap(
            p_pm,
            portrait_path=str(p_path) if p_path is not None else None,
        )

    def _rebuild_scene(self, snapshot: PublicBoardSnapshot, mode: CardDisplayMode) -> None:
        # Stop all active flips & glows before clearing QGraphicsScene items
        self._clear_hint_particles()
        self._clear_evidence_threads()
        self._motion_coordinator.reset_visuals(self._cards_by_id)
        self._scene.clear()
        self._cards_by_id.clear()
        self._cards_by_coord.clear()
        self._selected_cell_id = None

        n = snapshot.grid_size
        card_w, card_h = CARD_DIMENSIONS_BY_MODE[mode]
        gap_x = _GAP_X_BY_MODE[mode]
        gap_y = _GAP_Y_BY_MODE[mode]
        axis_pad = 20.0
        # Horizontal margin 14px keeps corner 3D flip/glow safely unclipped; vertical 10px maximizes card scale
        margin_x = 14.0
        margin_y = 10.0

        shared_back = self._get_scaled_card_pixmap(AssetId.A01_CARD_BACK, card_w, card_h)
        shared_front = self._get_scaled_card_pixmap(AssetId.A02_CARD_FRONT_TEMPLATE, card_w, card_h)

        axis_font = QFont(TYPOGRAPHY.font_family_mono[0])
        axis_font.setPixelSize(TYPOGRAPHY.size_axis_coord)
        axis_font.setBold(True)
        # Luminous champagne-ivory coordinates for >= 9:1 contrast over the dark noir backdrop
        axis_color = QColor("#F5E6C8")

        for col in range(n):
            col_label = chr(ord("A") + col)
            item = QGraphicsSimpleTextItem(col_label)
            item.setFont(axis_font)
            item.setBrush(axis_color)
            br = item.boundingRect()
            cx = margin_x + axis_pad + col * (card_w + gap_x) + (card_w - br.width()) / 2.0
            cy = margin_y + (axis_pad - br.height()) / 2.0
            item.setPos(cx, cy)
            self._scene.addItem(item)

        for row in range(n):
            row_label = str(row + 1)
            cy = margin_y + axis_pad + row * (card_h + gap_y) + card_h / 2.0
            cx = margin_x + axis_pad / 2.0
            # Antique brass circular row coordinate medallion (matches mockup ①..⑤)
            ring = QGraphicsEllipseItem(cx - 9.0, cy - 9.0, 18.0, 18.0)
            ring.setBrush(QBrush(QColor(22, 17, 13, 215)))
            ring.setPen(QPen(QColor(206, 168, 98, 200), 1.25))
            self._scene.addItem(ring)

            item = QGraphicsSimpleTextItem(row_label)
            item.setFont(axis_font)
            item.setBrush(axis_color)
            br = item.boundingRect()
            item.setPos(cx - br.width() / 2.0, cy - br.height() / 2.0)
            self._scene.addItem(item)

        for ch in snapshot.characters:
            card = CharacterCard(
                ch,
                display_mode=mode,
                card_back_pixmap=shared_back,
                card_front_pixmap=shared_front,
                reduced_motion=self._motion_coordinator.reduced_motion,
            )
            self._sync_card_portrait(card, snapshot.puzzle_id, ch, mode)
            card.set_interactive(self._interactive)
            x = margin_x + axis_pad + ch.col * (card_w + gap_x)
            y = margin_y + axis_pad + ch.row * (card_h + gap_y)
            card.setPos(x, y)
            card.card_selected.connect(self._handle_user_card_selected)
            self._scene.addItem(card)
            self._cards_by_id[ch.cell_id] = card
            self._cards_by_coord[(ch.row, ch.col)] = card

        total_w = margin_x * 2.0 + axis_pad + n * card_w + (n - 1) * gap_x
        total_h = margin_y * 2.0 + axis_pad + n * card_h + (n - 1) * gap_y
        self._scene.setSceneRect(QRectF(0.0, 0.0, total_w, total_h))
        self.fit_board_to_viewport()

    def _handle_user_card_selected(self, cell_id: str) -> None:
        if not self._interactive or self.is_animating or cell_id not in self._cards_by_id:
            return
        self.set_selection(cell_id)
        self.card_selected.emit(cell_id)

    # ------------------------------------------------------------------
    # Responsive Uniform Scaling, Keyboard Navigation & Safe Cleanup
    # ------------------------------------------------------------------

    def fit_board_to_viewport(self) -> float:
        """Compute uniform transform fitting the board within viewport without distorting 3:4 cards."""
        sr = self._scene.sceneRect()
        vp = self.viewport().size()
        if sr.width() <= 0 or sr.height() <= 0 or vp.width() <= 0 or vp.height() <= 0:
            return self._current_scale

        avail_w = max(1.0, vp.width() - 6.0)
        avail_h = max(1.0, vp.height() - 6.0)
        fit = min(avail_w / sr.width(), avail_h / sr.height())
        min_scale = _MIN_SCALE_BY_MODE.get(self._display_mode, 0.72)
        scale = max(min_scale, min(GEOMETRY.board_max_scale, fit))

        self.setTransform(QTransform.fromScale(scale, scale))
        self._current_scale = scale
        return scale

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        vp = self.viewport().size()
        if vp.width() > 0 and vp.height() > 0 and not self.reduced_motion:
            pos = event.position()
            self._cursor_vp = pos
            nx = max(-1.0, min(1.0, (pos.x() - vp.width() * 0.5) / max(1.0, vp.width() * 0.5)))
            ny = max(-1.0, min(1.0, (pos.y() - vp.height() * 0.5) / max(1.0, vp.height() * 0.5)))
            self._cursor_norm = QPointF(nx, ny)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._cursor_vp = None
        super().leaveEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self.reduced_motion and not self._ambient_timer.isActive():
            self._ambient_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._ambient_timer.stop()
        super().hideEvent(event)

    def _on_ambient_tick(self) -> None:
        if self.reduced_motion or not self.isVisible():
            self._ambient_timer.stop()
            return
        self._ambient_phase = (self._ambient_phase + 0.042) % (200.0 * math.pi)
        if self._ripple_progress < 1.0:
            self._ripple_progress = min(1.0, self._ripple_progress + 0.048)
        # Smoothly decay cursor parallax toward center when cursor leaves
        if self._cursor_vp is None:
            self._cursor_norm = QPointF(
                self._cursor_norm.x() * 0.90,
                self._cursor_norm.y() * 0.90,
            )
        self.viewport().update()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802, ARG002
        """Render the Living Shimmering Noir Detective Desk backdrop behind the N×N board."""
        vp = self.viewport().size()
        vw, vh = float(vp.width()), float(vp.height())
        if vw <= 4.0 or vh <= 4.0:
            return

        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        vp_rect = QRectF(0.0, 0.0, vw, vh)
        phase = 0.0 if self.reduced_motion else self._ambient_phase
        px_off = 0.0 if self.reduced_motion else (-self._cursor_norm.x() * 6.5)
        py_off = 0.0 if self.reduced_motion else (-self._cursor_norm.y() * 4.5)

        # 1. Layer 1 — Custom Widescreen Noir Detective Office Backdrop (A05_board_mat_noir.png)
        #    Seamless 3-slice widescreen framing preserves 1:1 proportions on the brass lamp, blinds,
        #    Sherlock mug, magnifying glass (left) and round full moon, Eiffel spire, skyline (right).
        overscan = QSize(int(vw + 16), int(vh + 12))
        if self._bg_cached_pm is None or self._bg_cached_size != overscan:
            noir_bg_path = Path(__file__).resolve().parents[2] / "assets" / "backgrounds" / "A05_board_mat_noir.png"
            raw_bg = QPixmap(str(noir_bg_path)) if noir_bg_path.is_file() else QPixmap()
            if raw_bg.isNull():
                raw_bg = self._pixmap_loader.load_pixmap(AssetId.A05_GAMEPLAY_BACKGROUND, prefer_derived=False)
            if not raw_bg.isNull():
                self._bg_cached_pm = raw_bg.scaled(
                    overscan,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._bg_cached_size = overscan

        if self._bg_cached_pm is not None and not self._bg_cached_pm.isNull():
            painter.drawPixmap(int(-8.0 + px_off), int(-6.0 + py_off), self._bg_cached_pm)
        else:
            painter.fillRect(vp_rect, QColor("#1A130E"))

        painter.setPen(Qt.PenStyle.NoPen)

        # 2. Layer 2 — Warm Brass Desk Lamp Tungsten Pulse & Volumetric Light Cone (left side)
        lamp_pt = QPointF(vw * 0.114 + px_off * 0.9, vh * 0.575 + py_off * 0.9)
        lamp_flicker = (
            0.86
            + 0.10 * math.sin(phase * 1.9)
            + 0.04 * math.sin(phase * 4.7 + 0.8)
        )
        # Soft volumetric cone pouring down onto books, Sherlock mug & magnifying glass
        cone = QPolygonF(
            [
                lamp_pt + QPointF(-vw * 0.025, 0.0),
                lamp_pt + QPointF(vw * 0.045, -vh * 0.01),
                QPointF(vw * 0.38 + px_off * 0.6, vh * 1.02),
                QPointF(vw * 0.00 + px_off * 0.6, vh * 1.02),
            ]
        )
        cone_grad = QLinearGradient(lamp_pt, QPointF(vw * 0.22, vh * 0.96))
        cone_grad.setColorAt(0.0, QColor(255, 224, 150, int(92 * lamp_flicker)))
        cone_grad.setColorAt(0.45, QColor(242, 178, 86, int(44 * lamp_flicker)))
        cone_grad.setColorAt(1.0, QColor(232, 155, 62, 0))
        painter.setBrush(cone_grad)
        painter.drawPolygon(cone)

        # Warm glowing bulb core halo
        bulb_r = min(vw, vh) * 0.165
        bulb_grad = QRadialGradient(lamp_pt, bulb_r)
        bulb_grad.setColorAt(0.0, QColor(255, 246, 206, int(135 * lamp_flicker)))
        bulb_grad.setColorAt(0.28, QColor(255, 198, 102, int(72 * lamp_flicker)))
        bulb_grad.setColorAt(0.65, QColor(228, 146, 54, int(24 * lamp_flicker)))
        bulb_grad.setColorAt(1.0, QColor(228, 146, 54, 0))
        painter.setBrush(bulb_grad)
        painter.drawEllipse(lamp_pt, bulb_r, bulb_r)

        # 3. Layer 3 — Swaying Venetian Blind Light Shafts & Soft Moonbeam Veil
        sway = math.sin(phase * 0.62) * 14.0
        for idx, (y_off, alpha_peak) in enumerate(((0.02, 24), (0.08, 22), (0.14, 18), (0.20, 14))):
            pulse = 0.78 + 0.22 * math.sin(phase * 1.05 + idx * 0.5)
            p_start = QPointF(vw * 0.16 + px_off * 0.7, vh * y_off + py_off * 0.6)
            shaft = QPolygonF(
                [
                    p_start,
                    p_start + QPointF(vw * 0.04, -vh * 0.01),
                    p_start + QPointF(vw * 0.34 + sway, vh * 0.24),
                    p_start + QPointF(vw * 0.27 + sway, vh * 0.29),
                ]
            )
            sg = QLinearGradient(p_start, p_start + QPointF(vw * 0.30, vh * 0.26))
            sg.setColorAt(0.0, QColor(255, 214, 134, int(alpha_peak * pulse)))
            sg.setColorAt(0.6, QColor(235, 182, 104, int(alpha_peak * 0.4 * pulse)))
            sg.setColorAt(1.0, QColor(235, 182, 104, 0))
            painter.setBrush(sg)
            painter.drawPolygon(shaft)

        # 4. Layer 4 — Shimmering Full Moon Corona, Drifting Night Clouds & Moonbeam (top-right)
        moon_pt = QPointF(vw * 0.922 + px_off * 0.55, vh * 0.096 + py_off * 0.55)
        moon_pulse = 0.84 + 0.16 * math.sin(phase * 1.15)
        moon_r = min(vw, vh) * 0.23
        moon_grad = QRadialGradient(moon_pt, moon_r)
        moon_grad.setColorAt(0.0, QColor(255, 248, 218, int(92 * moon_pulse)))
        moon_grad.setColorAt(0.32, QColor(252, 224, 162, int(48 * moon_pulse)))
        moon_grad.setColorAt(0.68, QColor(198, 178, 148, int(18 * moon_pulse)))
        moon_grad.setColorAt(1.0, QColor(198, 178, 148, 0))
        painter.setBrush(moon_grad)
        painter.drawEllipse(moon_pt, moon_r, moon_r)

        # Delicate moonlit mist wisps drifting slowly past the full moon
        for c_idx, (cy_r, speed, span) in enumerate(((0.068, 0.32, 0.11), (0.158, -0.26, 0.14))):
            cx = vw * (0.86 + 0.055 * math.sin(phase * speed + c_idx * 1.7)) + px_off * 0.45
            cy = vh * cy_r + py_off * 0.45
            cw, ch = vw * span, vh * 0.036
            cloud_grad = QRadialGradient(QPointF(cx, cy), cw)
            cloud_grad.setColorAt(0.0, QColor(246, 228, 196, 30))
            cloud_grad.setColorAt(0.6, QColor(214, 190, 158, 12))
            cloud_grad.setColorAt(1.0, QColor(214, 190, 158, 0))
            painter.setBrush(cloud_grad)
            painter.drawEllipse(QPointF(cx, cy), cw, ch)

        # 5. Layer 5 — Twinkling City Skyline Windows & Eiffel Spire Beacon Sparkle
        for idx, (lx, ly, spd, ph0, rad) in enumerate(self._skyline_lights):
            pt = QPointF(vw * lx + px_off * 0.72, vh * ly + py_off * 0.72)
            tw = 0.45 + 0.55 * math.sin(phase * spd + ph0)
            a_core = int((155 if idx == 0 else 108) * tw)
            r_glow = rad * (1.25 + 0.55 * tw)
            wg = QRadialGradient(pt, r_glow * 2.2)
            wg.setColorAt(0.0, QColor(255, 245, 206, a_core))
            wg.setColorAt(0.45, QColor(255, 196, 94, int(a_core * 0.5)))
            wg.setColorAt(1.0, QColor(255, 180, 74, 0))
            painter.setBrush(wg)
            painter.drawEllipse(pt, r_glow * 2.2, r_glow * 2.2)
            if idx == 0:
                # Crisp 4-point star sparkle atop the illuminated spire
                self._draw_star_sparkle(painter, pt, 7.5 + 3.5 * tw, QColor(255, 248, 220, int(215 * tw)))

        # 6. Layer 6 — Rising Curling Coffee Steam above Sherlock Mug & Magnifying Glass Glint
        mug_x = vw * 0.258 + px_off * 0.85
        mug_y = vh * 0.742 + py_off * 0.85
        for s_idx in range(3):
            prog = (phase * 0.24 + s_idx * 0.333) % 1.0
            fade = math.sin(prog * math.pi)
            if fade > 0.05:
                y0 = mug_y - prog * vh * 0.025
                y1 = mug_y - (0.07 + prog * 0.13) * vh
                wave1 = math.sin(phase * 1.4 + s_idx * 2.1) * 9.0
                wave2 = math.cos(phase * 1.1 + s_idx * 1.6) * 12.0
                ox = (s_idx - 1) * 7.5
                steam_path = QPainterPath(QPointF(mug_x + ox, y0))
                steam_path.cubicTo(
                    QPointF(mug_x + ox + wave1, (y0 + y1) * 0.5 + 12.0),
                    QPointF(mug_x + ox - wave2, (y0 + y1) * 0.5 - 12.0),
                    QPointF(mug_x + ox + wave1 * 0.6, y1),
                )
                steam_pen = QPen(
                    QColor(255, 238, 208, int(44 * fade)),
                    3.2 - prog * 1.6,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
                painter.setPen(steam_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(steam_path)

        painter.setPen(Qt.PenStyle.NoPen)
        # Sweeping optical glass reflection on bottom-left magnifying glass
        lens_pt = QPointF(vw * 0.188 + px_off * 0.9, vh * 0.905 + py_off * 0.9)
        lens_r = min(vw, vh) * 0.078
        glint_shift = math.sin(phase * 1.35) * (lens_r * 0.55)
        lens_grad = QRadialGradient(lens_pt + QPointF(glint_shift, -glint_shift * 0.35), lens_r)
        lens_a = int(76 + 44 * math.sin(phase * 1.85))
        lens_grad.setColorAt(0.0, QColor(255, 250, 232, lens_a))
        lens_grad.setColorAt(0.45, QColor(246, 202, 122, int(lens_a * 0.45)))
        lens_grad.setColorAt(1.0, QColor(246, 202, 122, 0))
        painter.setBrush(lens_grad)
        painter.drawEllipse(lens_pt, lens_r * 1.25, lens_r * 0.72)

        # 7. Layer 7 — 40 Shimmering 3D Golden Dust Motes, Luminous Bokeh & 4-Point Star Sparkles
        for x0, y0, depth, speed, p0, radius, kind in self._dust_motes:
            t = phase * speed + p0
            dx = math.sin(t * 0.85) * (18.0 * depth) + px_off * (1.45 * depth)
            dy = -((phase * 9.5 * speed * depth) % vh)
            mx = (x0 * vw + dx) % vw
            my = (y0 * vh + dy) % vh
            twinkle = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.25))
            alpha = int((56 + 112 * depth) * twinkle)
            if kind == 0:
                col = QColor(255, 210, 118, alpha)  # Warm golden lamp dust
            elif kind == 1:
                col = QColor(255, 245, 220, int(alpha * 0.92))  # Soft moon pearl bokeh
            else:
                col = QColor(255, 244, 204, min(240, int(alpha * 1.18)))  # Shimmering star glint

            r_eff = radius * (0.85 + 0.55 * depth)
            halo = QRadialGradient(QPointF(mx, my), r_eff * 3.1)
            halo.setColorAt(0.0, col)
            halo.setColorAt(0.4, QColor(col.red(), col.green(), col.blue(), int(alpha * 0.42)))
            halo.setColorAt(1.0, QColor(col.red(), col.green(), col.blue(), 0))
            painter.setBrush(halo)
            painter.drawEllipse(QPointF(mx, my), r_eff * 3.1, r_eff * 3.1)

            if kind == 2 and twinkle > 0.62:
                self._draw_star_sparkle(
                    painter,
                    QPointF(mx, my),
                    r_eff * (2.2 + 1.4 * twinkle),
                    QColor(255, 250, 232, min(230, int(alpha * 1.25))),
                )

        # 8. Layer 8 — Interactive Warm Detective Lantern Cursor Spotlight
        if self._cursor_vp is not None and not self.reduced_motion:
            spot = QRadialGradient(self._cursor_vp, 190.0)
            spot.setColorAt(0.0, QColor(255, 234, 178, 56))
            spot.setColorAt(0.5, QColor(235, 178, 92, 22))
            spot.setColorAt(1.0, QColor(235, 178, 92, 0))
            painter.setBrush(spot)
            painter.drawEllipse(self._cursor_vp, 190.0, 190.0)

        # 9. Layer 9 — Dark Leather & Double Antique-Brass Filigree Board Frame + Deduction Ripple
        sr = self._scene.sceneRect()
        if sr.width() > 0 and sr.height() > 0:
            mapped = self.mapFromScene(sr).boundingRect()
            mat_rect = QRectF(mapped).adjusted(-8.0, -7.0, 8.0, 7.0)

            # Soft outer tabletop shadow beneath dark leather frame
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 5, 3, 105))
            painter.drawRoundedRect(mat_rect.translated(0.0, 3.0).adjusted(-3.0, -2.0, 3.0, 3.0), 12.0, 12.0)

            # Rich dark detective leather board well (maximizes contrast for cards & glowing threads)
            painter.setBrush(QColor(18, 14, 11, 184))
            painter.setPen(QPen(QColor(206, 166, 92, 225), 2.1, Qt.PenStyle.SolidLine))
            painter.drawRoundedRect(mat_rect, 10.0, 10.0)

            inner_mat = mat_rect.adjusted(4.5, 4.5, -4.5, -4.5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(232, 198, 128, 130), 1.0))
            painter.drawRoundedRect(inner_mat, 7.0, 7.0)

            # Ornate antique brass corner filigree brackets inside the 4 board corners
            f_pen = QPen(QColor(226, 188, 112, 195), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(f_pen)
            for fx, fy, sx, sy in (
                (inner_mat.left() + 3.0, inner_mat.top() + 3.0, 1.0, 1.0),
                (inner_mat.right() - 3.0, inner_mat.top() + 3.0, -1.0, 1.0),
                (inner_mat.left() + 3.0, inner_mat.bottom() - 3.0, 1.0, -1.0),
                (inner_mat.right() - 3.0, inner_mat.bottom() - 3.0, -1.0, -1.0),
            ):
                painter.save()
                painter.translate(fx, fy)
                painter.scale(sx, sy)
                painter.drawLine(QPointF(0.0, 0.0), QPointF(14.0, 0.0))
                painter.drawLine(QPointF(0.0, 0.0), QPointF(0.0, 14.0))
                scroll = QPainterPath(QPointF(2.5, 11.0))
                scroll.quadTo(QPointF(3.5, 3.5), QPointF(11.0, 2.5))
                painter.drawPath(scroll)
                painter.restore()

            clip = QPainterPath()
            clip.addRoundedRect(inner_mat, 7.0, 7.0)
            painter.save()
            painter.setClipPath(clip)

            # Delicate golden archival coordinate hairlines
            grid_pen = QPen(QColor(232, 188, 112, 18), 1.0)
            painter.setPen(grid_pen)
            step_px = 26.0
            gx = inner_mat.left() + step_px
            while gx < inner_mat.right():
                painter.drawLine(QPointF(gx, inner_mat.top()), QPointF(gx, inner_mat.bottom()))
                gx += step_px
            gy = inner_mat.top() + step_px
            while gy < inner_mat.bottom():
                painter.drawLine(QPointF(inner_mat.left(), gy), QPointF(inner_mat.right(), gy))
                gy += step_px

            # Expanding luminous golden-amber deduction ripple wave when evidence is focused
            if self._ripple_progress < 0.995 and not self.reduced_motion:
                rp = self._ripple_progress
                r_max = max(inner_mat.width(), inner_mat.height()) * 0.72
                r_cur = 24.0 + rp * r_max
                r_alpha = int(150 * (1.0 - rp) * (1.0 - rp))
                painter.setPen(QPen(QColor(246, 206, 128, r_alpha), 2.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(inner_mat.center(), r_cur, r_cur)

            painter.restore()

        # Subtle antique-gold inner vignette frame around the viewport
        border_pen = QPen(QColor(218, 174, 102, 155), 1.3)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(vp_rect.adjusted(0.6, 0.6, -0.6, -0.6), 7.0, 7.0)
        painter.restore()

    @staticmethod
    def _draw_star_sparkle(painter: QPainter, center: QPointF, arm: float, color: QColor) -> None:
        """Draw a crisp 4-point diamond starlight sparkle for shimmering atmospheric dust."""
        if arm <= 1.0 or color.alpha() <= 4:
            return
        w = max(0.85, arm * 0.20)
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
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(star)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fit_board_to_viewport()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._ambient_timer.stop()
        self._clear_hint_particles()
        self._clear_evidence_threads()
        if self._board_transition is not None:
            self._board_transition.stop()
        self._motion_coordinator.reset_visuals(self._cards_by_id)
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._interactive and not self.is_animating and self._snapshot is not None:
            deltas = {
                Qt.Key.Key_Up: (-1, 0),
                Qt.Key.Key_Down: (1, 0),
                Qt.Key.Key_Left: (0, -1),
                Qt.Key.Key_Right: (0, 1),
            }
            if event.key() in deltas:
                dr, dc = deltas[event.key()]
                self._move_focus_by_delta(dr, dc)
                event.accept()
                return
        super().keyPressEvent(event)

    def _move_focus_by_delta(self, dr: int, dc: int) -> None:
        if self._snapshot is None or not self._cards_by_coord:
            return
        n = self._snapshot.grid_size
        focused = self._scene.focusItem()
        if isinstance(focused, CharacterCard):
            row, col = focused.public_data.row, focused.public_data.col
        elif self._selected_cell_id and self._selected_cell_id in self._cards_by_id:
            d = self._cards_by_id[self._selected_cell_id].public_data
            row, col = d.row, d.col
        else:
            row, col = 0, 0
            target = self._cards_by_coord.get((0, 0))
            if target is not None:
                target.setFocus()
            return

        nr = max(0, min(n - 1, row + dr))
        nc = max(0, min(n - 1, col + dc))
        target = self._cards_by_coord.get((nr, nc))
        if target is not None:
            target.setFocus()
            self.ensureVisible(target, 16, 16)
