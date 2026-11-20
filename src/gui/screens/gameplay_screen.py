"""GameplayScreen integrating GĐ3 GameBoard with full GĐ4 Dashboard panels.

Layout (aligned with Phase 4 §14):
    - Top Bar: GRIDUCTIVE logo | Case ID & grid size | Demo switcher (dev-only) | GameState pill
    - Non-blocking NotificationBanner (auto-hides when dismissed; never covers GameBoard)
    - Main Workspace (QSplitter ~65% Board / ~35% Sidebar):
        * Left: Preserved GĐ3 ``GameBoard`` (3×3, 4×4, 5×5)
        * Right: ``CluePanel`` (scrollable) + ``DeductionPanel`` (scrollable + HintBox) + ``ProgressPanel``
    - Bottom: ``ActionBar`` (Verdict Strip + Game Action Controls)

Strictly presentation & signal forwarding ONLY — contains ZERO SAT, DPLL,
Hint, Auto-Solve, or GameEngine logic.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.gui.asset_registry import AssetId
from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.components.action_bar import ActionBar
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.clue_panel import CluePanel
from src.gui.components.deduction_panel import DeductionPanel
from src.gui.components.interaction_dialog import InteractionDialog
from src.gui.components.notification_dialog import NotificationBanner
from src.gui.components.progress_panel import ProgressPanel
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.grid_view import GameBoard
from src.gui.interaction_state import InteractionState
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.screens.backdrop_screen import BackdropScreen
from src.gui.styles.tokens import COLORS, GEOMETRY, SPACING
from src.gui.view_models import (
    ActionCode,
    CardVisibility,
    GameState,
    PublicBoardSnapshot,
    PublicCharacterView,
    coerce_game_state,
    normalize_board_snapshot,
)

_HEADER_STATE_STYLE: dict[GameState, tuple[str, str]] = {
    GameState.NO_PUZZLE: ("CHƯA NẠP VỤ ÁN", "neutral"),
    GameState.READY: ("SẴN SÀNG", "info"),
    GameState.PROCESSING: ("ĐANG PHÂN TÍCH...", "accent"),
    GameState.ANIMATING: ("ĐANG LẬT THẺ...", "accent"),
    GameState.SOLVED: ("ĐÃ PHÁ ÁN", "success"),
    GameState.STUCK: ("BẾ TẮC", "warning"),
    GameState.ERROR: ("LỖI HỆ THỐNG", "danger"),
}


class GameplayScreen(BackdropScreen):
    """Completed Phase 4 Gameplay Screen hosting GĐ3 ``GameBoard`` + GĐ4 Dashboard."""

    # Canonical GUI -> Controller intent signals (STAGE2_API_CONTRACT §C)
    card_selected = Signal(str)
    verdict_requested = Signal(str, object)
    clue_selected = Signal(str)
    level_selection_requested = Signal()
    restart_requested = Signal()
    hint_requested = Signal()
    auto_solve_requested = Signal()
    auto_solve_speed_changed = Signal(int)
    back_requested = Signal()
    animation_finished = Signal(str, object)   # (cell_id, token) — ONLY on completion
    animation_cancelled = Signal(str, object)  # (cell_id, token) — ONLY on cancel

    # Developer standalone-demo-only signals (hidden when demo_mode=False)
    demo_results_requested = Signal()
    demo_size_requested = Signal(int)
    demo_notification_requested = Signal(object)  # ActionCode
    demo_hint_requested = Signal()
    demo_flip_requested = Signal()
    demo_reduced_motion_toggled = Signal(bool)

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        demo_mode: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            AssetId.A05_GAMEPLAY_BACKGROUND,
            scrim_rgba=COLORS.scrim_gameplay_rgba,
            pixmap_loader=pixmap_loader,
            parent=parent,
        )
        self.setObjectName("GameplayScreen")
        self._demo_mode = bool(demo_mode)
        self._game_state: GameState = GameState.NO_PUZZLE
        self._current_kb_version: Optional[int] = None
        self.ui_state = InteractionState()

        # ------------------------------------------------------------------
        # 1. TOP BAR: GRIDUCTIVE | CASE ID | DEV DEMO SWITCHER | STATUS
        # ------------------------------------------------------------------
        top_bar = QFrame(self)
        top_bar.setProperty("widgetKind", "pageHeader")
        top_bar.setMinimumHeight(52)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(SPACING.space_4, SPACING.space_1, SPACING.space_4, SPACING.space_1)
        top_layout.setSpacing(SPACING.space_2)

        compact_logo = AssetImageView(
            AssetId.A04_LOGO_WIDE,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=top_bar,
        )
        compact_logo.setFixedSize(124, 36)
        top_layout.addWidget(compact_logo)

        self._case_label = QLabel("Hồ sơ: Chưa nạp vụ án", top_bar)
        self._case_label.setTextFormat(Qt.TextFormat.PlainText)
        self._case_label.setProperty("role", "paperSubheading")
        top_layout.addWidget(self._case_label, 1)

        # Developer standalone demo toolbar (grouped cleanly in a secondary Demo QA capsule)
        self._demo_size_buttons: dict[int, StyledButton] = {}
        self._demo_notify_buttons: dict[ActionCode, StyledButton] = {}
        if self._demo_mode:
            demo_group = QFrame(top_bar)
            demo_group.setObjectName("DeveloperDemoControlsGroup")
            demo_group.setProperty("widgetKind", "demoToolbarGroup")
            demo_row = QHBoxLayout(demo_group)
            demo_row.setContentsMargins(SPACING.space_2, 2, SPACING.space_2, 2)
            demo_row.setSpacing(4)

            demo_lbl = QLabel("DEMO QA", demo_group)
            demo_lbl.setProperty("role", "demoGroupLabel")
            demo_row.addWidget(demo_lbl)

            for sz in (3, 4, 5):
                btn = StyledButton(f"Demo {sz}×{sz}", variant="ghost", min_height=30, parent=demo_group)
                btn.setProperty("compact", "true")
                btn.setToolTip(
                    f"Dữ liệu mẫu công khai {sz}×{sz} (không dùng DPLL/hidden_solution)"
                )
                btn.clicked.connect(lambda _checked=False, n=sz: self.demo_size_requested.emit(n))
                demo_row.addWidget(btn)
                self._demo_size_buttons[sz] = btn

            for code, label in (
                (ActionCode.NOT_PROVABLE, "Mock: Chưa rõ"),
                (ActionCode.CONTRADICTED, "Mock: Mâu thuẫn"),
            ):
                nbtn = StyledButton(label, variant="ghost", min_height=30, parent=demo_group)
                nbtn.setProperty("compact", "true")
                nbtn.setToolTip(
                    f"Nút QA lập trình viên: xem thử thông báo {code.value} (dữ liệu mẫu)"
                )
                nbtn.clicked.connect(
                    lambda _checked=False, c=code: self.demo_notification_requested.emit(c)
                )
                demo_row.addWidget(nbtn)
                self._demo_notify_buttons[code] = nbtn

            self._demo_flip_btn = StyledButton("Mock Flip 3D", variant="ghost", min_height=30, parent=demo_group)
            self._demo_flip_btn.setProperty("compact", "true")
            self._demo_flip_btn.setToolTip(
                "Nút QA lập trình viên: mô phỏng Controller gọi reveal_card() lật 3D cho thẻ đang chọn"
            )
            self._demo_flip_btn.clicked.connect(self.demo_flip_requested.emit)
            demo_row.addWidget(self._demo_flip_btn)

            self._demo_reduced_btn = StyledButton("Giảm hiệu ứng: Tắt", variant="ghost", min_height=30, parent=demo_group)
            self._demo_reduced_btn.setProperty("compact", "true")
            self._demo_reduced_btn.setToolTip("Bật/tắt chế độ Reduced Motion để kiểm thử GĐ5")
            self._demo_reduced_btn.clicked.connect(self._on_demo_reduced_clicked)
            demo_row.addWidget(self._demo_reduced_btn)

            # Collapsed by default to keep Gameplay Top Bar clean and focused; toggle via compact QA button
            self._demo_group = demo_group
            self._demo_group.setVisible(False)
            top_layout.addWidget(demo_group)

            self._demo_qa_toggle_btn = StyledButton("Công cụ QA", variant="ghost", min_height=28, parent=top_bar)
            self._demo_qa_toggle_btn.setProperty("compact", "true")
            self._demo_qa_toggle_btn.setToolTip("Ẩn/hiện thanh công cụ kiểm thử nhanh (Demo 3×3 / 4×4 / 5×5 / Flip 3D)")
            self._demo_qa_toggle_btn.clicked.connect(
                lambda: self._demo_group.setVisible(not self._demo_group.isVisible())
            )
            top_layout.addWidget(self._demo_qa_toggle_btn)
        else:
            self._demo_group = None
            self._demo_qa_toggle_btn = None
            self._demo_flip_btn = None
            self._demo_reduced_btn = None

        self._status_pill = StatusLabel(
            "CHƯA NẠP VỤ ÁN",
            tone="neutral",
            parent=top_bar,
        )
        top_layout.addWidget(self._status_pill)
        self.body_layout.addWidget(top_bar)

        # ------------------------------------------------------------------
        # 2. NON-BLOCKING NOTIFICATION BANNER (never obscures GameBoard)
        # ------------------------------------------------------------------
        banner_wrap = QHBoxLayout()
        banner_wrap.setContentsMargins(SPACING.space_4, SPACING.space_1, SPACING.space_4, 0)
        self._notification_banner = NotificationBanner(parent=self)
        banner_wrap.addWidget(self._notification_banner)
        self.body_layout.addLayout(banner_wrap)

        # ------------------------------------------------------------------
        # 3. MAIN WORKSPACE: QSplitter — Dominant GameBoard (~65%) + Sidebar (~35%)
        # ------------------------------------------------------------------
        workspace_wrap = QHBoxLayout()
        workspace_wrap.setContentsMargins(SPACING.space_4, SPACING.space_1, SPACING.space_4, SPACING.space_1)
        workspace_wrap.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setObjectName("GameplaySplitter")
        self._splitter.setChildrenCollapsible(False)

        # Left: Preserved GĐ3 GameBoard inside warm Paper Beige investigation tabletop panel
        self._board_panel = StyledPanel(
            variant="translucent",
            padding=SPACING.space_2,
            accent_bar="brass",
            parent=self._splitter,
        )
        self._board_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._board_panel.setMinimumWidth(520)

        self._game_board = GameBoard(
            pixmap_loader=pixmap_loader,
            motion_config=MotionConfig(card_flip_duration=DEFAULT_MOTION.assisted_flip_duration),
            parent=self._board_panel,
        )
        self._game_board.card_selected.connect(self._on_board_card_selected)
        self._game_board.background_clicked.connect(self.clear_highlights)
        self._game_board.animation_finished.connect(self._on_board_animation_finished)
        self._game_board.animation_cancelled.connect(self.animation_cancelled.emit)
        self._board_panel.content_layout.addWidget(self._game_board, 1)
        self._splitter.addWidget(self._board_panel)

        # Right: Dashboard Sidebar (CluePanel + DeductionPanel + ProgressPanel)
        self._sidebar_widget = QWidget(self._splitter)
        self._sidebar_widget.setObjectName("GameplaySidebar")
        self._sidebar_widget.setMinimumWidth(320)
        self._sidebar_widget.setMaximumWidth(540)
        sidebar_layout = QVBoxLayout(self._sidebar_widget)
        sidebar_layout.setContentsMargins(SPACING.space_2, 0, 0, 0)
        sidebar_layout.setSpacing(SPACING.space_2)

        self._clue_panel = CluePanel(pixmap_loader=pixmap_loader, parent=self._sidebar_widget)
        self._clue_panel.clue_selected.connect(self._on_clue_selected)
        self._clue_panel.focus_cleared.connect(self.clear_highlights)
        self._clue_panel.clue_usage_changed.connect(self._on_clue_usage_changed)
        sidebar_layout.addWidget(self._clue_panel, 5)

        self._deduction_panel = DeductionPanel(parent=self._sidebar_widget)
        self._deduction_panel.hint_changed.connect(self._on_hint_changed)
        sidebar_layout.addWidget(self._deduction_panel, 3)

        self._progress_panel = ProgressPanel(parent=self._sidebar_widget)
        sidebar_layout.addWidget(self._progress_panel, 0)

        self._splitter.addWidget(self._sidebar_widget)
        self._splitter.setStretchFactor(0, 65)
        self._splitter.setStretchFactor(1, 35)
        self._splitter.setSizes([860, 440])

        workspace_wrap.addWidget(self._splitter, 1)
        self.body_layout.addLayout(workspace_wrap, 1)

        # ------------------------------------------------------------------
        # 4. BOTTOM ACTION BAR (Verdict Strip + Game Controls)
        # ------------------------------------------------------------------
        action_wrap = QHBoxLayout()
        action_wrap.setContentsMargins(SPACING.space_4, 0, SPACING.space_4, SPACING.space_2)

        self._action_bar = ActionBar(demo_mode=self._demo_mode, parent=self)
        self._action_bar.verdict_requested.connect(self.verdict_requested.emit)
        self._action_bar.level_selection_requested.connect(self.level_selection_requested.emit)
        self._action_bar.restart_requested.connect(self.restart_requested.emit)
        self._action_bar.restart_confirmation_requested.connect(self._show_restart_dialog)
        self._action_bar.hint_requested.connect(self.hint_requested.emit)
        self._action_bar.auto_solve_requested.connect(self.auto_solve_requested.emit)
        self._action_bar.auto_solve_speed_changed.connect(self.auto_solve_speed_changed.emit)
        self._action_bar.back_requested.connect(self.back_requested.emit)
        self._action_bar.demo_results_requested.connect(self.demo_results_requested.emit)

        action_wrap.addWidget(self._action_bar)
        self.body_layout.addLayout(action_wrap)

        self._restart_dialog = InteractionDialog(self)
        self._restart_dialog.confirmed.connect(self.restart_requested.emit)
        self._feedback_dialog = InteractionDialog(self)
        self._feedback_dialog.inspect_requested.connect(
            self._notification_banner.inspect_requested.emit
        )

        self.set_game_status(GameState.NO_PUZZLE)
        QApplication.instance().installEventFilter(self)
        self._notification_banner.dismissed.connect(self._on_feedback_dismissed)

    # ------------------------------------------------------------------
    # Public Controller -> GUI Presentation API (ViewPort-aligned)
    # ------------------------------------------------------------------

    def set_board(self, snapshot: Any) -> None:
        """Render a complete public snapshot, syncing clues, progress, and selection."""
        norm: PublicBoardSnapshot = normalize_board_snapshot(snapshot)
        prev_kb = self._current_kb_version

        self._game_board.set_board(norm)
        self._current_kb_version = norm.kb_version

        n = self._game_board.grid_size
        pid = self._game_board.puzzle_id
        revealed_count = sum(1 for c in norm.characters if c.visibility is CardVisibility.REVEALED)
        self._case_label.setText(f"Hồ sơ: {pid}  ·  Bàn cờ {n}×{n}")

        # Sync public clues & public progress counts from snapshot
        self._clue_panel.set_clues(norm.clues)
        self._progress_panel.set_case_info(pid, n)
        self._progress_panel.set_progress(revealed_count, len(norm.characters))
        self._action_bar.set_session_stats(revealed_count, len(norm.characters),
                                           self.ui_state.hint_count, self.ui_state.mistake_count)

        # Per STAGE2_API_CONTRACT §D: when KB version advances, clear stale Hint
        if prev_kb is not None and norm.kb_version != prev_kb:
            self.clear_hint()

        self._sync_selected_character()
        for sz, btn in self._demo_size_buttons.items():
            btn.set_variant("primary" if sz == n else "ghost")

    def reset_for_new_case(self, snapshot: Any) -> None:
        """Prepare screen for a fresh Load/Restart (cancel flips, clear trace/hint/banner/highlights)."""
        self._game_board.cancel_animations(revert_to_original=False)
        self._notification_banner.dismiss(animated=False)
        self._restart_dialog.force_close()
        self._feedback_dialog.force_close()
        self._deduction_panel.clear()
        self._deduction_panel.clear_hint()
        self._game_board.clear_highlights()
        self._game_board.clear_selection()
        for card in self._game_board.cards_by_id.values():
            card.reset_interaction_visuals()
        self.ui_state = InteractionState()
        self._clue_panel.clear()
        self._action_bar.set_auto_solving(False)
        self._current_kb_version = None
        self.set_board(snapshot)

    def reveal_card(
        self,
        cell_id: str,
        public_data: Any,
        token: object = None,
    ) -> bool:
        """Start an authorized 3D card reveal flip on ``GameBoard``."""
        return self._game_board.reveal_card(cell_id, public_data, token=token)

    def animate_card_reveal(
        self,
        cell_id: str,
        public_character: Any,
        token: object = None,
    ) -> bool:
        """Alias of ``reveal_card`` matching Phase 5 §9."""
        return self.reveal_card(cell_id, public_character, token=token)

    def cancel_animations(self, *, revert_to_original: bool = True) -> bool:
        """Cancel any active card flip safely without emitting ``animation_finished``."""
        return self._game_board.cancel_animations(revert_to_original=revert_to_original)

    def set_reduced_motion(self, enabled: bool) -> None:
        """Propagate reduced-motion setting to GameBoard and NotificationBanner."""
        flag = bool(enabled)
        self._game_board.set_reduced_motion(flag)
        self._notification_banner.set_reduced_motion(flag)
        if self._demo_reduced_btn is not None:
            self._demo_reduced_btn.setText(f"Giảm hiệu ứng: {'Bật' if flag else 'Tắt'}")
            self._demo_reduced_btn.set_variant("primary" if flag else "ghost")

    def set_animation_enabled(self, enabled: bool) -> None:
        self.set_reduced_motion(not bool(enabled))

    def set_highlighted_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        return self.highlight_cells(cell_ids)

    def clear_highlight(self) -> None:
        self.clear_highlights()

    def update_character(self, public_character: Any) -> bool:
        """Update one character card in-place and sync selected summary if needed."""
        updated = self._game_board.update_character(public_character)
        if updated:
            self._sync_selected_character()
        return updated

    def set_clues(self, clues: Iterable[Any]) -> None:
        """Replace CluePanel contents with validated public clues."""
        self._clue_panel.set_clues(clues)

    def append_deduction_step(self, step: Any) -> bool:
        """Append one accepted deduction step (idempotent)."""
        return self._deduction_panel.append_step(step)

    def set_deduction_trace(self, steps: Iterable[Any]) -> None:
        """Replace the full accepted deduction trace."""
        self._deduction_panel.set_steps(steps)

    def clear_deduction_trace(self) -> None:
        """Clear all accepted deduction trace steps."""
        self._deduction_panel.clear()

    def show_hint(self, hint: Any) -> None:
        """Render a temporary non-mutating HintView in DeductionPanel."""
        self._deduction_panel.show_hint(hint)
        self.ui_state.active_hint = hint

    def animate_hint_flow(
        self,
        clue_ids: Iterable[str],
        supporting_cells: Iterable[str],
        target_cell_id: str,
    ) -> bool:
        clue_set = set(clue_ids)
        source_cells = list(supporting_cells)
        for clue in self._clue_panel.clues:
            if clue.clue_id in clue_set:
                source_cells.append(clue.owner_id)
                source_cells.extend(clue.referenced_cells)
        return self._game_board.animate_hint_flow(source_cells, target_cell_id)

    def clear_hint(self) -> None:
        """Hide and clear the temporary Hint box."""
        self._deduction_panel.clear_hint()
        self.ui_state.active_hint = None

    def set_progress(self, revealed: int, total: int) -> None:
        """Update ProgressPanel counts and bar from public Controller counts."""
        self._progress_panel.set_progress(revealed, total)

    def set_game_status(self, state: GameState | str) -> None:
        """Apply ``GameState`` across header badge, ProgressPanel, ActionBar, and interaction locks."""
        resolved = coerce_game_state(state)
        self._game_state = resolved

        hdr_text, hdr_tone = _HEADER_STATE_STYLE[resolved]
        self._status_pill.set_status(hdr_text, tone=hdr_tone)
        self._progress_panel.set_game_status(resolved)
        self._action_bar.set_game_state(resolved)

        # Per STAGE2_API_CONTRACT §C: lock board & clue selection during PROCESSING/ANIMATING
        interactive = resolved in (GameState.READY, GameState.STUCK, GameState.SOLVED)
        self._game_board.set_interactive(interactive)
        self._clue_panel.set_interactive(interactive)

    def set_busy(self, state: GameState | str) -> None:
        """Canonical ``ViewPort.set_busy(state)`` alias of ``set_game_status``."""
        self.set_game_status(state)

    def set_actions_enabled(self, state: GameState | str) -> None:
        """Convenience alias matching Phase 4 §15 contract."""
        self.set_game_status(state)

    def show_notification(self, result: Any) -> None:
        """Display a non-blocking Controller notification banner."""
        self._notification_banner.show_result(result)
        current = self._notification_banner.current_result
        self.ui_state.error_feedback = current if current.code in (ActionCode.NOT_PROVABLE, ActionCode.CONTRADICTED) else None
        if current.code is ActionCode.NOT_PROVABLE:
            self._feedback_dialog.force_close()
            self._feedback_dialog.configure(
                tone="warning",
                icon="?",
                kicker="CHƯA ĐỦ CHỨNG CỨ · NOT_PROVABLE",
                title="Kết luận này vẫn còn hai khả năng hợp lệ",
                message=current.message,
                detail=(
                    "SAT vẫn tìm được ít nhất một mô hình cho mỗi giả thiết. "
                    "Hãy mở thêm chuỗi suy luận hoặc xem lại một manh mối khác trước khi kết luận."
                ),
                cancel_text="Quay lại điều tra",
                modal=False,
            )
            self._feedback_dialog.show()
            self._feedback_dialog.raise_()
        elif current.code is ActionCode.CONTRADICTED:
            self._feedback_dialog.force_close()
            self._feedback_dialog.configure(
                tone="danger",
                icon="×",
                kicker="XUNG ĐỘT LOGIC · CONTRADICTED",
                title="Giả thiết vừa chọn phá vỡ chuỗi chứng cứ",
                message=current.message,
                detail=(
                    "Giả thiết ngược lại đã được chứng minh từ KB hiện tại. "
                    "Bạn có thể soi tập chứng cứ tối tiểu đang gây ra mâu thuẫn."
                ),
                cancel_text="Đóng",
                allow_inspect=self._notification_banner.inspect_button.isVisible(),
                modal=False,
            )
            self._feedback_dialog.show()
            self._feedback_dialog.raise_()

    def dismiss_notification(self) -> None:
        self._notification_banner.dismiss()
        self._feedback_dialog.close_animated()

    def dismiss_interaction_dialogs(self) -> None:
        self._restart_dialog.force_close()
        self._feedback_dialog.force_close()

    def set_contradiction_inspect_available(self, enabled: bool) -> None:
        flag = bool(enabled)
        self._notification_banner.inspect_button.setVisible(flag)
        self._feedback_dialog.inspect_button.setVisible(flag)

    def set_selection(self, cell_id: Optional[str]) -> bool:
        """Programmatically update selected cell (emits no signal)."""
        ok = self._game_board.set_selection(cell_id)
        if ok:
            self._sync_selected_character()
        return ok

    def clear_selection(self) -> None:
        self._game_board.clear_selection()
        self._sync_selected_character()

    def highlight_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        self.ui_state.highlighted_targets = self._game_board.highlight_cells(cell_ids)
        return self.ui_state.highlighted_targets

    def clear_highlights(self) -> None:
        self._game_board.clear_highlights()
        self._clue_panel.set_selected_clue(None)
        self.ui_state.selected_clue_id = None
        self.ui_state.highlighted_targets = ()

    def focus_evidence(self, clue_ids: Iterable[str], cells: Iterable[str] = ()) -> None:
        ids = tuple(clue_ids)
        clues = [c for c in self._clue_panel.clues if c.clue_id in ids]
        primary = list(cells)
        references = []
        for clue in clues:
            primary.append(clue.owner_id)
            references.extend(clue.referenced_cells)
        self._clue_panel.set_evidence_clues(c.clue_id for c in clues)
        self.ui_state.selected_clue_id = clues[0].clue_id if clues else None
        self.ui_state.highlighted_targets = self._game_board.focus_evidence(primary, references)

    def _on_clue_selected(self, clue_id: str) -> None:
        clue = next(c for c in self._clue_panel.clues if c.clue_id == clue_id)
        primary = clue.primary_cells or (clue.referenced_cells[:1] if clue.clue_type in {"SAME", "DIFFERENT"} else clue.referenced_cells)
        references = (*clue.referenced_cells, clue.owner_id)
        self.ui_state.selected_clue_id = clue_id
        self.ui_state.highlighted_targets = self._game_board.focus_evidence(primary, references)
        self.clue_selected.emit(clue_id)

    def _on_clue_usage_changed(self, clue_id: str, used: bool) -> None:
        if used:
            self.ui_state.solved_clues.add(clue_id)
        else:
            self.ui_state.solved_clues.discard(clue_id)

    def _on_feedback_dismissed(self) -> None:
        self.ui_state.error_feedback = None

    def _on_hint_changed(self, hint) -> None:
        self.ui_state.active_hint = hint

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if self.isVisible():
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.clear_highlights()
                self._notification_banner.dismiss(animated=True)
                self._restart_dialog.close_animated()
                self._feedback_dialog.close_animated()
                return True
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                blank = (self, self._board_panel, self._sidebar_widget,
                         self._clue_panel.scroll_area.viewport(), self._clue_panel.scroll_area.widget())
                if watched in blank:
                    self.clear_highlights()
        return False

    def closeEvent(self, event) -> None:  # noqa: N802
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._restart_dialog.force_close()
        self._feedback_dialog.force_close()
        super().closeEvent(event)

    def set_board_interactive(self, enabled: bool) -> None:
        self._game_board.set_interactive(enabled)

    def restart_with_transition(self, snapshot: Any, completed=None) -> None:
        """Clear transient UI while the old board collapses and the new one is dealt."""
        self._restart_dialog.force_close()
        self._feedback_dialog.force_close()
        self._notification_banner.dismiss(animated=False)
        self._deduction_panel.clear()
        self._deduction_panel.clear_hint()
        self._clue_panel.clear()
        self._game_board.clear_selection()
        self.ui_state = InteractionState()
        self._action_bar.set_auto_solving(False)
        self._current_kb_version = None

        def finish() -> None:
            self.set_board(snapshot)
            if callable(completed):
                completed()

        self._game_board.animate_board_rebuild(snapshot, finish)

    def _show_restart_dialog(self) -> None:
        revealed = self._progress_panel.revealed_count
        total = self._progress_panel.total_count
        self._restart_dialog.configure(
            tone="restart",
            icon="↻",
            kicker="TÁI DỰNG HỒ SƠ",
            title="Xóa tiến độ và dựng lại bàn điều tra?",
            message=(
                "Các thẻ đã mở, nhật ký suy luận, highlight và ghi chú manh mối "
                "của lượt chơi hiện tại sẽ được làm mới."
            ),
            detail=f"Tiến độ hiện tại: {revealed}/{total} thẻ đã mở. Dữ liệu puzzle gốc và solver không bị thay đổi.",
            confirm_text="↻ Tái dựng từ đầu",
            cancel_text="Giữ nguyên hồ sơ",
            modal=True,
        )
        self._restart_dialog.show()
        self._restart_dialog.raise_()
        self._restart_dialog.activateWindow()

    def set_demo_case_preview(self, grid_label: str) -> None:
        self._case_label.setText(f"VỤ ÁN: [XEM TRƯỚC {grid_label.upper()}]")

    # ------------------------------------------------------------------
    # Internal Handlers
    # ------------------------------------------------------------------

    def _on_board_card_selected(self, cell_id: str) -> None:
        self._notification_banner.dismiss(animated=False)
        self._feedback_dialog.close_animated()
        self._sync_selected_character()
        self.card_selected.emit(cell_id)

    def _on_board_animation_finished(self, cell_id: str, token: object) -> None:
        self._sync_selected_character()
        self.animation_finished.emit(cell_id, token)

    def _on_demo_reduced_clicked(self) -> None:
        new_val = not self._game_board.reduced_motion
        self.set_reduced_motion(new_val)
        self.demo_reduced_motion_toggled.emit(new_val)

    def _sync_selected_character(self) -> None:
        cell_id = self._game_board.selected_cell_id
        if cell_id is None or cell_id not in self._game_board.cards_by_id:
            self._action_bar.set_selected_character(None)
            return
        data: PublicCharacterView = self._game_board.cards_by_id[cell_id].public_data
        self._action_bar.set_selected_character(data)

    # ------------------------------------------------------------------
    # Properties & Preserved GĐ3 Slot Names
    # ------------------------------------------------------------------

    @property
    def game_board(self) -> GameBoard:
        return self._game_board

    @property
    def board_container(self) -> StyledPanel:
        return self._board_panel

    @property
    def clue_panel(self) -> CluePanel:
        return self._clue_panel

    @property
    def deduction_panel(self) -> DeductionPanel:
        return self._deduction_panel

    @property
    def progress_panel(self) -> ProgressPanel:
        return self._progress_panel

    @property
    def action_bar(self) -> ActionBar:
        return self._action_bar

    @property
    def notification_banner(self) -> NotificationBanner:
        return self._notification_banner

    @property
    def splitter(self) -> QSplitter:
        return self._splitter

    @property
    def game_state(self) -> GameState:
        return self._game_state

    # Preserved GĐ2/GĐ3 property names for backward compatibility
    @property
    def clue_container(self) -> CluePanel:
        return self._clue_panel

    @property
    def deduction_container(self) -> DeductionPanel:
        return self._deduction_panel

    @property
    def progress_container(self) -> ProgressPanel:
        return self._progress_panel

    @property
    def verdict_container(self) -> StyledPanel:
        return self._action_bar.verdict_panel

    @property
    def action_container(self) -> StyledPanel:
        return self._action_bar.controls_panel

    @property
    def demo_size_buttons(self) -> dict[int, StyledButton]:
        return dict(self._demo_size_buttons)
