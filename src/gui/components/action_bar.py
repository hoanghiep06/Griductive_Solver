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

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.styles.tokens import SPACING
from src.gui.view_models import (
    CardVisibility,
    GameState,
    PublicCharacterView,
    coerce_game_state,
)


class _TargetSuspectIcon(QWidget):
    """Crisp antique-bronze chess-knight/detective piece icon left of selected cell label."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(22, 24)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor("#8C6024"))
        p.setPen(QPen(QColor("#4F3310"), 1.2))
        path = QPainterPath(QPointF(6.0, 21.0))
        path.lineTo(QPointF(17.0, 21.0))
        path.lineTo(QPointF(15.5, 17.5))
        path.quadTo(QPointF(16.5, 11.0), QPointF(14.5, 5.5))
        path.lineTo(QPointF(12.5, 3.0))
        path.lineTo(QPointF(10.0, 5.5))
        path.lineTo(QPointF(5.5, 8.5))
        path.lineTo(QPointF(6.8, 11.2))
        path.lineTo(QPointF(10.2, 10.5))
        path.quadTo(QPointF(8.0, 14.5), QPointF(7.2, 17.5))
        path.closeSubpath()
        p.drawPath(path)
        p.end()


class ActionBar(QWidget):
    """Combined Verdict Strip (top) and Game Action Controls (bottom)."""

    verdict_requested = Signal(str, object)  # (cell_id, "CRIMINAL" | "INNOCENT")
    level_selection_requested = Signal()
    restart_requested = Signal()
    restart_confirmation_requested = Signal()
    hint_requested = Signal()
    auto_solve_requested = Signal()
    auto_solve_speed_changed = Signal(int)
    back_requested = Signal()
    demo_results_requested = Signal()
    session_stats_updated = Signal(int, int)  # (hints, mistakes)

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
        self._nav_docked = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING.space_1)

        # ------------------------------------------------------------------
        # 1. UNIFIED HERO ACTION STRIP: Selected Suspect + Verdict + Assist + Pace
        # ------------------------------------------------------------------
        self._verdict_panel = StyledPanel(
            variant="dossier",
            padding=6,
            accent_bar="brass",
            parent=self,
        )
        self._verdict_panel.setObjectName("ActionBarVerdictPanel")
        self._verdict_panel.setStyleSheet(
            "QFrame#ActionBarVerdictPanel {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )
        verdict_row = QHBoxLayout()
        verdict_row.setContentsMargins(6, 0, 6, 0)
        verdict_row.setSpacing(6)

        verdict_row.addWidget(_TargetSuspectIcon(self._verdict_panel), 0, Qt.AlignmentFlag.AlignVCenter)

        self._selected_label = QLabel(
            "Chọn thẻ chưa mở trên bàn cờ",
            self._verdict_panel,
        )
        self._selected_label.setTextFormat(Qt.TextFormat.PlainText)
        self._selected_label.setProperty("role", "paperSubheading")
        self._selected_label.setWordWrap(False)
        self._selected_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._selected_label.setMinimumWidth(110)
        verdict_row.addWidget(self._selected_label, 1)

        self._criminal_btn = StyledButton(
            "▲ Tội phạm",
            variant="danger",
            min_height=36,
            parent=self._verdict_panel,
        )
        self._criminal_btn.setProperty("compactAction", "true")
        self._criminal_btn.setToolTip(
            "Chứng minh nhân vật này là tội phạm từ các manh mối đang mở"
        )
        self._criminal_btn.clicked.connect(lambda: self._emit_verdict("CRIMINAL"))
        verdict_row.addWidget(self._criminal_btn)

        self._innocent_btn = StyledButton(
            "✓ Vô tội",
            variant="success",
            min_height=36,
            parent=self._verdict_panel,
        )
        self._innocent_btn.setProperty("compactAction", "true")
        self._innocent_btn.setToolTip(
            "Chứng minh nhân vật này vô tội từ các manh mối đang mở"
        )
        self._innocent_btn.clicked.connect(lambda: self._emit_verdict("INNOCENT"))
        verdict_row.addWidget(self._innocent_btn)

        action_divider = QFrame(self._verdict_panel)
        action_divider.setFrameShape(QFrame.Shape.VLine)
        action_divider.setFixedHeight(24)
        verdict_row.addWidget(action_divider)

        self._hint_btn = StyledButton(
            "? Gợi ý",
            variant="secondary",
            min_height=36,
            parent=self._verdict_panel,
        )
        self._hint_btn.setProperty("compactAction", "true")
        self._hint_btn.setToolTip("Chỉ ra ô nên xét và các manh mối liên quan, không tiết lộ kết luận")
        self._hint_btn.clicked.connect(self.hint_requested.emit)
        verdict_row.addWidget(self._hint_btn)

        self._auto_solve_btn = StyledButton(
            "▶ Tự giải",
            variant="primary",
            min_height=36,
            parent=self._verdict_panel,
        )
        self._auto_solve_btn.setProperty("compactAction", "true")
        self._auto_solve_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1D324D, stop:1 #112034);"
            "  color: #FFFDF7;"
            "  border: 1.8px solid #D9B365;"
            "  border-radius: 7px;"
            "  font-weight: 700;"
            "  padding: 0 14px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #264164, stop:1 #172B45);"
            "  border: 1.8px solid #F0D088;"
            "}"
            "QPushButton:disabled {"
            "  background: #425062;"
            "  color: #B4BECB;"
            "  border: 1.4px solid #8A8170;"
            "}"
        )
        self._auto_solve_btn.setToolTip("Tự động giải tuần tự theo suy luận logic")
        self._auto_solve_btn.clicked.connect(self.auto_solve_requested.emit)
        verdict_row.addWidget(self._auto_solve_btn)

        pace_divider = QFrame(self._verdict_panel)
        pace_divider.setFrameShape(QFrame.Shape.VLine)
        pace_divider.setFixedHeight(24)
        verdict_row.addWidget(pace_divider)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal, self._verdict_panel)
        self.speed_slider.setProperty("widgetKind", "autoSpeedSlider")
        self.speed_slider.setRange(600, 3000)
        self.speed_slider.setSingleStep(100)
        self.speed_slider.setPageStep(300)
        self.speed_slider.setValue(1500)
        self.speed_slider.setFixedWidth(72)
        self.speed_slider.setToolTip("Nhịp tự giải: Nhanh (0.6s) ↔ Chậm (3.0s)")
        self.speed_slider.setAccessibleName("Tốc độ tự giải")
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        verdict_row.addWidget(self.speed_slider)

        self.speed_value_label = QLabel("1.50s", self._verdict_panel)
        self.speed_value_label.setProperty("role", "paperMono")
        self.speed_value_label.setMinimumWidth(40)
        self.speed_value_label.setToolTip("Khoảng nghỉ giữa mỗi bước tự giải")
        verdict_row.addWidget(self.speed_value_label)

        self._verdict_panel.content_layout.addLayout(verdict_row)
        root.addWidget(self._verdict_panel)

        # ------------------------------------------------------------------
        # 2. NAVIGATION CONTROLS CAPSULE: Load | Restart | Back
        #    (Docked into GameplayScreen Top Bar; stays inline when standalone)
        # ------------------------------------------------------------------
        self._controls_panel = StyledPanel(variant="paper", padding=3, parent=self)
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(4, 0, 4, 0)
        controls_row.setSpacing(4)

        self._load_btn = StyledButton(
            "▣ Đổi hồ sơ",
            variant="ghost",
            min_height=32,
            parent=self._controls_panel,
        )
        self._load_btn.setProperty("compact", "true")
        self._load_btn.setToolTip("Mở màn hình chọn vụ án (Kho Hồ Sơ)")
        self._load_btn.clicked.connect(self.level_selection_requested.emit)
        controls_row.addWidget(self._load_btn)

        self._restart_btn = StyledButton(
            "↻ Chơi lại",
            variant="ghost",
            min_height=32,
            parent=self._controls_panel,
        )
        self._restart_btn.setProperty("compact", "true")
        self._restart_btn.setToolTip("Khởi động lại vụ án hiện tại")
        self._restart_btn.clicked.connect(self._request_restart)
        controls_row.addWidget(self._restart_btn)

        self._demo_results_btn = StyledButton(
            "Biên bản khép án →",
            variant="primary",
            min_height=32,
            parent=self._controls_panel,
        )
        self._demo_results_btn.setProperty("compact", "true")
        self._demo_results_btn.setToolTip(
            "Mở Biên Bản Khép Án và chuyển sang vụ án tiếp theo"
        )
        self._demo_results_btn.clicked.connect(self.demo_results_requested.emit)
        self._demo_results_btn.setVisible(False)
        controls_row.addWidget(self._demo_results_btn)

        self._back_btn = StyledButton(
            "← Trang chủ",
            variant="ghost",
            min_height=32,
            parent=self._controls_panel,
        )
        self._back_btn.setProperty("compact", "true")
        self._back_btn.setToolTip("Quay lại màn hình chính")
        self._back_btn.clicked.connect(self.back_requested.emit)
        controls_row.addWidget(self._back_btn)

        self._controls_panel.content_layout.addLayout(controls_row)
        root.addWidget(self._controls_panel)

        self.status_label = QLabel("Đã giải 0 / 0  ·  Gợi ý 0  ·  Đoán lỗi 0", self)
        self.status_label.setProperty("role", "paperCaption")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        self._apply_enablement()

    def dock_navigation_bar(self, target_layout: QHBoxLayout, insert_index: int = -1) -> None:
        """Move navigation controls capsule into GameplayScreen's Top Bar to free board height."""
        if self._nav_docked:
            return
        self._nav_docked = True
        self.layout().removeWidget(self._controls_panel)
        self._controls_panel.setProperty("widgetKind", "topNavCapsule")
        if insert_index >= 0:
            target_layout.insertWidget(insert_index, self._controls_panel)
        else:
            target_layout.addWidget(self._controls_panel)
        self._controls_panel.show()

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
        self.session_stats_updated.emit(hints, mistakes)

    def set_auto_solving(self, running: bool) -> None:
        self._auto_solving = running
        self._auto_solve_btn.setText("Ⅱ Tạm dừng" if running else "▶ Tự giải")
        self._auto_solve_btn.set_variant("secondary" if running else "primary")
        self._apply_enablement()

    def _request_restart(self) -> None:
        if self._accepted_steps >= 2:
            self.restart_confirmation_requested.emit()
        else:
            self.restart_requested.emit()

    def _on_speed_changed(self, value: int) -> None:
        self.speed_value_label.setText(f"{value / 1000:.2f}s")
        self.auto_solve_speed_changed.emit(value)

    def set_actions_enabled(self, state: GameState | str) -> None:
        """Alias of ``set_game_state`` matching Phase 4 §15 conceptual contract."""
        self.set_game_state(state)

    def set_selected_character(self, character: Optional[PublicCharacterView]) -> None:
        """Update selected suspect summary and verdict button enablement."""
        self._selected_character = character
        if character is None:
            self._selected_label.setText("Chọn thẻ chưa mở trên bàn cờ")
            self._selected_label.setToolTip(
                "Chưa chọn nghi phạm — Nhấp vào một thẻ chưa mở trên bàn cờ"
            )
        else:
            if character.visibility is CardVisibility.HIDDEN:
                status_text = "Chưa mở"
            elif character.verdict == "CRIMINAL":
                status_text = "Tội phạm"
            else:
                status_text = "Vô tội"
            self._selected_label.setText(
                f"[{character.cell_id}] {character.name} · {status_text}"
            )
            self._selected_label.setToolTip(
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
        if self._demo_results_btn is not None:
            self._demo_results_btn.setVisible(state is GameState.SOLVED)
            self._demo_results_btn.setEnabled(state is GameState.SOLVED)