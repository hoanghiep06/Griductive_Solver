"""ProgressPanel — Compact Cream Editorial investigation progress strip.

Displays ONLY public progress counts (revealed / total / remaining / percentage)
and ``GameState`` supplied via public API. Never infers ``SOLVED`` from counts,
never accesses ``hidden_solution``, and safely handles zero/invalid totals.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import EASE_SOFT, build_easing
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import SPACING
from src.gui.view_models import GameState, coerce_game_state

_GAME_STATE_DISPLAY: dict[GameState, tuple[str, str]] = {
    GameState.NO_PUZZLE: ("○ CHƯA NẠP VỤ ÁN", "neutral"),
    GameState.READY: ("● SẴN SÀNG", "info"),
    GameState.PROCESSING: ("◈ ĐANG PHÂN TÍCH", "accent"),
    GameState.ANIMATING: ("◇ ĐANG LẬT THẺ", "accent"),
    GameState.SOLVED: ("✓ ĐÃ PHÁ ÁN", "success"),
    GameState.STUCK: ("△ BẾ TẮC", "warning"),
    GameState.ERROR: ("✕ LỖI HỆ THỐNG", "danger"),
}


class ProgressPanel(StyledPanel):
    """Compact Cream Editorial progress strip unified with Evidence & Timeline panels."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title=None,
            variant="dossier",
            padding=10,
            accent_bar=None,
            parent=parent,
        )
        self.setObjectName("ProgressPanel")
        self.content_layout.setSpacing(6)

        self._puzzle_id: Optional[str] = None
        self._grid_size: Optional[int] = None
        self._revealed: int = 0
        self._total: int = 0
        self._game_state: GameState = GameState.NO_PUZZLE
        self._reduced_motion: bool = bool(DEFAULT_MOTION.reduced_motion)

        # Hidden metadata labels (preserved for API & unit-test compatibility; displayed in Top Bar)
        self._case_label = QLabel("Vụ án: —", self)
        self._case_label.setTextFormat(Qt.TextFormat.PlainText)
        self._case_label.setVisible(False)

        self._grid_label = QLabel("Lưới: —", self)
        self._grid_label.setTextFormat(Qt.TextFormat.PlainText)
        self._grid_label.setVisible(False)

        self._status_badge = StatusLabel(
            _GAME_STATE_DISPLAY[GameState.NO_PUZZLE][0],
            tone=_GAME_STATE_DISPLAY[GameState.NO_PUZZLE][1],
            parent=self,
        )
        self._status_badge.setVisible(False)

        # Top row: TIẾN ĐỘ ĐIỀU TRA                          24.0%
        top_row = QHBoxLayout()
        top_row.setContentsMargins(2, 0, 2, 0)
        top_row.setSpacing(SPACING.space_2)

        self._kicker_label = QLabel("TIẾN ĐỘ ĐIỀU TRA", self)
        self._kicker_label.setProperty("widgetKind", "timelineStepType")
        top_row.addWidget(self._kicker_label, 1)

        self._percent_label = QLabel("0.0%", self)
        self._percent_label.setProperty("role", "paperMono")
        self._percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self._percent_label, 0)
        self.content_layout.addLayout(top_row)

        # Sleek 8px editorial progress track (text rendered cleanly in _percent_label)
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setProperty("widgetKind", "caseProgress")
        self._progress_bar.setProperty("complete", "false")
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("0.0%")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        self.content_layout.addWidget(self._progress_bar)

        self._bar_anim = QPropertyAnimation(self._progress_bar, b"value", self)
        self._bar_anim.setDuration(DEFAULT_MOTION.scaled_ms(420))
        self._bar_anim.setEasingCurve(build_easing(EASE_SOFT))

        # Bottom metadata strip: Đã lật: 0 / 0   ·   Gợi ý 0 · Lỗi 0   ·   Còn lại: 0
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(2, 0, 2, 0)
        bottom_row.setSpacing(SPACING.space_2)

        self._revealed_label = QLabel("Đã lật: 0 / 0", self)
        self._revealed_label.setProperty("role", "paperCaption")
        bottom_row.addWidget(self._revealed_label, 1)

        self._metrics_label = QLabel("Gợi ý 0 · Lỗi 0", self)
        self._metrics_label.setProperty("role", "paperCaption")
        self._metrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_row.addWidget(self._metrics_label, 0)

        self._remaining_label = QLabel("Còn lại: 0", self)
        self._remaining_label.setProperty("role", "paperCaption")
        self._remaining_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom_row.addWidget(self._remaining_label, 0)
        self.content_layout.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_case_info(
        self,
        puzzle_id: Optional[str],
        grid_size: Optional[int],
    ) -> None:
        """Update displayed puzzle ID and grid size metadata."""
        self._puzzle_id = puzzle_id.strip() if isinstance(puzzle_id, str) and puzzle_id.strip() else None
        self._grid_size = grid_size if type(grid_size) is int and grid_size > 0 else None
        self._case_label.setText(f"Vụ án: {self._puzzle_id or '—'}")
        self._grid_label.setText(
            f"Lưới: {self._grid_size}×{self._grid_size}" if self._grid_size else "Lưới: —"
        )

    def set_progress(self, revealed: int, total: int) -> None:
        """Update revealed / total / remaining / percentage safely.

        Handles zero or negative totals gracefully without division errors.
        """
        safe_total = total if (type(total) is int and total > 0) else 0
        if type(revealed) is not int or revealed < 0:
            safe_revealed = 0
        else:
            safe_revealed = min(revealed, safe_total) if safe_total > 0 else 0

        self._revealed = safe_revealed
        self._total = safe_total
        remaining = max(0, safe_total - safe_revealed)
        pct = (safe_revealed * 100.0 / safe_total) if safe_total > 0 else 0.0

        target_val = int(round(pct * 10))
        pct_text = f"{pct:.1f}%"
        self._progress_bar.setFormat(pct_text)
        self._percent_label.setText(pct_text)
        self._revealed_label.setText(f"Đã lật: {safe_revealed} / {safe_total}")
        self._remaining_label.setText(f"Còn lại: {remaining}")

        is_complete = "true" if (safe_total > 0 and safe_revealed >= safe_total) else "false"
        if self._progress_bar.property("complete") != is_complete:
            self._progress_bar.setProperty("complete", is_complete)
            self._progress_bar.style().unpolish(self._progress_bar)
            self._progress_bar.style().polish(self._progress_bar)

        if self._reduced_motion or not self.isVisible() or safe_total == 0:
            if self._bar_anim.state() == QAbstractAnimation.State.Running:
                self._bar_anim.stop()
            self._progress_bar.setValue(target_val)
        else:
            current_val = self._progress_bar.value()
            if current_val != target_val:
                if self._bar_anim.state() == QAbstractAnimation.State.Running:
                    self._bar_anim.stop()
                self._bar_anim.setStartValue(current_val)
                self._bar_anim.setEndValue(target_val)
                self._bar_anim.start()

    def set_session_metrics(self, hints: int, mistakes: int) -> None:
        """Update compact hint and mistake counters inside the progress footer."""
        h = hints if type(hints) is int and hints >= 0 else 0
        m = mistakes if type(mistakes) is int and mistakes >= 0 else 0
        self._metrics_label.setText(f"Gợi ý {h} · Lỗi {m}")

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion and self._bar_anim.state() == QAbstractAnimation.State.Running:
            end_val = int(self._bar_anim.endValue())
            self._bar_anim.stop()
            self._progress_bar.setValue(end_val)

    def set_game_status(self, state: GameState | str) -> None:
        """Update the explicit GameState badge from Controller."""
        resolved = coerce_game_state(state)
        self._game_state = resolved
        label_text, tone = _GAME_STATE_DISPLAY[resolved]
        self._status_badge.set_status(label_text, tone=tone)

    def reset(self) -> None:
        """Reset panel to empty ``NO_PUZZLE`` state."""
        self.set_case_info(None, None)
        self.set_progress(0, 0)
        self.set_game_status(GameState.NO_PUZZLE)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def puzzle_id(self) -> Optional[str]:
        return self._puzzle_id

    @property
    def grid_size(self) -> Optional[int]:
        return self._grid_size

    @property
    def revealed_count(self) -> int:
        return self._revealed

    @property
    def total_count(self) -> int:
        return self._total

    @property
    def remaining_count(self) -> int:
        return max(0, self._total - self._revealed)

    @property
    def progress_percent(self) -> float:
        return (self._revealed * 100.0 / self._total) if self._total > 0 else 0.0

    @property
    def game_state(self) -> GameState:
        return self._game_state

    @property
    def progress_bar(self) -> QProgressBar:
        return self._progress_bar

    @property
    def status_badge(self) -> StatusLabel:
        return self._status_badge

    @property
    def revealed_label(self) -> QLabel:
        return self._revealed_label

    @property
    def remaining_label(self) -> QLabel:
        return self._remaining_label

    @property
    def percent_label(self) -> QLabel:
        return self._percent_label
