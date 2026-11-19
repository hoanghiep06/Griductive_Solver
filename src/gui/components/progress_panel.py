"""ProgressPanel — Case progress bar, public counts & GameState badge (Phase 4).

Displays ONLY public progress counts (revealed / total / remaining / percentage)
and ``GameState`` supplied via public API. Never infers ``SOLVED`` from counts,
never accesses ``hidden_solution``, and safely handles zero/invalid totals.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import SPACING
from src.gui.view_models import GameState, coerce_game_state

_GAME_STATE_DISPLAY: dict[GameState, tuple[str, str]] = {
    GameState.NO_PUZZLE: ("○ CHƯA NẠP VỤ ÁN (NO_PUZZLE)", "neutral"),
    GameState.READY: ("● SẴN SÀNG (READY)", "info"),
    GameState.PROCESSING: ("◈ ĐANG PHÂN TÍCH (PROCESSING)", "accent"),
    GameState.ANIMATING: ("◇ ĐANG LẬT THẺ (ANIMATING)", "accent"),
    GameState.SOLVED: ("✓ ĐÃ PHÁ ÁN (SOLVED)", "success"),
    GameState.STUCK: ("△ BẾ TẮC (STUCK)", "warning"),
    GameState.ERROR: ("✕ LỖI HỆ THỐNG (ERROR)", "danger"),
}


class ProgressPanel(StyledPanel):
    """Compact progress & status dashboard panel on Soft Ivory Cream dossier surface."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            title=None,
            variant="dossier",
            padding=SPACING.space_2,
            accent_bar="brass",
            parent=parent,
        )
        self.setObjectName("ProgressPanel")
        self.content_layout.setSpacing(4)

        self._puzzle_id: Optional[str] = None
        self._grid_size: Optional[int] = None
        self._revealed: int = 0
        self._total: int = 0
        self._game_state: GameState = GameState.NO_PUZZLE

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

        # Compact single-row progress strip: [Đã lật: X / N]  [==== % ====]  [Còn lại: Y]
        strip_row = QHBoxLayout()
        strip_row.setContentsMargins(SPACING.space_1, 0, SPACING.space_1, 0)
        strip_row.setSpacing(SPACING.space_2)

        self._revealed_label = QLabel("Đã lật: 0 / 0", self)
        self._revealed_label.setProperty("role", "paperSubheading")
        strip_row.addWidget(self._revealed_label, 0)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setProperty("widgetKind", "caseProgress")
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("0.0%")
        self._progress_bar.setFixedHeight(18)
        strip_row.addWidget(self._progress_bar, 1)

        self._remaining_label = QLabel("Còn lại: 0", self)
        self._remaining_label.setProperty("role", "paperSecondary")
        self._remaining_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        strip_row.addWidget(self._remaining_label, 0)

        self.content_layout.addLayout(strip_row)

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

        self._progress_bar.setValue(int(round(pct * 10)))
        self._progress_bar.setFormat(f"{pct:.1f}%")
        self._revealed_label.setText(f"Đã lật: {safe_revealed} / {safe_total}")
        self._remaining_label.setText(f"Còn lại: {remaining}")

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
