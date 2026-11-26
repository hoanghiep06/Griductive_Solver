"""CluePanel — Editorial Evidence Ledger displaying revealed public clues.

Displays ONLY public clues supplied via ``PublicClueView`` (normalized via
``normalize_clue_view``). Never computes clue regions, never evaluates SAT/DPLL,
and never reads unrevealed clues or ``puzzles/*.json``.

Visual Design (Cream Detective Editorial):
    - Unified Soft Ivory (#FBF7F0) Evidence Cards with single 1px hairline border.
    - Production 8-icon Vietnamese RGBA clue badges (512x512 cached via PixmapLoader,
      rendered crisply at 52x52 with High-DPI awareness and zero dark box frame).
    - Custom-painted circular archival check toggle replacing unstyled system QCheckBox.
    - Compact non-stretching inline reference chips (zero height jump on selection).
    - Distinct Evidence Blue (#5B7FA3) selected rail — never Crimson error styling.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import Property, QAbstractAnimation, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
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
from src.gui.animations.motion_tokens import EASE_OUT, EASE_SOFT, STAGGER_STACK_MS, build_easing
from src.gui.asset_registry import VIETNAMESE_CLUE_LABELS
from src.gui.components.styled_panel import StyledPanel
from src.gui.resources.pixmap_loader import PixmapLoader, default_pixmap_loader
from src.gui.styles.tokens import COLORS, SPACING
from src.gui.view_models import PublicClueView, normalize_clue_view

_CLUE_TYPE_DESCRIPTIONS_VI: dict[str, str] = {
    "FACT": "SỰ THẬT · Xác định trực tiếp",
    "SAME": "CÙNG PHE · Hai nghi phạm cùng trạng thái",
    "DIFFERENT": "KHÁC PHE · Hai nghi phạm khác trạng thái",
    "EXACTLY": "CHÍNH XÁC · Đúng k tội phạm",
    "AT_LEAST": "ÍT NHẤT · Ít nhất k tội phạm",
    "AT_MOST": "NHIỀU NHẤT · Không quá k tội phạm",
    "PARITY": "CHẴN / LẺ · Ràng buộc chẵn hoặc lẻ",
    "COUNT_COMPARE": "SO SÁNH SỐ LƯỢNG · So sánh hai nhóm",
    "IMPLIES": "ĐIỀU KIỆN · Nếu vế trước đúng thì vế sau đúng",
}


class _UsedToggleBox(QCheckBox):
    """Editorial circular checkmark toggle (replaces unstyled dark QCheckBox square).

    Preserves 100% ``QCheckBox`` semantics (``click()``, ``toggle()``,
    ``isChecked()``, ``setChecked()``, ``toggled`` signal) while painting a
    crisp, DPI-independent vector circle + checkmark matching Cream Editorial.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hovered = False
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(3.0, 3.0, self.width() - 6.0, self.height() - 6.0)
        checked = self.isChecked()
        enabled = self.isEnabled()

        if checked:
            fill = QColor(COLORS.evidence_teal if enabled else COLORS.ink_disabled)
            border = QColor(COLORS.paper_innocent if enabled else COLORS.paper_border_strong)
        elif self._hovered and enabled:
            fill = QColor(COLORS.paper_beige)
            border = QColor(COLORS.ink_primary)
        else:
            fill = QColor(COLORS.paper_sheet)
            border = QColor(COLORS.paper_border_strong if enabled else COLORS.paper_border)

        painter.setPen(QPen(border, 1.5))
        painter.setBrush(fill)
        painter.drawEllipse(rect)

        if checked or (self._hovered and enabled):
            check_color = QColor(COLORS.paper_sheet) if checked else QColor(COLORS.ink_secondary)
            if not checked:
                check_color.setAlpha(115)
            path = QPainterPath()
            cx = self.width() * 0.5
            cy = self.height() * 0.5
            path.moveTo(QPointF(cx - 4.0, cy + 0.2))
            path.lineTo(QPointF(cx - 1.2, cy + 3.0))
            path.lineTo(QPointF(cx + 4.4, cy - 3.0))
            pen = QPen(check_color, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        if self.hasFocus() and enabled:
            focus_pen = QPen(QColor(COLORS.focus_ring), 1.8)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(-2.0, -2.0, 2.0, 2.0))

        painter.end()


class _ClueCardItem(QFrame):
    """Single clickable Evidence Card rendered inside ``CluePanel``."""

    clicked = Signal(str)
    hovered = Signal(str)
    hover_left = Signal(str)
    used_toggled = Signal(str, bool)

    ICON_SIZE = QSize(52, 52)

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
        self.setProperty("used", "false")
        self.setProperty("interactive", "true" if self._interactive else "false")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._interactive
            else Qt.CursorShape.ArrowCursor
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        type_hint = _CLUE_TYPE_DESCRIPTIONS_VI.get(clue.clue_type, clue.clue_type)
        self.setToolTip(
            f"{clue.clue_id} [{type_hint}]\n"
            f"Chủ manh mối: Ô {clue.owner_id}\n"
            f"{clue.text}"
        )
        self.setAccessibleName(
            f"Manh mối {clue.clue_id} từ ô {clue.owner_id}. "
            "Nhấn Enter để xem các ô liên quan, nhấp đúp để đánh dấu đã dùng."
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # Left: 52x52 transparent Vietnamese RGBA clue icon (no dark enclosing box)
        self._icon_label = QLabel(self)
        self._icon_label.setProperty("widgetKind", "clueIconFrame")
        self._icon_label.setFixedSize(self.ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._used_fallback_icon = False

        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        scaled_icon = pixmap_loader.load_clue_icon_scaled(
            clue.clue_type,
            self.ICON_SIZE,
            device_pixel_ratio=dpr,
            prefer_vietnamese=True,
        )
        if scaled_icon is not None and not scaled_icon.isNull():
            self._icon_label.setPixmap(scaled_icon)
        else:
            self._used_fallback_icon = True
            self._icon_label.setProperty("widgetKind", "clueFallbackBadge")
            short_code = "⇒" if clue.clue_type == "IMPLIES" else (clue.clue_type[:4] if clue.clue_type else "?")
            self._icon_label.setText(short_code)
            self._icon_label.setToolTip(f"Biểu tượng dự phòng cho loại manh mối: {clue.clue_type}")

        root.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)

        # Center: Structured editorial hierarchy (Owner + Type Caption -> Description -> Chips)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)

        # Hidden backward-compatible metadata labels
        self._id_label = QLabel(clue.clue_id, self)
        self._id_label.setTextFormat(Qt.TextFormat.PlainText)
        self._id_label.setProperty("role", "paperMono")
        self._id_label.setVisible(False)

        self._type_pill = QLabel(clue.clue_type, self)
        self._type_pill.setTextFormat(Qt.TextFormat.PlainText)
        self._type_pill.setProperty("widgetKind", "clueTypePill")
        self._type_pill.setVisible(False)

        # Top row: Owner title + Editorial circular check toggle
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(1)

        self._owner_label = QLabel(f"Manh mối từ ô {clue.owner_id}", self)
        self._owner_label.setTextFormat(Qt.TextFormat.PlainText)
        self._owner_label.setProperty("role", "paperSubheading")
        title_stack.addWidget(self._owner_label)

        vi_label = VIETNAMESE_CLUE_LABELS.get(clue.clue_type)
        type_caption_text = vi_label if vi_label else clue.clue_type
        self._type_caption = QLabel(type_caption_text, self)
        self._type_caption.setTextFormat(Qt.TextFormat.PlainText)
        self._type_caption.setProperty("widgetKind", "clueTypeCaption")
        title_stack.addWidget(self._type_caption)

        top_row.addLayout(title_stack, 1)

        self.used_button = _UsedToggleBox(self)
        self.used_button.setToolTip("Đánh dấu đã dùng xong (hoặc nhấp đúp manh mối)")
        self.used_button.setAccessibleName(f"Đánh dấu đã dùng xong {clue.clue_id}")
        self.used_button.toggled.connect(self._set_used)
        top_row.addWidget(self.used_button, 0, Qt.AlignmentFlag.AlignTop)

        col.addLayout(top_row)

        # Main clue statement (full word wrap, never truncated/ellipsized)
        self._text_label = QLabel(clue.text, self)
        self._text_label.setTextFormat(Qt.TextFormat.PlainText)
        self._text_label.setProperty("role", "paperBody")
        self._text_label.setWordWrap(True)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        col.addWidget(self._text_label)

        # Compact inline reference chips (always stable height — zero layout jump on select)
        self._chips = QWidget(self)
        self._chips.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        chips_vbox = QVBoxLayout(self._chips)
        chips_vbox.setContentsMargins(0, 3, 0, 0)
        chips_vbox.setSpacing(4)

        chip_specs: list[tuple[str, str]] = [(lbl, "reference") for lbl in clue.reference_labels]
        comparative = clue.clue_type in {"SAME", "DIFFERENT", "COUNT_COMPARE", "IMPLIES"}
        for index, cid in enumerate(clue.referenced_cells[:8]):
            secondary = cid in clue.secondary_cells or (not clue.primary_cells and index > 0)
            if comparative:
                label_text = f"{'Đối chiếu' if secondary else 'Chính'} {cid}"
                role = "reference" if secondary else "primary"
            else:
                label_text = f"Ô {cid}"
                role = "primary" if (cid in clue.primary_cells or not clue.primary_cells) else "reference"
            chip_specs.append((label_text, role))
        if len(clue.referenced_cells) > 8:
            chip_specs.append((f"+{len(clue.referenced_cells) - 8} ô · di chuột để xem", "reference"))

        # Pack compactly in rows of up to 3 chips with trailing stretch (never stretches full-width)
        row_limit = 3
        for row_start in range(0, len(chip_specs), row_limit):
            chip_row = QHBoxLayout()
            chip_row.setContentsMargins(0, 0, 0, 0)
            chip_row.setSpacing(5)
            for badge_text, chip_role in chip_specs[row_start : row_start + row_limit]:
                chip = QLabel(badge_text, self._chips)
                chip.setTextFormat(Qt.TextFormat.PlainText)
                chip.setProperty("widgetKind", "evidenceChip")
                chip.setProperty("chipRole", chip_role)
                chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
                chip_row.addWidget(chip, 0)
            chip_row.addStretch(1)
            chips_vbox.addLayout(chip_row)

        self._chips.setVisible(bool(chip_specs))
        col.addWidget(self._chips)

        root.addLayout(col, 1)

        # Pure-QPainter evidence-blue sheen glide (zero QGraphicsOpacityEffect flicker)
        self._arrival_sweep: float = 1.0
        self._sweep_anim = QPropertyAnimation(self, b"arrival_sweep", self)
        self._sweep_anim.setDuration(DEFAULT_MOTION.scaled_ms(500))
        self._sweep_anim.setEasingCurve(build_easing(EASE_SOFT))

    def _get_arrival_sweep(self) -> float:
        return self._arrival_sweep

    def _set_arrival_sweep(self, value: float) -> None:
        self._arrival_sweep = max(0.0, min(1.0, float(value)))
        self.update()

    arrival_sweep = Property(float, _get_arrival_sweep, _set_arrival_sweep)

    def trigger_glide_sheen(self, *, reduced_motion: bool = False) -> None:
        if reduced_motion:
            self._sweep_anim.stop()
            self._arrival_sweep = 1.0
            self.update()
            return
        self._sweep_anim.stop()
        self._arrival_sweep = 0.0
        self._sweep_anim.setStartValue(0.0)
        self._sweep_anim.setEndValue(1.0)
        self._sweep_anim.start()

    def stop_glide_sheen(self) -> None:
        if self._sweep_anim.state() != QAbstractAnimation.State.Stopped:
            self._sweep_anim.stop()
        if self._arrival_sweep != 1.0:
            self._arrival_sweep = 1.0
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        t = self._arrival_sweep
        if t >= 0.995:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = float(self.width())
        h = float(self.height())
        fade = 1.0 - t
        cx = -0.30 * w + t * 1.60 * w
        grad = QLinearGradient(cx - 0.28 * w, 0.0, cx + 0.28 * w, h * 0.22)
        grad.setColorAt(0.0, QColor(91, 128, 155, 0))
        grad.setColorAt(0.5, QColor(115, 162, 198, int(46 * fade)))
        grad.setColorAt(1.0, QColor(91, 128, 155, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(QRectF(2.0, 2.0, max(0.0, w - 4.0), max(0.0, h - 4.0)), 8.0, 8.0)
        painter.end()

    def _set_used(self, used: bool) -> None:
        self.setProperty("used", "true" if used else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._text_label.setStyleSheet(
            f"color: {COLORS.ink_disabled}; text-decoration: line-through;" if used else ""
        )
        font = self._text_label.font()
        font.setStrikeOut(used)
        self._text_label.setFont(font)
        self.update()
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

    @property
    def type_caption_label(self) -> QLabel:
        return self._type_caption

    def set_selected(self, selected: bool) -> None:
        flag = bool(selected)
        if self._selected == flag:
            return
        self._selected = flag
        self.setProperty("selected", "true" if flag else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_interactive(self, enabled: bool) -> None:
        flag = bool(enabled)
        if self._interactive == flag:
            return
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

    def enterEvent(self, event):  # noqa: N802
        if self._interactive:
            self.hovered.emit(self._clue.clue_id)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.hover_left.emit(self._clue.clue_id)
        super().leaveEvent(event)

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


class _MagnifierHeaderIcon(QWidget):
    """Crisp vector antique-brass magnifying glass emblem for Bảng Chứng Cứ."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(26, 26)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Warm glass lens
        p.setBrush(QColor(238, 224, 192, 180))
        p.setPen(QPen(QColor("#8C6226"), 2.1))
        p.drawEllipse(QPointF(14.5, 10.5), 7.5, 7.5)
        # Subtle lens highlight arc
        p.setPen(QPen(QColor(255, 252, 240, 210), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(9.5, 5.5, 10.0, 10.0), 100 * 16, 75 * 16)
        # Dark walnut handle
        p.setPen(QPen(QColor("#5C3C16"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(9.0, 16.0), QPointF(3.5, 22.0))
        p.end()


class CluePanel(StyledPanel):
    """Scrollable Evidence Ledger displaying ONLY public clues supplied by Controller."""

    clue_selected = Signal(str)
    clue_hovered = Signal(str)
    clue_hover_left = Signal(str)
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
            decorative_texture=False,
            accent_bar=None,
            pixmap_loader=self._pixmap_loader,
            parent=parent,
        )
        self.setObjectName("CluePanel")
        self.set_header_icon(_MagnifierHeaderIcon(self))
        if self.title_label is not None:
            self.title_label.setStyleSheet(
                "color: #162436; font-family: Georgia, serif; font-size: 18px; "
                "font-weight: 800; font-style: italic; background: transparent;"
            )
        self.setStyleSheet(
            "QFrame#CluePanel {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCF6E9, stop:1 #F4E9D2);"
            "  border: 1.5px solid #C9AC78;"
            "  border-radius: 9px;"
            "}"
        )
        self.content_layout.setSpacing(SPACING.space_2)

        from src.gui.components.global_clue_card import GlobalClueCard
        self.global_card = GlobalClueCard(self)
        self.global_card.clicked.connect(self._on_card_clicked)
        self.global_card.hovered.connect(self.clue_hovered)
        self.global_card.hover_left.connect(self.clue_hover_left)
        self.content_layout.addWidget(self.global_card)

        self._clues: list[PublicClueView] = []
        self._cards_by_id: dict[str, _ClueCardItem] = {}
        self._selected_clue_id: Optional[str] = None
        self._interactive: bool = True
        self._auto_solving: bool = False
        self._used_clues: set[str] = set()
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)
        self._entry_anims: list[QPropertyAnimation] = []

        # Compact calm Auto-Solve indicator strip (shows active clues without scrolling the list)
        self._active_strip = QLabel("", self)
        self._active_strip.setTextFormat(Qt.TextFormat.PlainText)
        self._active_strip.setProperty("widgetKind", "activeEvidenceStrip")
        self._active_strip.setFixedHeight(26)
        self._active_strip.setVisible(False)
        self.content_layout.addWidget(self._active_strip)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setMinimumHeight(110)

        self._list_host = QWidget(self._scroll_area)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 2, 4, 2)
        self._list_layout.setSpacing(8)

        self._empty_label = QLabel(
            "Chưa có manh mối công khai.\nHãy lật thẻ hoặc nạp vụ án để mở chứng cứ.",
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

        self.global_card.set_clues([c for c in normalized if c.scope == "ALL"])

        prev_selected = self._selected_clue_id
        prev_ids = {c.clue_id for c in self._clues}

        # Incremental update path: when existing clues are an unchanged prefix of the
        # incoming list (normal gameplay & Auto-Solve), preserve every existing card
        # widget in-place to eliminate full-panel destroy/rebuild flicker & scroll jumps.
        is_incremental_append = (
            len(normalized) >= len(self._clues)
            and len(self._clues) == len(self._cards_by_id)
            and all(old == new for old, new in zip(self._clues, normalized))
        )

        new_cards: list[_ClueCardItem] = []
        if is_incremental_append:
            appended = normalized[len(self._clues) :]
            if appended:
                self._clues = normalized
                for clue in appended:
                    new_cards.append(self._insert_card_widget(clue))
                self._sync_empty_and_subtitle()
                if prev_ids:
                    self._animate_new_cards(new_cards)
            return

        self._clear_cards_only()
        self._clues = normalized

        for clue in self._clues:
            card = self._insert_card_widget(clue)
            if clue.clue_id not in prev_ids:
                new_cards.append(card)

        self._sync_empty_and_subtitle()

        if prev_selected is not None and prev_selected in self._cards_by_id:
            self._selected_clue_id = prev_selected
            self._cards_by_id[prev_selected].set_selected(True)
        else:
            self._selected_clue_id = None

        if new_cards and prev_ids:
            self._animate_new_cards(new_cards)

    def add_or_update_clue(self, raw_clue: Any) -> None:
        """Append a newly revealed public clue or refresh an existing entry."""
        clue = normalize_clue_view(raw_clue)
        if clue.clue_id in self._cards_by_id:
            updated = [clue if c.clue_id == clue.clue_id else c for c in self._clues]
            self.set_clues(updated)
            return
        self._clues.append(clue)
        self.global_card.set_clues([c for c in self._clues if c.scope == "ALL"])
        card = self._insert_card_widget(clue)
        self._sync_empty_and_subtitle()
        self._animate_new_cards([card])

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            self._stop_entry_anims()

    def clear(self) -> None:
        """Remove all clue cards and reset selection."""
        self._clear_cards_only()
        self._clues = []
        self.global_card.set_clues([])
        self._selected_clue_id = None
        self._used_clues.clear()
        self._auto_solving = False
        self._active_strip.setText("")
        self._active_strip.setVisible(False)
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
                if card.is_selected:
                    card.set_selected(False)
            self._selected_clue_id = None
            return True

        target = self._cards_by_id.get(clue_id)
        if target is None:
            return False

        for cid, card in self._cards_by_id.items():
            should_select = cid == clue_id
            if card.is_selected != should_select:
                card.set_selected(should_select)
        self._selected_clue_id = clue_id
        self._ensure_card_visible_smooth(target)
        return True

    def set_auto_solving(self, running: bool) -> None:
        """Toggle Calm Auto-Solve mode: keeps list steady and displays active clues in header strip."""
        flag = bool(running)
        if self._auto_solving == flag:
            return
        self._auto_solving = flag
        self.global_card.set_interactive(self._interactive and not flag)
        if flag:
            if not self._active_strip.text():
                self._active_strip.setText("Đang phân tích chứng cứ...")
            self._active_strip.setVisible(True)
        else:
            self._active_strip.setVisible(False)

    def set_evidence_clues(self, clue_ids: Iterable[str]) -> None:
        ids = tuple(cid for cid in clue_ids if cid in self._cards_by_id)
        id_set = set(ids)
        newly_selected: list[_ClueCardItem] = []
        for cid, card in self._cards_by_id.items():
            should_select = cid in id_set
            if card.is_selected != should_select:
                card.set_selected(should_select)
                if should_select:
                    newly_selected.append(card)
        self._selected_clue_id = ids[0] if ids else None
        if ids:
            owners = ", ".join(self._cards_by_id[cid].clue.owner_id for cid in ids)
            self._active_strip.setText(f"Đang dùng: {owners}")
            # Glide smoothly to frame the primary evidence card (velvet EASE_SOFT scroll)
            self._ensure_card_visible_smooth(self._cards_by_id[ids[0]])
            if self.isVisible():
                for card in newly_selected[:3]:
                    card.trigger_glide_sheen(reduced_motion=self._reduced_motion)
        elif self._auto_solving:
            self._active_strip.setText("Đang phân tích chứng cứ...")

    def _ensure_card_visible_smooth(self, card: _ClueCardItem) -> None:
        """Glide smoothly to center ``card`` in the viewport when it is outside comfortable bounds."""
        vp = self._scroll_area.viewport()
        bar = self._scroll_area.verticalScrollBar()
        if vp is None or bar.maximum() <= 0:
            return
        card_top = card.y()
        card_bottom = card_top + card.height()
        view_top = bar.value()
        view_bottom = view_top + vp.height()
        margin = 14
        if card_top >= view_top + margin and card_bottom <= view_bottom - margin:
            return
        # Center the target card smoothly inside the viewport for a calm, flowing glide
        card_center = card_top + card.height() // 2
        target_val = max(0, min(bar.maximum(), card_center - vp.height() // 2))
        if target_val == bar.value():
            return
        if self._reduced_motion or not self.isVisible():
            bar.setValue(target_val)
            return
        existing = getattr(self, "_scroll_anim", None)
        if existing is not None and existing.state() == QAbstractAnimation.State.Running:
            existing.stop()
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(DEFAULT_MOTION.scaled_ms(440))
        anim.setStartValue(bar.value())
        anim.setEndValue(target_val)
        anim.setEasingCurve(build_easing(EASE_SOFT))
        self._scroll_anim = anim
        anim.start()

    def set_interactive(self, enabled: bool) -> None:
        """Enable or lock user clue selection (e.g. during PROCESSING/ANIMATING)."""
        flag = bool(enabled)
        self.global_card.set_interactive(flag and not self._auto_solving)
        if self._interactive == flag:
            return
        self._interactive = flag
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

    def _insert_card_widget(self, clue: PublicClueView) -> _ClueCardItem:
        card = _ClueCardItem(
            clue,
            pixmap_loader=self._pixmap_loader,
            interactive=self._interactive,
            parent=self._list_host,
        )
        card.clicked.connect(self._on_card_clicked)
        card.hovered.connect(self.clue_hovered)
        card.hover_left.connect(self.clue_hover_left)
        card.set_used(clue.clue_id in self._used_clues)
        card.used_toggled.connect(self._on_usage_changed)
        # Insert right before trailing stretch item
        insert_idx = max(0, self._list_layout.count() - 1)
        self._list_layout.insertWidget(insert_idx, card)
        self._cards_by_id[clue.clue_id] = card
        return card

    def _animate_new_cards(self, cards: list[_ClueCardItem]) -> None:
        """Apply pure-QPainter evidence-blue sheen glide to newly revealed clue cards."""
        if not self.isVisible():
            return
        for card in cards[:4]:
            card.trigger_glide_sheen(reduced_motion=self._reduced_motion)

    def _stop_entry_anims(self) -> None:
        for anim in list(self._entry_anims):
            try:
                if anim.state() != QAbstractAnimation.State.Stopped:
                    anim.stop()
            except RuntimeError:
                pass
        self._entry_anims.clear()
        for card in self._cards_by_id.values():
            try:
                card.stop_glide_sheen()
                card.setGraphicsEffect(None)
            except RuntimeError:
                pass

    def _clear_cards_only(self) -> None:
        self._stop_entry_anims()
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
                self.subtitle_label.setText(f"{count} manh mối công khai · Nhấp để xem các ô liên quan")

    def _on_card_clicked(self, clue_id: str) -> None:
        if not self._interactive or clue_id not in self._cards_by_id:
            return
        if self._selected_clue_id == clue_id:
            self.set_selected_clue(None)
            self.focus_cleared.emit()
            return
        self.set_selected_clue(clue_id)
        self.clue_selected.emit(clue_id)
