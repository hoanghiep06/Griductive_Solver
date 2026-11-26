"""DeductionPanel — Investigation Notebook Timeline & Compact Collapsible Hint UI.

Renders ONLY accepted deduction steps supplied via ``DeductionStepView`` and
temporary non-mutating hints supplied via ``HintView``.
Never runs DPLL, never fabricates proof steps, and preserves strict separation
between accepted deduction history and temporary hints per
``docs/STAGE2_API_CONTRACT.md`` §D.

Visual Design (Cream Detective Editorial):
    - Investigation Notebook Timeline with warm-brass vertical rail and crisp
      ink-navy circular step markers (01, 02, ...) separated by thin hairlines.
    - Truthful step labels derived strictly from DTO data (never fabricates
      Hypothesis / Contradiction steps when the Agent does not provide them).
    - Compact collapsible Hint strip on warm beige with brass accent rail,
      expand/collapse detail control, and dismiss button (never an oversized
      yellow debug box).
    - Purposeful compact empty state with vector notebook glyph.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import Property, QAbstractAnimation, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import EASE_OUT, EASE_SOFT, build_easing
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import COLORS, SPACING, TYPOGRAPHY
from src.gui.view_models import (
    DeductionStepView,
    HintView,
    normalize_deduction_step,
    normalize_hint_view,
)


def _format_clue_ref(clue_id: str) -> str:
    """Format a clue ID for readable notebook display by stripping technical 'CLUE_' prefix."""
    cleaned = clue_id.strip()
    if cleaned.upper().startswith("CLUE_") and len(cleaned) > 5:
        return cleaned[5:]
    return cleaned


class _TimelineRailMarker(QWidget):
    """Vertical warm-brass timeline line + circular ink-navy step number marker."""

    def __init__(
        self,
        step_number: int,
        *,
        is_first: bool = False,
        is_last: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._step_number = step_number
        self._is_first = is_first
        self._is_last = is_last
        self.setFixedWidth(28)
        self.setMinimumHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_position_flags(self, *, is_first: bool, is_last: bool) -> None:
        if self._is_first != is_first or self._is_last != is_last:
            self._is_first = is_first
            self._is_last = is_last
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx = self.width() * 0.5
        cy = 15.0
        radius = 10.5
        rail_pen = QPen(QColor(COLORS.brass_accent), 1.5)
        painter.setPen(rail_pen)

        # Upper connector segment
        if not self._is_first:
            painter.drawLine(QPointF(cx, 0.0), QPointF(cx, cy - radius))
        # Lower connector segment
        if not self._is_last and self.height() > cy + radius:
            painter.drawLine(QPointF(cx, cy + radius), QPointF(cx, float(self.height())))

        # Circular Ink Navy step badge with subtle brass perimeter
        circle_rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)
        painter.setPen(QPen(QColor(COLORS.brass_accent), 1.2))
        painter.setBrush(QColor(COLORS.ink_primary))
        painter.drawEllipse(circle_rect)

        font = QFont(TYPOGRAPHY.font_family_mono[0])
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(COLORS.paper_sheet))
        painter.drawText(circle_rect, Qt.AlignmentFlag.AlignCenter, f"{self._step_number:02d}")
        painter.end()


class _NotebookEmptyGlyph(QWidget):
    """Minimal vector investigation notebook glyph for the Deduction empty state."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(34, 34)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        book = QRectF(6.0, 4.0, 22.0, 26.0)
        painter.setPen(QPen(QColor(COLORS.paper_border_strong), 1.5))
        painter.setBrush(QColor(COLORS.paper_canvas))
        painter.drawRoundedRect(book, 3.0, 3.0)

        # Brass spine accent
        painter.setPen(QPen(QColor(COLORS.brass_accent), 2.2))
        painter.drawLine(QPointF(10.0, 5.5), QPointF(10.0, 28.5))

        # Ruled notebook lines
        painter.setPen(QPen(QColor(COLORS.ink_disabled), 1.2))
        for y in (11.5, 16.5, 21.5):
            painter.drawLine(QPointF(13.5, y), QPointF(24.0, y))
        painter.end()


class _HintIconGlyph(QWidget):
    """Subtle vector investigation note/lamp glyph for the compact Hint strip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(COLORS.brass_ink), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Minimal bulb outline + base line
        painter.drawEllipse(QRectF(4.0, 2.0, 10.0, 10.0))
        painter.drawLine(QPointF(6.5, 14.5), QPointF(11.5, 14.5))
        painter.drawLine(QPointF(7.5, 16.5), QPointF(10.5, 16.5))
        painter.end()


class _TraceEntryCard(QFrame):
    """Single Investigation Notebook timeline entry for one accepted deduction step."""

    def __init__(
        self,
        step_index: int,
        step: DeductionStepView,
        *,
        is_first: bool = False,
        is_last: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._step_index = step_index
        self._step = step

        if step.verdict == "CRIMINAL":
            tone_prop = "criminal"
            badge_text = "TỘI PHẠM"
            badge_tone = "danger"
        elif step.verdict == "INNOCENT":
            tone_prop = "innocent"
            badge_text = "VÔ TỘI"
            badge_tone = "success"
        else:
            tone_prop = "unknown"
            badge_text = "CHƯA XÁC ĐỊNH"
            badge_tone = "neutral"

        self.setProperty("widgetKind", "traceEntry")
        self.setProperty("verdictTone", tone_prop)
        self.setProperty("isLast", "true" if is_last else "false")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        root = QHBoxLayout(self)
        root.setContentsMargins(2, 6, 4, 10)
        root.setSpacing(10)

        display_num = step.step if step.step is not None else step_index
        self._rail = _TimelineRailMarker(
            display_num,
            is_first=is_first,
            is_last=is_last,
            parent=self,
        )
        root.addWidget(self._rail, 0)

        body_col = QVBoxLayout()
        body_col.setContentsMargins(0, 1, 0, 0)
        body_col.setSpacing(4)

        # Header: KẾT LUẬN · Ô <cell_id>  [CRIMINAL / INNOCENT]
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)

        self._kind_label = QLabel(f"BƯỚC {display_num:02d} · KẾT LUẬN", self)
        self._kind_label.setTextFormat(Qt.TextFormat.PlainText)
        self._kind_label.setProperty("widgetKind", "timelineStepType")
        title_col.addWidget(self._kind_label)

        self._step_label = QLabel(f"Ô {step.cell_id}", self)
        self._step_label.setTextFormat(Qt.TextFormat.PlainText)
        self._step_label.setProperty("role", "paperSubheading")
        title_col.addWidget(self._step_label)

        header.addLayout(title_col, 1)

        self._verdict_badge = StatusLabel(badge_text, tone=badge_tone, parent=self)
        self._verdict_badge.setProperty("widgetKind", "timelineVerdictBadge")
        self._verdict_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self._verdict_badge, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        body_col.addLayout(header)

        # Plain-text explanation from DTO
        self._explanation_label = QLabel(step.explanation, self)
        self._explanation_label.setTextFormat(Qt.TextFormat.PlainText)
        self._explanation_label.setProperty("role", "paperBody")
        self._explanation_label.setWordWrap(True)
        self._explanation_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        body_col.addWidget(self._explanation_label)

        # Compact evidence metadata line (only genuine DTO references)
        meta_parts: list[str] = []
        if step.source_clue_ids:
            refs = ", ".join(_format_clue_ref(cid) for cid in step.source_clue_ids)
            meta_parts.append(f"Căn cứ: {refs}")
        if step.newly_revealed_clue_id:
            meta_parts.append(f"Mở mới: {_format_clue_ref(step.newly_revealed_clue_id)}")

        if meta_parts:
            self._meta_label = QLabel(" · ".join(meta_parts), self)
            self._meta_label.setTextFormat(Qt.TextFormat.PlainText)
            self._meta_label.setProperty("role", "paperCaption")
            self._meta_label.setWordWrap(True)
            self._meta_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            body_col.addWidget(self._meta_label)
        else:
            self._meta_label = None

        root.addLayout(body_col, 1)

        # Pure-QPainter warm-brass arrival glide (zero QGraphicsOpacityEffect flicker)
        self._arrival_sweep: float = 1.0
        self._sweep_anim = QPropertyAnimation(self, b"arrival_sweep", self)
        self._sweep_anim.setDuration(DEFAULT_MOTION.scaled_ms(520))
        self._sweep_anim.setEasingCurve(build_easing(EASE_SOFT))

    def _get_arrival_sweep(self) -> float:
        return self._arrival_sweep

    def _set_arrival_sweep(self, value: float) -> None:
        self._arrival_sweep = max(0.0, min(1.0, float(value)))
        self.update()

    arrival_sweep = Property(float, _get_arrival_sweep, _set_arrival_sweep)

    def trigger_arrival_glide(self, *, reduced_motion: bool = False) -> None:
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

    def stop_arrival_glide(self) -> None:
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
        # Soft warm-brass highlight wash that glides left-to-right and melts away
        fade = 1.0 - t
        band_x = -0.35 * w + t * 1.70 * w
        grad = QLinearGradient(band_x - 0.30 * w, 0.0, band_x + 0.30 * w, h * 0.25)
        grad.setColorAt(0.0, QColor(185, 149, 96, 0))
        grad.setColorAt(0.5, QColor(205, 168, 108, int(44 * fade)))
        grad.setColorAt(1.0, QColor(185, 149, 96, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(QRectF(2.0, 2.0, max(0.0, w - 4.0), max(0.0, h - 4.0)), 6.0, 6.0)
        painter.end()

    def set_timeline_position(self, *, is_first: bool, is_last: bool) -> None:
        self._rail.set_position_flags(is_first=is_first, is_last=is_last)
        flag = "true" if is_last else "false"
        if self.property("isLast") != flag:
            self.setProperty("isLast", flag)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    @property
    def step(self) -> DeductionStepView:
        return self._step

    @property
    def step_index(self) -> int:
        return self._step_index

    @property
    def verdict_badge(self) -> StatusLabel:
        return self._verdict_badge


class _HintBox(QFrame):
    """Compact collapsible Hint strip kept strictly separate from Deduction Timeline."""

    _SUMMARY_MAX_CHARS = 92
    _COMPACT_BODY_HEIGHT = 40

    def __init__(self, *, on_dismiss, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DeductionHintBox")
        self.setProperty("widgetKind", "hintBox")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self._current_hint: Optional[HintView] = None
        self._expanded: bool = False
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Compact Header: [Icon] GỢI Ý ĐIỀU TRA · Ô E1   [VERDICT?] [Xem chi tiết] [Ẩn]
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self._icon = _HintIconGlyph(self)
        header.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self._title_label = QLabel("GỢI Ý ĐIỀU TRA", self)
        self._title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._title_label.setProperty("role", "paperMono")
        header.addWidget(self._title_label, 1)

        self._verdict_pill = StatusLabel("GỢI Ý", tone="paperAccent", parent=self)
        self._verdict_pill.setProperty("widgetKind", "timelineVerdictBadge")
        self._verdict_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._verdict_pill.setVisible(False)
        header.addWidget(self._verdict_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        self._toggle_btn = QPushButton("Xem chi tiết", self)
        self._toggle_btn.setProperty("widgetKind", "hintActionBtn")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setToolTip("Mở rộng hoặc thu gọn nội dung gợi ý đầy đủ")
        self._toggle_btn.clicked.connect(self.toggle_expanded)
        header.addWidget(self._toggle_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._dismiss_btn = QPushButton("Ẩn", self)
        self._dismiss_btn.setProperty("widgetKind", "hintActionBtn")
        self._dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_btn.setToolTip("Ẩn gợi ý hiện tại")
        self._dismiss_btn.clicked.connect(on_dismiss)
        header.addWidget(self._dismiss_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        # Summary / full hint body text
        self._body_label = QLabel("", self)
        self._body_label.setTextFormat(Qt.TextFormat.PlainText)
        self._body_label.setProperty("role", "paperBody")
        self._body_label.setWordWrap(True)
        self._body_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._body_label.setFixedHeight(self._COMPACT_BODY_HEIGHT)
        self._body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._body_label)

        # Expandable detail container (public clue references, shown when expanded)
        self._detail_box = QWidget(self)
        detail_lay = QVBoxLayout(self._detail_box)
        detail_lay.setContentsMargins(0, 2, 0, 0)
        detail_lay.setSpacing(4)

        self._refs_label = QLabel("", self._detail_box)
        self._refs_label.setTextFormat(Qt.TextFormat.PlainText)
        self._refs_label.setProperty("role", "paperCaption")
        self._refs_label.setWordWrap(True)
        detail_lay.addWidget(self._refs_label)

        # Kept hidden in normal compact editorial layout (preserved for attribute compatibility)
        self._logic_chain = QLabel(
            "CHỨNG CỨ  →  PHÂN TÍCH  →  KẾT LUẬN",
            self._detail_box,
        )
        self._logic_chain.setProperty("widgetKind", "logicChain")
        self._logic_chain.setVisible(False)
        detail_lay.addWidget(self._logic_chain)

        self._detail_box.setVisible(False)
        layout.addWidget(self._detail_box)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._enter = QPropertyAnimation(self._opacity, b"opacity", self)
        self._enter.setDuration(DEFAULT_MOTION.scaled_ms(220))
        self._enter.setEasingCurve(build_easing(EASE_SOFT))

        # Subtle horizontal brass sheen sweep on in-place content updates (zero blink)
        self._sheen_progress: float = 1.0
        self._sheen_anim = QPropertyAnimation(self, b"sheen_progress", self)
        self._sheen_anim.setDuration(DEFAULT_MOTION.scaled_ms(480))
        self._sheen_anim.setEasingCurve(build_easing(EASE_SOFT))

        self.setVisible(False)

    def _get_sheen_progress(self) -> float:
        return self._sheen_progress

    def _set_sheen_progress(self, value: float) -> None:
        self._sheen_progress = max(0.0, min(1.0, float(value)))
        self.update()

    sheen_progress = Property(float, _get_sheen_progress, _set_sheen_progress)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        t = self._sheen_progress
        if t >= 0.995:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = float(self.width())
        h = float(self.height())
        fade = 1.0 - t
        cx = -0.25 * w + t * 1.50 * w
        grad = QLinearGradient(cx - 0.28 * w, 0.0, cx + 0.28 * w, h * 0.2)
        grad.setColorAt(0.0, QColor(214, 178, 114, 0))
        grad.setColorAt(0.5, QColor(214, 178, 114, int(52 * fade)))
        grad.setColorAt(1.0, QColor(214, 178, 114, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(QRectF(2.0, 2.0, max(0.0, w - 4.0), max(0.0, h - 4.0)), 6.0, 6.0)
        painter.end()

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    @property
    def toggle_button(self) -> QPushButton:
        return self._toggle_btn

    @property
    def dismiss_button(self) -> QPushButton:
        return self._dismiss_btn

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion:
            if self._enter.state() == QAbstractAnimation.State.Running:
                self._enter.stop()
                self._opacity.setOpacity(1.0)
            if self._sheen_anim.state() == QAbstractAnimation.State.Running:
                self._sheen_anim.stop()
                self._sheen_progress = 1.0
                self.update()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self._refresh_text_state()
        self.updateGeometry()

    def toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def display_hint(self, hint: HintView) -> None:
        was_visible = self.isVisible()
        self._current_hint = hint
        self._expanded = False  # Always start compact so timeline stays readable

        if hint.outcome == "FORCED" and hint.cell_id:
            if hint.verdict:
                self._title_label.setText(f"SUY LUẬN · Ô {hint.cell_id}")
                tone = "danger" if hint.verdict == "CRIMINAL" else "success"
                verdict_vi = "TỘI PHẠM" if hint.verdict == "CRIMINAL" else "VÔ TỘI"
                self._verdict_pill.set_status(verdict_vi, tone=tone)
                self._verdict_pill.setVisible(True)
            else:
                self._title_label.setText(f"GỢI Ý ĐIỀU TRA · Ô {hint.cell_id}")
                self._verdict_pill.setVisible(False)
        else:
            self._title_label.setText("GỢI Ý · CHƯA CÓ NƯỚC ĐI BẮT BUỘC")
            self._verdict_pill.setVisible(False)

        self._refresh_text_state()
        self.setVisible(True)
        # Only run opacity fade-in when entering from hidden; when already visible
        # (e.g., consecutive Auto-Solve steps), keep opacity 1.0 and glide a velvet sheen across.
        if self._reduced_motion:
            if self._enter.state() == QAbstractAnimation.State.Running:
                self._enter.stop()
            self._sheen_anim.stop()
            self._sheen_progress = 1.0
            self._opacity.setOpacity(1.0)
        elif was_visible:
            if self._enter.state() == QAbstractAnimation.State.Running:
                self._enter.stop()
            self._opacity.setOpacity(1.0)
            self._sheen_anim.stop()
            self._sheen_progress = 0.0
            self._sheen_anim.setStartValue(0.0)
            self._sheen_anim.setEndValue(1.0)
            self._sheen_anim.start()
        else:
            self._enter.stop()
            self._opacity.setOpacity(0.0)
            self._enter.setStartValue(0.0)
            self._enter.setEndValue(1.0)
            self._enter.start()
        self.updateGeometry()

    def clear_hint(self) -> None:
        self._current_hint = None
        self._expanded = False
        self._body_label.clear()
        self._refs_label.clear()
        self._detail_box.setVisible(False)
        self._verdict_pill.setVisible(False)
        self._enter.stop()
        self._opacity.setOpacity(1.0)
        self.setVisible(False)
        self.updateGeometry()

    def _refresh_text_state(self) -> None:
        hint = self._current_hint
        if hint is None:
            return

        full_text = hint.text.strip()
        has_refs = bool(hint.source_clue_ids)
        is_long = len(full_text) > self._SUMMARY_MAX_CHARS or "\n" in full_text
        needs_expand_control = is_long or has_refs
        self._toggle_btn.setVisible(needs_expand_control)

        if self._expanded:
            self._body_label.setMinimumHeight(0)
            self._body_label.setMaximumHeight(16777215)
            self._body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self._body_label.setText(full_text)
        else:
            # Lock compact body to exact 2-line height so Timeline below never jumps
            # when consecutive Auto-Solve explanations vary between 1 and 2 lines.
            self._body_label.setFixedHeight(self._COMPACT_BODY_HEIGHT)
            self._body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if not is_long:
                self._body_label.setText(full_text)
            else:
                first_line = full_text.splitlines()[0]
                if len(first_line) > self._SUMMARY_MAX_CHARS:
                    cut = first_line[: self._SUMMARY_MAX_CHARS].rsplit(" ", 1)[0]
                    summary = f"{cut}…"
                else:
                    summary = f"{first_line}…"
                self._body_label.setText(summary)

        if self._expanded and has_refs:
            refs = ", ".join(_format_clue_ref(cid) for cid in hint.source_clue_ids)
            self._refs_label.setText(f"Căn cứ công khai: {refs}")
            self._detail_box.setVisible(True)
        else:
            self._detail_box.setVisible(False)

        self._toggle_btn.setText("Thu gọn" if self._expanded else "Xem chi tiết")


class _NotebookHeaderIcon(QWidget):
    """Crisp vector vintage notebook & brass pencil icon for Nhật Ký Suy Luận."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(26, 26)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Spiral archival notepad
        p.setBrush(QColor("#F7ECD5"))
        p.setPen(QPen(QColor("#7A5828"), 1.6))
        p.drawRoundedRect(QRectF(4.0, 4.0, 15.0, 19.0), 2.5, 2.5)
        # Ruled lines
        p.setPen(QPen(QColor("#B69B6D"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for y in (9.5, 13.5, 17.5):
            p.drawLine(QPointF(7.2, y), QPointF(15.2, y))
        # Diagonal brass pencil
        p.setPen(QPen(QColor("#5C3D18"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(15.5, 16.5), QPointF(23.0, 7.5))
        p.setPen(QPen(QColor("#D6A852"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(16.2, 15.8), QPointF(22.2, 8.5))
        p.end()


class DeductionPanel(StyledPanel):
    """Investigation Notebook Timeline with smart auto-scroll & compact Hint strip."""

    hint_changed = Signal(object)

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Nhật Ký Suy Luận",
            subtitle="0 bước đã chứng minh",
            variant="paper",
            padding=SPACING.space_3,
            decorative_texture=False,
            accent_bar=None,
            parent=parent,
        )
        self.setObjectName("DeductionPanel")
        self.set_header_icon(_NotebookHeaderIcon(self))
        if self.title_label is not None:
            self.title_label.setStyleSheet(
                "color: #162436; font-family: Georgia, serif; font-size: 18px; "
                "font-weight: 800; font-style: italic; background: transparent;"
            )
        self.setStyleSheet(
            "QFrame#DeductionPanel {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FCF6E9, stop:1 #F4E9D2);"
            "  border: 1.5px solid #C9AC78;"
            "  border-radius: 9px;"
            "}"
        )
        self.content_layout.setSpacing(SPACING.space_2)

        self._steps: list[DeductionStepView] = []
        self._entry_widgets: list[_TraceEntryCard] = []
        self._seen_keys: set[tuple[str, int, str]] = set()
        self._current_hint: Optional[HintView] = None
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)
        self._scroll_anim: Optional[QPropertyAnimation] = None
        self._entry_anims: list[QPropertyAnimation] = []

        # Separate non-mutating collapsible Hint strip at top of panel
        self._hint_box = _HintBox(on_dismiss=self.clear_hint, parent=self)
        self.content_layout.addWidget(self._hint_box)

        # Scrollable Investigation Notebook Timeline
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setMinimumHeight(80)

        self._list_host = QWidget(self._scroll_area)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 2, 4, 2)
        self._list_layout.setSpacing(0)

        # Purposeful compact empty state with vector notebook glyph
        self._empty_container = QWidget(self._list_host)
        empty_lay = QVBoxLayout(self._empty_container)
        empty_lay.setContentsMargins(SPACING.space_3, SPACING.space_4, SPACING.space_3, SPACING.space_4)
        empty_lay.setSpacing(6)
        empty_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_glyph = _NotebookEmptyGlyph(self._empty_container)
        empty_lay.addWidget(self._empty_glyph, 0, Qt.AlignmentFlag.AlignCenter)

        self._empty_label = QLabel(
            "Chưa có bước suy luận nào.\nCác kết luận được chứng minh sẽ xuất hiện tại đây.",
            self._empty_container,
        )
        self._empty_label.setProperty("role", "paperCaption")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        empty_lay.addWidget(self._empty_label)

        self._list_layout.addWidget(self._empty_container)
        self._list_layout.addStretch(1)

        self._scroll_area.setWidget(self._list_host)
        self.content_layout.addWidget(self._scroll_area, 1)

    # ------------------------------------------------------------------
    # Public Trace API
    # ------------------------------------------------------------------

    def append_step(self, raw_step: Any) -> bool:
        """Append one accepted deduction step incrementally (idempotent by dedup_key)."""
        step = normalize_deduction_step(raw_step)
        if step.dedup_key in self._seen_keys:
            return False

        bar = self._scroll_area.verticalScrollBar()
        scrolling_to_bottom = (
            self._scroll_anim is not None
            and self._scroll_anim.state() == QAbstractAnimation.State.Running
        )
        was_at_bottom = scrolling_to_bottom or (bar.maximum() == 0) or (bar.value() >= bar.maximum() - 24)

        self._seen_keys.add(step.dedup_key)
        self._steps.append(step)
        card = self._append_entry_widget(len(self._steps), step)
        self._sync_empty_and_subtitle()
        self._animate_entry_card(card)

        if was_at_bottom:
            self._scroll_to_bottom()
        return True

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        self._hint_box.set_reduced_motion(self._reduced_motion)
        if self._reduced_motion:
            self._stop_entry_anims()
            if self._scroll_anim is not None and self._scroll_anim.state() == QAbstractAnimation.State.Running:
                self._scroll_anim.stop()

    def set_steps(self, steps: Iterable[Any]) -> None:
        """Replace the entire accepted deduction trace cleanly."""
        normalized: list[DeductionStepView] = []
        seen: set[tuple[str, int, str]] = set()
        for raw in steps:
            step = normalize_deduction_step(raw)
            if step.dedup_key in seen:
                continue
            seen.add(step.dedup_key)
            normalized.append(step)

        self._clear_entries_only()
        self._steps = normalized
        self._seen_keys = seen
        for idx, step in enumerate(self._steps, start=1):
            self._append_entry_widget(idx, step)
        self._sync_empty_and_subtitle()
        if self._steps:
            self._scroll_to_bottom()

    def clear(self) -> None:
        """Clear all accepted deduction trace steps (does not alter board)."""
        self._clear_entries_only()
        self._steps = []
        self._seen_keys.clear()
        self._sync_empty_and_subtitle()

    # ------------------------------------------------------------------
    # Public Hint API (Separate from Accepted Trace)
    # ------------------------------------------------------------------

    def show_hint(self, raw_hint: Any) -> None:
        """Display a temporary ``HintView`` in the dedicated Hint strip."""
        hint = normalize_hint_view(raw_hint)
        if hint == self._current_hint and self._hint_box.isVisible():
            return
        self._current_hint = hint
        self._hint_box.display_hint(hint)
        self.hint_changed.emit(hint)

    def clear_hint(self) -> None:
        """Hide and clear the temporary Hint strip."""
        self._current_hint = None
        self._hint_box.clear_hint()
        self.hint_changed.emit(None)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def steps(self) -> tuple[DeductionStepView, ...]:
        return tuple(self._steps)

    @property
    def step_count(self) -> int:
        return len(self._steps)

    @property
    def entry_widgets(self) -> tuple[_TraceEntryCard, ...]:
        return tuple(self._entry_widgets)

    @property
    def current_hint(self) -> Optional[HintView]:
        return self._current_hint

    @property
    def hint_box(self) -> _HintBox:
        return self._hint_box

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    @property
    def is_empty(self) -> bool:
        return len(self._steps) == 0

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _append_entry_widget(self, idx: int, step: DeductionStepView) -> _TraceEntryCard:
        is_first = len(self._entry_widgets) == 0
        if self._entry_widgets:
            prev = self._entry_widgets[-1]
            prev.set_timeline_position(is_first=(len(self._entry_widgets) == 1), is_last=False)

        card = _TraceEntryCard(
            idx,
            step,
            is_first=is_first,
            is_last=True,
            parent=self._list_host,
        )
        insert_idx = max(0, self._list_layout.count() - 1)
        self._list_layout.insertWidget(insert_idx, card)
        self._entry_widgets.append(card)
        return card

    def _animate_entry_card(self, card: _TraceEntryCard) -> None:
        # Pure-QPainter warm-brass glide (zero QGraphicsOpacityEffect X11 flicker)
        if not self.isVisible():
            return
        card.trigger_arrival_glide(reduced_motion=self._reduced_motion)

    def _stop_entry_anims(self) -> None:
        for anim in list(self._entry_anims):
            try:
                if anim.state() != QAbstractAnimation.State.Stopped:
                    anim.stop()
            except RuntimeError:
                pass
        self._entry_anims.clear()
        for card in self._entry_widgets:
            try:
                card.stop_arrival_glide()
                card.setGraphicsEffect(None)
            except RuntimeError:
                pass

    def _clear_entries_only(self) -> None:
        self._stop_entry_anims()
        for card in self._entry_widgets:
            self._list_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._entry_widgets.clear()

    def _sync_empty_and_subtitle(self) -> None:
        count = len(self._steps)
        self._empty_container.setVisible(count == 0)
        if self.subtitle_label is not None:
            self.subtitle_label.setText(f"{count} bước đã chứng minh")

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(0, self, self._jump_scroll_to_bottom)

    def _jump_scroll_to_bottom(self) -> None:
        bar = self._scroll_area.verticalScrollBar()
        target = bar.maximum()
        if target <= 0:
            return
        if self._reduced_motion or not self.isVisible():
            bar.setValue(target)
            return
        if self._scroll_anim is not None and self._scroll_anim.state() == QAbstractAnimation.State.Running:
            self._scroll_anim.stop()
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(DEFAULT_MOTION.scaled_ms(420))
        anim.setStartValue(bar.value())
        anim.setEndValue(target)
        anim.setEasingCurve(build_easing(EASE_SOFT))
        self._scroll_anim = anim
        anim.start()
