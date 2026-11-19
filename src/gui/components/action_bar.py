"""ActionBar — Verdict Strip & Game Controls Bar (Phase 4).

Strictly presentation & signal emission ONLY:
- Emits ``verdict_requested(cell_id, verdict)``, ``level_selection_requested()``,
  ``restart_requested()``, ``hint_requested()``, ``auto_solve_requested()``,
  and ``back_requested()``.
- Enforces enable/disable rules driven exclusively by public ``GameState`` and
  currently selected ``PublicCharacterView``.
- NEVER flips cards, NEVER mutates board state, NEVER runs Hint/Auto-Solve/SAT.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import SPACING
from src.gui.view_models import (
    CardVisibility,
    GameState,
    PublicCharacterView,
    coerce_game_state,
)


class ActionBar(QWidget):
    """Combined Verdict Strip (top) and Game Action Controls (bottom)."""

    verdict_requested = Signal(str, object)  # (cell_id, "CRIMINAL" | "INNOCENT")
    level_selection_requested = Signal()
    restart_requested = Signal()
    hint_requested = Signal()
    auto_solve_requested = Signal()
    back_requested = Signal()
    demo_results_requested = Signal()

    def __init__(
        self,
        *,
        demo_mode: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ActionBar")
        self._demo_mode = bool(demo_mode)
        self._game_state: GameState = GameState.NO_PUZZLE
        self._selected_character: Optional[PublicCharacterView] = None
        self._auto_solving = False
        self._accepted_steps = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING.space_1)

        # ------------------------------------------------------------------
        # 1. VERDICT STRIP: Selected Suspect + CRIMINAL / INNOCENT (Cream Dossier)
        # ------------------------------------------------------------------
        self._verdict_panel = StyledPanel(
            variant="dossier",
            padding=SPACING.space_1,
            accent_bar="brass",
            parent=self,
        )
        verdict_row = QHBoxLayout()
        verdict_row.setContentsMargins(SPACING.space_2, 0, SPACING.space_2, 0)
        verdict_row.setSpacing(SPACING.space_3)

        self._selected_label = QLabel(
            "Chưa chọn nghi phạm — Nhấp vào một thẻ chưa mở trên bàn cờ",
            self._verdict_panel,
        )
        self._selected_label.setTextFormat(Qt.TextFormat.PlainText)
        self._selected_label.setProperty("role", "paperSubheading")
        self._selected_label.setWordWrap(True)
        self._selected_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        verdict_row.addWidget(self._selected_label, 1)

        self._criminal_btn = StyledButton(
            "▲ Tội phạm",
            variant="danger",
            min_height=44,
            parent=self._verdict_panel,
        )
        self._criminal_btn.setToolTip(
            "Chứng minh nhân vật này là tội phạm từ các manh mối đang mở"
        )
        self._criminal_btn.clicked.connect(lambda: self._emit_verdict("CRIMINAL"))
        verdict_row.addWidget(self._criminal_btn)

        self._innocent_btn = StyledButton(
            "✓ Vô tội",
            variant="success",
            min_height=44,
            parent=self._verdict_panel,
        )
        self._innocent_btn.setToolTip(
            "Chứng minh nhân vật này vô tội từ các manh mối đang mở"
        )
        self._innocent_btn.clicked.connect(lambda: self._emit_verdict("INNOCENT"))
        verdict_row.addWidget(self._innocent_btn)

        self._verdict_panel.content_layout.addLayout(verdict_row)
        root.addWidget(self._verdict_panel)

        # ------------------------------------------------------------------
        # 2. GAME CONTROLS STRIP: Load | Restart | Hint | Auto Solve | Back
        # ------------------------------------------------------------------
        self._controls_panel = StyledPanel(variant="paper", padding=SPACING.space_1, parent=self)
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(SPACING.space_2, 0, SPACING.space_2, 0)
        controls_row.setSpacing(SPACING.space_2)
        management_label = QLabel("MÀN CHƠI", self)
        management_label.setProperty("role", "paperCaption")
        controls_row.addWidget(management_label)

        self._load_btn = StyledButton(
            "▣ Đổi hồ sơ",
            variant="ghost",
            min_height=44,
            parent=self._controls_panel,
        )
        self._load_btn.setToolTip("Mở màn hình chọn vụ án (Kho Hồ Sơ)")
        self._load_btn.clicked.connect(self.level_selection_requested.emit)
        controls_row.addWidget(self._load_btn)

        self._restart_btn = StyledButton(
            "↻ Chơi lại",
            variant="ghost",
            min_height=44,
            parent=self._controls_panel,
        )
        self._restart_btn.setToolTip("Khởi động lại vụ án hiện tại")
        self._restart_btn.clicked.connect(self._request_restart)
        controls_row.addWidget(self._restart_btn)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.VLine)
        controls_row.addWidget(divider)
        assist_label = QLabel("TRỢ GIÚP", self)
        assist_label.setProperty("role", "paperCaption")
        controls_row.addWidget(assist_label)

        self._hint_btn = StyledButton(
            "? Gợi ý",
            variant="secondary",
            min_height=44,
            parent=self._controls_panel,
        )
        self._hint_btn.setToolTip("Chứng minh và mở một ô, kèm manh mối và lời giải thích")
        self._hint_btn.clicked.connect(self.hint_requested.emit)
        controls_row.addWidget(self._hint_btn)

        self._auto_solve_btn = StyledButton(
            "▶ Tự giải",
            variant="primary",
            min_height=44,
            parent=self._controls_panel,
        )
        self._auto_solve_btn.setToolTip("Tự động giải tuần tự theo suy luận logic")
        self._auto_solve_btn.clicked.connect(self.auto_solve_requested.emit)
        controls_row.addWidget(self._auto_solve_btn)

        controls_row.addStretch(1)

        self._demo_results_btn: Optional[StyledButton] = None
        if self._demo_mode:
            self._demo_results_btn = StyledButton(
                "Xem kết quả (Demo) →",
                variant="ghost",
                min_height=44,
                parent=self._controls_panel,
            )
            self._demo_results_btn.setToolTip(
                "Nút dành cho lập trình viên: mở màn hình Results với dữ liệu mẫu preview"
            )
            self._demo_results_btn.clicked.connect(self.demo_results_requested.emit)
            self._demo_results_btn.setVisible(False)
            controls_row.addWidget(self._demo_results_btn)

        self._back_btn = StyledButton(
            "← Menu chính",
            variant="ghost",
            min_height=44,
            parent=self._controls_panel,
        )
        self._back_btn.setToolTip("Quay lại màn hình chính")
        self._back_btn.clicked.connect(self.back_requested.emit)
        controls_row.addWidget(self._back_btn)

        self._controls_panel.content_layout.addLayout(controls_row)
        root.addWidget(self._controls_panel)

        self._restart_confirm = QWidget(self)
        confirm_row = QHBoxLayout(self._restart_confirm)
        confirm_row.setContentsMargins(SPACING.space_2, 0, SPACING.space_2, 0)
        confirm_label = QLabel("Chơi lại sẽ xóa tiến độ của ván này.", self)
        confirm_label.setProperty("role", "paperSubheading")
        confirm_row.addWidget(confirm_label, 1)
        self.confirm_restart_button = StyledButton("Chơi lại từ đầu", variant="danger", min_height=32, parent=self)
        self.cancel_restart_button = StyledButton("Tiếp tục chơi", variant="ghost", min_height=32, parent=self)
        self.confirm_restart_button.clicked.connect(self._confirm_restart)
        self.cancel_restart_button.clicked.connect(self.dismiss_restart_confirmation)
        confirm_row.addWidget(self.confirm_restart_button)
        confirm_row.addWidget(self.cancel_restart_button)
        self._restart_confirm.hide()
        root.addWidget(self._restart_confirm)

        self.status_label = QLabel("Đã giải 0 / 0  ·  Gợi ý 0  ·  Đoán lỗi 0", self)
        self.status_label.setProperty("role", "paperCaption")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.status_label)

        self._apply_enablement()

    # ------------------------------------------------------------------
    # Public State Control API
    # ------------------------------------------------------------------

    def set_game_state(self, state: GameState | str) -> None:
        """Update button enablement according to ``STAGE2_UI_DESIGN.md`` §8."""
        self._game_state = coerce_game_state(state)
        self._apply_enablement()

    def set_session_stats(self, revealed: int, total: int, hints: int, mistakes: int, accepted_steps: int = 0) -> None:
        self._accepted_steps = accepted_steps
        self.status_label.setText(f"Đã giải {revealed} / {total}  ·  Gợi ý {hints}  ·  Đoán lỗi {mistakes}")

    def set_auto_solving(self, running: bool) -> None:
        self._auto_solving = running
        self._auto_solve_btn.setText("Ⅱ Tạm dừng" if running else "▶ Tự giải")
        self._auto_solve_btn.set_variant("secondary" if running else "primary")
        self._apply_enablement()

    def _request_restart(self) -> None:
        if self._accepted_steps >= 2:
            self._restart_confirm.show()
        else:
            self.restart_requested.emit()

    def _confirm_restart(self) -> None:
        self.dismiss_restart_confirmation()
        self.restart_requested.emit()

    def dismiss_restart_confirmation(self) -> None:
        self._restart_confirm.hide()

    def set_actions_enabled(self, state: GameState | str) -> None:
        """Alias of ``set_game_state`` matching Phase 4 §15 conceptual contract."""
        self.set_game_state(state)

    def set_selected_character(self, character: Optional[PublicCharacterView]) -> None:
        """Update selected suspect summary and verdict button enablement."""
        self._selected_character = character
        if character is None:
            self._selected_label.setText(
                "Chưa chọn nghi phạm — Nhấp vào một thẻ chưa mở trên bàn cờ"
            )
        else:
            if character.visibility is CardVisibility.HIDDEN:
                status_text = "Chưa mở"
            elif character.verdict == "CRIMINAL":
                status_text = "Tội phạm (Đã mở)"
            else:
                status_text = "Vô tội (Đã mở)"
            self._selected_label.setText(
                f"Đang chọn: [{character.cell_id}] {character.name} ({character.profession}) · {status_text}"
            )
        self._apply_enablement()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def game_state(self) -> GameState:
        return self._game_state

    @property
    def selected_character(self) -> Optional[PublicCharacterView]:
        return self._selected_character

    @property
    def criminal_button(self) -> StyledButton:
        return self._criminal_btn

    @property
    def innocent_button(self) -> StyledButton:
        return self._innocent_btn

    @property
    def load_button(self) -> StyledButton:
        return self._load_btn

    @property
    def restart_button(self) -> StyledButton:
        return self._restart_btn

    @property
    def hint_button(self) -> StyledButton:
        return self._hint_btn

    @property
    def auto_solve_button(self) -> StyledButton:
        return self._auto_solve_btn

    @property
    def back_button(self) -> StyledButton:
        return self._back_btn

    @property
    def demo_results_button(self) -> Optional[StyledButton]:
        return self._demo_results_btn

    @property
    def verdict_panel(self) -> StyledPanel:
        return self._verdict_panel

    @property
    def controls_panel(self) -> StyledPanel:
        return self._controls_panel

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _emit_verdict(self, verdict: str) -> None:
        if not self._can_submit_verdict():
            return
        assert self._selected_character is not None
        # Pure signal emission ONLY — NEVER mutate card or board locally!
        self.verdict_requested.emit(self._selected_character.cell_id, verdict)

    def _can_submit_verdict(self) -> bool:
        if self._auto_solving:
            return False
        if self._game_state not in (GameState.READY, GameState.STUCK):
            return False
        if self._selected_character is None:
            return False
        return self._selected_character.visibility is CardVisibility.HIDDEN

    def _apply_enablement(self) -> None:
        state = self._game_state
        can_verdict = self._can_submit_verdict()
        self._criminal_btn.setEnabled(can_verdict)
        self._innocent_btn.setEnabled(can_verdict)

        can_agent_assist = state in (GameState.READY, GameState.STUCK)
        self._hint_btn.setEnabled(can_agent_assist and not self._auto_solving)
        self._auto_solve_btn.setEnabled(can_agent_assist or self._auto_solving)

        # Restart enabled whenever a puzzle is loaded (even during PROCESSING/ANIMATING per cancellation policy)
        self._restart_btn.setEnabled(state is not GameState.NO_PUZZLE)
        # Load & Back remain enabled across all states per STAGE2_API_CONTRACT §C cancellation policy
        self._load_btn.setEnabled(True)
        self._back_btn.setEnabled(True)
