"""CluePanel — Public Evidence List displaying revealed clues (Phase 4).

Displays ONLY public clues supplied via ``PublicClueView`` (normalized via
``normalize_clue_view``). Never computes clue regions, never evaluates SAT/DPLL,
and never reads unrevealed clues or ``puzzles/*.json``.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.asset_registry import CLUE_ICON_BY_TYPE
from src.gui.components.styled_panel import StyledPanel
from src.gui.resources.pixmap_loader import PixmapLoader, default_pixmap_loader
from src.gui.styles.tokens import COLORS, SPACING
from src.gui.view_models import PublicClueView, normalize_clue_view

_CLUE_TYPE_LABELS_VI: dict[str, str] = {
    "FACT": "FACT · Xác định trực tiếp",
    "SAME": "SAME · Cùng phe",
    "DIFFERENT": "DIFFERENT · Khác phe",
    "EXACTLY": "EXACTLY · Đúng k tội phạm",
    "AT_LEAST": "AT_LEAST · Ít nhất k tội phạm",
    "AT_MOST": "AT_MOST · Nhiều nhất k tội phạm",
}


class _ClueCardItem(QFrame):
    """Single clickable evidence card rendered inside ``CluePanel``."""

    clicked = Signal(str)
    used_toggled = Signal(str, bool)

    ICON_SIZE = QSize(48, 46)

    def __init__(
        self,
        clue: PublicClueView,
        *,
        pixmap_loader: PixmapLoader,
        interactive: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._clue = clue
        self._selected = False
        self._interactive = bool(interactive)

        self.setProperty("widgetKind", "clueCard")
        self.setProperty("selected", "false")
        self.setProperty("interactive", "true" if self._interactive else "false")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._interactive
            else Qt.CursorShape.ArrowCursor
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        type_hint = _CLUE_TYPE_LABELS_VI.get(clue.clue_type, clue.clue_type)
        self.setToolTip(
            f"{clue.clue_id} [{type_hint}]\n"
            f"Chủ manh mối: {clue.owner_id}\n"
            f"{clue.text}"
        )
        self.setAccessibleName(f"Manh mối {clue.clue_id}. Nhấn Enter để tập trung, nhấp đúp để đánh dấu đã dùng.")

        root = QHBoxLayout(self)
        root.setContentsMargins(SPACING.space_2, SPACING.space_2, SPACING.space_2, SPACING.space_2)
        root.setSpacing(SPACING.space_2)

        # Left: A10 Clue Icon (>=48px) or safe Qt-native fallback badge for unknown clue types
        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(self.ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._used_fallback_icon = False

        asset_id = CLUE_ICON_BY_TYPE.get(clue.clue_type)
        pixmap = (
            pixmap_loader.load_pixmap(asset_id, prefer_derived=False)
            if asset_id is not None
            else None
        )
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap_loader.scale_contain(pixmap, self.ICON_SIZE, allow_upscale=False)
            self._icon_label.setPixmap(scaled)
        else:
            self._used_fallback_icon = True
            self._icon_label.setProperty("widgetKind", "clueFallbackBadge")
            short_code = clue.clue_type[:4] if clue.clue_type else "?"
            self._icon_label.setText(short_code)
            self._icon_label.setToolTip(f"Biểu tượng dự phòng cho loại manh mối: {clue.clue_type}")

        root.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Right: Clean 2-line layout (Manh mối từ ô <owner> + wrapped plain-text statement)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        self._id_label = QLabel(clue.clue_id, self)
        self._id_label.setTextFormat(Qt.TextFormat.PlainText)
        self._id_label.setProperty("role", "paperMono")
        self._id_label.setVisible(False)

        self._type_pill = QLabel(clue.clue_type, self)
        self._type_pill.setTextFormat(Qt.TextFormat.PlainText)
        self._type_pill.setProperty("widgetKind", "clueTypePill")
        self._type_pill.setVisible(False)

        self._owner_label = QLabel(f"Manh mối từ ô {clue.owner_id}", self)
        self._owner_label.setTextFormat(Qt.TextFormat.PlainText)
        self._owner_label.setProperty("role", "paperSubheading")
        col.addWidget(self._owner_label)

        self._text_label = QLabel(clue.text, self)
        self._text_label.setTextFormat(Qt.TextFormat.PlainText)
        self._text_label.setProperty("role", "paperBody")
        self._text_label.setWordWrap(True)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        col.addWidget(self._text_label)

        # Coordinate chips are plain public metadata, independent of SAT state.
        self._chips = QWidget(self)
        chips_layout = QGridLayout(self._chips)
        chips_layout.setContentsMargins(0, 4, 0, 0)
        chips_layout.setSpacing(4)
        badges = list(clue.reference_labels)
        for index, cid in enumerate(clue.referenced_cells):
            comparative = clue.clue_type in {"SAME", "DIFFERENT", "COUNT_COMPARE"}
            secondary = cid in clue.secondary_cells or (not clue.primary_cells and index > 0)
            role = ("Đối chiếu" if secondary else "Chính") if comparative else "Ô"
            badges.append(f"{role} {cid}")
        for index, badge in enumerate(badges):
            chip = QLabel(badge, self._chips)
            chip.setTextFormat(Qt.TextFormat.PlainText)
            chip.setStyleSheet(f"color: {COLORS.paper_clue}; background: {COLORS.paper_beige}; border: 1px solid {COLORS.paper_border}; border-radius: 6px; padding: 3px 6px; font-size: 11px;")
            chips_layout.addWidget(chip, index // 3, index % 3)
        self._chips.setVisible(False)
        col.addWidget(self._chips)

        root.addLayout(col, 1)
        self.used_button = QCheckBox(self)
        self.used_button.setToolTip("Đánh dấu đã dùng xong (hoặc nhấp đúp manh mối)")
        self.used_button.setAccessibleName(f"Đã dùng xong {clue.clue_id}")
        self.used_button.toggled.connect(self._set_used)
        root.addWidget(self.used_button, 0, Qt.AlignmentFlag.AlignTop)

    def _set_used(self, used: bool) -> None:
        font = self._text_label.font()
        font.setStrikeOut(used)
        self._text_label.setFont(font)
        self._text_label.setStyleSheet(f"color: {COLORS.ink_disabled};" if used else "")
        self.used_toggled.emit(self._clue.clue_id, used)

    def set_used(self, used: bool) -> None:
        self.used_button.setChecked(used)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._interactive and event.button() == Qt.MouseButton.LeftButton:
            self.used_button.toggle()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    @property
    def clue(self) -> PublicClueView:
        return self._clue

    @property
    def is_selected(self) -> bool:
        return self._selected

    @property
    def used_fallback_icon(self) -> bool:
        return self._used_fallback_icon

    @property
    def icon_label(self) -> QLabel:
        return self._icon_label

    @property
    def text_label(self) -> QLabel:
        return self._text_label

    def set_selected(self, selected: bool) -> None:
        flag = bool(selected)
        if self._selected == flag:
            return
        self._selected = flag
        self._chips.setVisible(flag)
        self.setProperty("selected", "true" if flag else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_interactive(self, enabled: bool) -> None:
        flag = bool(enabled)
        self._interactive = flag
        self.used_button.setEnabled(flag)
        self.setProperty("interactive", "true" if flag else "false")
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if flag else Qt.CursorShape.ArrowCursor
        )
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._interactive and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._clue.clue_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._interactive and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.clicked.emit(self._clue.clue_id)
            event.accept()
            return
        super().keyPressEvent(event)


class CluePanel(StyledPanel):
    """Scrollable evidence panel displaying ONLY public clues supplied by Controller."""

    clue_selected = Signal(str)
    clue_usage_changed = Signal(str, bool)
    focus_cleared = Signal()

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._pixmap_loader = pixmap_loader or default_pixmap_loader()
        super().__init__(
            title="Bảng Chứng Cứ",
            subtitle="0 manh mối công khai",
            variant="paper",
            padding=SPACING.space_3,
            decorative_texture=True,  # Subtle 8% cropped central A08 paper underlay
            accent_bar="brass",
            pixmap_loader=self._pixmap_loader,
            parent=parent,
        )
        self.setObjectName("CluePanel")

        self._clues: list[PublicClueView] = []
        self._cards_by_id: dict[str, _ClueCardItem] = {}
        self._selected_clue_id: Optional[str] = None
        self._interactive: bool = True
        self._used_clues: set[str] = set()

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setMinimumHeight(110)

        self._list_host = QWidget(self._scroll_area)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, SPACING.space_1, 0)
        self._list_layout.setSpacing(SPACING.space_2)

        self._empty_label = QLabel(
            "Chưa có manh mối công khai.\nHãy lật thẻ hoặc nạp một vụ án để xem chứng cứ.",
            self._list_host,
        )
        self._empty_label.setProperty("role", "paperCaption")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._empty_label.setContentsMargins(SPACING.space_2, SPACING.space_4, SPACING.space_2, SPACING.space_4)
        self._list_layout.addWidget(self._empty_label)
        self._list_layout.addStretch(1)

        self._scroll_area.setWidget(self._list_host)
        self.content_layout.addWidget(self._scroll_area, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_clues(self, clues: Iterable[Any]) -> None:
        """Replace displayed clues with validated public clues (no duplicates)."""
        normalized: list[PublicClueView] = []
        seen_ids: set[str] = set()
        for raw in clues:
            clue = normalize_clue_view(raw)
            if clue.clue_id in seen_ids:
                continue
            seen_ids.add(clue.clue_id)
            normalized.append(clue)

        prev_selected = self._selected_clue_id
        self._clear_cards_only()
        self._clues = normalized

        for clue in self._clues:
            self._insert_card_widget(clue)

        self._sync_empty_and_subtitle()

        if prev_selected is not None and prev_selected in self._cards_by_id:
            self._selected_clue_id = prev_selected
            self._cards_by_id[prev_selected].set_selected(True)
        else:
            self._selected_clue_id = None

    def add_or_update_clue(self, raw_clue: Any) -> None:
        """Append a newly revealed public clue or refresh an existing entry."""
        clue = normalize_clue_view(raw_clue)
        if clue.clue_id in self._cards_by_id:
            updated = [clue if c.clue_id == clue.clue_id else c for c in self._clues]
            self.set_clues(updated)
            return
        self._clues.append(clue)
        self._insert_card_widget(clue)
        self._sync_empty_and_subtitle()

    def clear(self) -> None:
        """Remove all clue cards and reset selection."""
        self._clear_cards_only()
        self._clues = []
        self._selected_clue_id = None
        self._used_clues.clear()
        self._sync_empty_and_subtitle()

    @property
    def solved_clues(self) -> frozenset[str]:
        return frozenset(self._used_clues)

    def _on_usage_changed(self, clue_id: str, used: bool) -> None:
        if used:
            self._used_clues.add(clue_id)
        else:
            self._used_clues.discard(clue_id)
        self.clue_usage_changed.emit(clue_id, used)

    def set_selected_clue(self, clue_id: Optional[str]) -> bool:
        """Programmatically select a clue without emitting ``clue_selected``."""
        if clue_id is None:
            for card in self._cards_by_id.values():
                card.set_selected(False)
            self._selected_clue_id = None
            return True

        target = self._cards_by_id.get(clue_id)
        if target is None:
            return False

        for card in self._cards_by_id.values():
            card.set_selected(False)
        self._selected_clue_id = clue_id
        target.set_selected(True)
        self._scroll_area.ensureWidgetVisible(target)
        return True

    def set_evidence_clues(self, clue_ids: Iterable[str]) -> None:
        ids = tuple(cid for cid in clue_ids if cid in self._cards_by_id)
        self.set_selected_clue(ids[0] if ids else None)
        for cid in ids:
            self._cards_by_id[cid].set_selected(True)

    def set_interactive(self, enabled: bool) -> None:
        """Enable or lock user clue selection (e.g. during PROCESSING/ANIMATING)."""
        self._interactive = bool(enabled)
        for card in self._cards_by_id.values():
            card.set_interactive(self._interactive)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def clues(self) -> tuple[PublicClueView, ...]:
        return tuple(self._clues)

    @property
    def clue_cards(self) -> dict[str, _ClueCardItem]:
        return dict(self._cards_by_id)

    @property
    def selected_clue_id(self) -> Optional[str]:
        return self._selected_clue_id

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    @property
    def is_empty(self) -> bool:
        return len(self._clues) == 0

    @property
    def is_interactive(self) -> bool:
        return self._interactive

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _insert_card_widget(self, clue: PublicClueView) -> None:
        card = _ClueCardItem(
            clue,
            pixmap_loader=self._pixmap_loader,
            interactive=self._interactive,
            parent=self._list_host,
        )
        card.clicked.connect(self._on_card_clicked)
        card.set_used(clue.clue_id in self._used_clues)
        card.used_toggled.connect(self._on_usage_changed)
        # Insert right before trailing stretch item
        insert_idx = max(0, self._list_layout.count() - 1)
        self._list_layout.insertWidget(insert_idx, card)
        self._cards_by_id[clue.clue_id] = card

    def _clear_cards_only(self) -> None:
        for card in self._cards_by_id.values():
            self._list_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards_by_id.clear()

    def _sync_empty_and_subtitle(self) -> None:
        count = len(self._clues)
        self._empty_label.setVisible(count == 0)
        if self.subtitle_label is not None:
            if count == 0:
                self.subtitle_label.setText("0 manh mối công khai")
            else:
                self.subtitle_label.setText(f"{count} manh mối công khai · Nhấp để chọn")

    def _on_card_clicked(self, clue_id: str) -> None:
        if not self._interactive or clue_id not in self._cards_by_id:
            return
        if self._selected_clue_id == clue_id:
            self.set_selected_clue(None)
            self.focus_cleared.emit()
            return
        self.set_selected_clue(clue_id)
        self.clue_selected.emit(clue_id)
