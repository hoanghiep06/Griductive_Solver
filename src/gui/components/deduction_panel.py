"""DeductionPanel — Accepted Deduction Trace & separate Hint display (Phase 4).

Renders ONLY accepted deduction steps supplied via ``DeductionStepView`` and
temporary non-mutating hints supplied via ``HintView``.
Never runs DPLL, never fabricates proof steps, and preserves separation between
accepted history and temporary hints per ``docs/STAGE2_API_CONTRACT.md`` §D.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import SPACING
from src.gui.view_models import (
    DeductionStepView,
    HintView,
    normalize_deduction_step,
    normalize_hint_view,
)


class _TraceEntryCard(QFrame):
    """Compact read-only card representing one accepted deduction step."""

    def __init__(
        self,
        step_index: int,
        step: DeductionStepView,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._step_index = step_index
        self._step = step

        if step.verdict == "CRIMINAL":
            tone_prop = "criminal"
            badge_text = "CRIMINAL"
            badge_tone = "danger"
        elif step.verdict == "INNOCENT":
            tone_prop = "innocent"
            badge_text = "INNOCENT"
            badge_tone = "success"
        else:
            tone_prop = "unknown"
            badge_text = "CHƯA XÁC ĐỊNH"
            badge_tone = "neutral"

        self.setProperty("widgetKind", "traceEntry")
        self.setProperty("verdictTone", tone_prop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.space_2, SPACING.space_2, SPACING.space_2, SPACING.space_2)
        layout.setSpacing(SPACING.space_1)

        # Header: STEP NN | Target cell | Verdict badge
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(SPACING.space_2)

        display_num = step.step if step.step is not None else step_index
        self._step_label = QLabel(f"BƯỚC {display_num:02d} · Ô {step.cell_id}", self)
        self._step_label.setTextFormat(Qt.TextFormat.PlainText)
        self._step_label.setProperty("role", "paperMono")
        header.addWidget(self._step_label, 1)

        self._verdict_badge = StatusLabel(badge_text, tone=badge_tone, parent=self)
        header.addWidget(self._verdict_badge, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header)

        # Plain-text explanation
        self._explanation_label = QLabel(step.explanation, self)
        self._explanation_label.setTextFormat(Qt.TextFormat.PlainText)
        self._explanation_label.setProperty("role", "paperBody")
        self._explanation_label.setWordWrap(True)
        self._explanation_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self._explanation_label)

        # Concise evidence metadata line (omit technical SAT call/ms benchmarks from gameplay view)
        meta_parts: list[str] = []
        if step.source_clue_ids:
            meta_parts.append(f"Căn cứ: {', '.join(step.source_clue_ids)}")
        if step.newly_revealed_clue_id:
            meta_parts.append(f"Mở mới: {step.newly_revealed_clue_id}")

        if meta_parts:
            self._meta_label = QLabel(" · ".join(meta_parts), self)
            self._meta_label.setTextFormat(Qt.TextFormat.PlainText)
            self._meta_label.setProperty("role", "paperCaption")
            self._meta_label.setWordWrap(True)
            self._meta_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            layout.addWidget(self._meta_label)
        else:
            self._meta_label = None

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
    """Dedicated temporary Hint area kept strictly separate from Accepted Trace."""

    def __init__(self, *, on_dismiss, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DeductionHintBox")
        self.setProperty("widgetKind", "hintBox")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.space_2, SPACING.space_2, SPACING.space_2, SPACING.space_2)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(SPACING.space_2)

        self._title_label = QLabel("Gợi ý suy luận", self)
        self._title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._title_label.setProperty("role", "paperSubheading")
        header.addWidget(self._title_label, 1)

        self._verdict_pill = StatusLabel("HINT", tone="paperAccent", parent=self)
        self._verdict_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(self._verdict_pill)

        self._dismiss_btn = QPushButton("Ẩn", self)
        self._dismiss_btn.setProperty("widgetKind", "compactButton")
        self._dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_btn.setToolTip("Ẩn khung gợi ý hiện tại")
        self._dismiss_btn.clicked.connect(on_dismiss)
        header.addWidget(self._dismiss_btn)
        layout.addLayout(header)

        self._body_label = QLabel("", self)
        self._body_label.setTextFormat(Qt.TextFormat.PlainText)
        self._body_label.setProperty("role", "paperCaption")
        self._body_label.setWordWrap(True)
        self._body_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self._body_label)

        self._logic_chain = QLabel(
            "CHỨNG CỨ  →  THỬ GIẢ THIẾT NGƯỢC  →  MÂU THUẪN  →  KẾT LUẬN",
            self,
        )
        self._logic_chain.setProperty("widgetKind", "logicChain")
        self._logic_chain.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logic_chain.setWordWrap(True)
        layout.addWidget(self._logic_chain)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._enter = QPropertyAnimation(self._opacity, b"opacity", self)
        self._enter.setDuration(260)
        self._enter.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setVisible(False)

    def display_hint(self, hint: HintView) -> None:
        if hint.outcome == "FORCED" and hint.cell_id and hint.verdict:
            self._title_label.setText(f"SUY LUẬN · Ô {hint.cell_id}")
            tone = "danger" if hint.verdict == "CRIMINAL" else "success"
            self._verdict_pill.set_status(hint.verdict, tone=tone)
        else:
            self._title_label.setText("GỢI Ý · CHƯA CÓ NƯỚC ĐI BẮT BUỘC")
            self._verdict_pill.set_status("NO_FORCED", tone="warning")

        body = hint.text
        if hint.source_clue_ids:
            body = f"{body}\n\nCăn cứ công khai: {', '.join(hint.source_clue_ids)}"
        self._body_label.setText(body)
        self._logic_chain.setVisible(hint.outcome == "FORCED")
        self.setMinimumHeight(92)
        self.setVisible(True)
        self._enter.stop()
        self._opacity.setOpacity(0.0)
        self._enter.setStartValue(0.0)
        self._enter.setEndValue(1.0)
        self._enter.start()
        self.updateGeometry()

    def clear_hint(self) -> None:
        self._body_label.clear()
        self._enter.stop()
        self._opacity.setOpacity(1.0)
        self.setMinimumHeight(0)
        self.setVisible(False)
        self.updateGeometry()


class DeductionPanel(StyledPanel):
    """Scrollable accepted deduction trace panel with smart auto-scroll & Hint box."""

    hint_changed = Signal(object)

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title="Nhật Ký Suy Luận",
            subtitle="0 bước đã chứng minh",
            variant="paper",
            padding=SPACING.space_3,
            accent_bar="brick",
            parent=parent,
        )
        self.setObjectName("DeductionPanel")

        self._steps: list[DeductionStepView] = []
        self._entry_widgets: list[_TraceEntryCard] = []
        self._seen_keys: set[tuple[str, int, str]] = set()
        self._current_hint: Optional[HintView] = None

        # Separate non-mutating Hint box at top of panel
        self._hint_box = _HintBox(on_dismiss=self.clear_hint, parent=self)
        self.content_layout.addWidget(self._hint_box)

        # Scrollable Accepted Trace list
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setMinimumHeight(48)

        self._list_host = QWidget(self._scroll_area)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, SPACING.space_1, 0)
        self._list_layout.setSpacing(SPACING.space_2)

        self._empty_label = QLabel(
            "Chưa có bước suy luận nào được chấp nhận.\nCác bước hợp lệ sẽ được ghi nhận tại đây.",
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
    # Public Trace API
    # ------------------------------------------------------------------

    def append_step(self, raw_step: Any) -> bool:
        """Append one accepted deduction step incrementally (idempotent by dedup_key).

        Returns ``True`` if appended, ``False`` if ignored as a duplicate key.
        """
        step = normalize_deduction_step(raw_step)
        if step.dedup_key in self._seen_keys:
            return False

        bar = self._scroll_area.verticalScrollBar()
        was_at_bottom = (bar.maximum() == 0) or (bar.value() >= bar.maximum() - 24)

        self._seen_keys.add(step.dedup_key)
        self._steps.append(step)
        self._append_entry_widget(len(self._steps), step)
        self._sync_empty_and_subtitle()

        if was_at_bottom:
            self._scroll_to_bottom()
        return True

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
        """Display a temporary ``HintView`` in the dedicated Hint box."""
        hint = normalize_hint_view(raw_hint)
        self._current_hint = hint
        self._hint_box.display_hint(hint)
        self.hint_changed.emit(hint)

    def clear_hint(self) -> None:
        """Hide and clear the temporary Hint box."""
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

    def _append_entry_widget(self, idx: int, step: DeductionStepView) -> None:
        card = _TraceEntryCard(idx, step, parent=self._list_host)
        insert_idx = max(0, self._list_layout.count() - 1)
        self._list_layout.insertWidget(insert_idx, card)
        self._entry_widgets.append(card)

    def _clear_entries_only(self) -> None:
        for card in self._entry_widgets:
            self._list_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._entry_widgets.clear()

    def _sync_empty_and_subtitle(self) -> None:
        count = len(self._steps)
        self._empty_label.setVisible(count == 0)
        if self.subtitle_label is not None:
            self.subtitle_label.setText(f"{count} bước đã chứng minh")

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(0, self, self._jump_scroll_to_bottom)

    def _jump_scroll_to_bottom(self) -> None:
        bar = self._scroll_area.verticalScrollBar()
        if bar.maximum() > 0:
            bar.setValue(bar.maximum())
