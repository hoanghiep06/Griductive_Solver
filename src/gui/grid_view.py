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
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QSizePolicy,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.animations.motion_coordinator import MotionCoordinator
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

_MIN_SCALE_BY_MODE: dict[CardDisplayMode, float] = {
    CardDisplayMode.EXPANDED: 0.72,
    CardDisplayMode.STANDARD: 0.66,
    CardDisplayMode.COMPACT: 0.66,
}


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
                card.set_public_data(ch)
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
        self._motion_coordinator.set_reduced_motion(flag)
        for card in self._cards_by_id.values():
            card.set_reduced_motion(flag)

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
        valid = self._highlighter.apply_highlight(self._cards_by_id, cell_ids)
        active = set(valid)
        for cid, card in self._cards_by_id.items():
            card.set_focus_context(bool(active) and cid not in active, "primary")
        return valid

    def focus_evidence(self, primary: Iterable[str], references: Iterable[str] = ()) -> tuple[str, ...]:
        main = set(primary)
        targets = tuple(dict.fromkeys((*main, *references)))
        valid = self.highlight_cells(targets)
        for cid, card in self._cards_by_id.items():
            card.set_focus_context(bool(valid) and cid not in valid,
                                   "primary" if cid in main else "reference")
        return valid

    def set_highlighted_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        """Alias of ``highlight_cells`` matching Phase 5 §6.3."""
        return self.highlight_cells(cell_ids)

    def clear_highlights(self) -> None:
        """Fade out / clear all visual highlight overlays."""
        self._highlighter.clear_highlight(self._cards_by_id)
        for card in self._cards_by_id.values():
            card.set_focus_context(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and not isinstance(item, CharacterCard):
            self.background_clicked.emit()
        super().mousePressEvent(event)

    def clear_highlight(self) -> None:
        """Alias of ``clear_highlights`` matching Phase 5 §6.3."""
        self.clear_highlights()

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
        self._motion_coordinator.reset_visuals(self._cards_by_id)
        self._scene.clear()
        self._cards_by_id.clear()
        self._cards_by_coord.clear()
        self._selected_cell_id = None

        n = snapshot.grid_size
        card_w, card_h = CARD_DIMENSIONS_BY_MODE[mode]
        gap = _GAP_BY_MODE[mode]
        axis_pad = float(GEOMETRY.board_axis_label_space)
        # Extra margin (20px) ensures corner cards on 3x3/4x4/5x5 never clip during 3D lift/glow
        margin = 20.0

        shared_back = self._get_scaled_card_pixmap(AssetId.A01_CARD_BACK, card_w, card_h)
        shared_front = self._get_scaled_card_pixmap(AssetId.A02_CARD_FRONT_TEMPLATE, card_w, card_h)

        axis_font = QFont(TYPOGRAPHY.font_family_mono[0])
        axis_font.setPixelSize(TYPOGRAPHY.size_axis_coord)
        axis_font.setBold(True)
        axis_color = QColor(COLORS.ink_primary)

        for col in range(n):
            col_label = chr(ord("A") + col)
            item = QGraphicsSimpleTextItem(col_label)
            item.setFont(axis_font)
            item.setBrush(axis_color)
            br = item.boundingRect()
            cx = margin + axis_pad + col * (card_w + gap) + (card_w - br.width()) / 2.0
            cy = margin + (axis_pad - br.height()) / 2.0
            item.setPos(cx, cy)
            self._scene.addItem(item)

        for row in range(n):
            row_label = str(row + 1)
            item = QGraphicsSimpleTextItem(row_label)
            item.setFont(axis_font)
            item.setBrush(axis_color)
            br = item.boundingRect()
            rx = margin + (axis_pad - br.width()) / 2.0
            ry = margin + axis_pad + row * (card_h + gap) + (card_h - br.height()) / 2.0
            item.setPos(rx, ry)
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
            x = margin + axis_pad + ch.col * (card_w + gap)
            y = margin + axis_pad + ch.row * (card_h + gap)
            card.setPos(x, y)
            card.card_selected.connect(self._handle_user_card_selected)
            self._scene.addItem(card)
            self._cards_by_id[ch.cell_id] = card
            self._cards_by_coord[(ch.row, ch.col)] = card

        total_w = margin * 2.0 + axis_pad + n * card_w + (n - 1) * gap
        total_h = margin * 2.0 + axis_pad + n * card_h + (n - 1) * gap
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

        avail_w = max(1.0, vp.width() - 10.0)
        avail_h = max(1.0, vp.height() - 10.0)
        fit = min(avail_w / sr.width(), avail_h / sr.height())
        min_scale = _MIN_SCALE_BY_MODE.get(self._display_mode, 0.72)
        scale = max(min_scale, min(GEOMETRY.board_max_scale, fit))

        self.setTransform(QTransform.fromScale(scale, scale))
        self._current_scale = scale
        return scale

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fit_board_to_viewport()

    def closeEvent(self, event) -> None:  # noqa: N802
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
