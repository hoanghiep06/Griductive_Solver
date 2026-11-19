"""MainWindow application shell & presentation facade (Phase 2–4).

Canonical file preserved from ``docs/STAGE2_SHARED_BASELINE.md`` §5.
Implements the full ``ViewPort`` presentation facade (``STAGE2_API_CONTRACT.md`` §D)
and forwards all GUI → Controller intent signals (§C) exactly once.

When Hiệp integrates ``GameController``, passing ``demo_navigation=False``
disables all standalone demo helpers so Controller has 100% authority over
navigation, state transitions, notifications, hints, and results.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from src.gui.asset_registry import AssetId
from src.gui.components.notification_dialog import HowToPlayDialog, NotificationDialog
from src.gui.navigation.screen_router import ScreenId, ScreenRouter
from src.gui.resources.pixmap_loader import PixmapLoader, default_pixmap_loader
from src.gui.screens.about_screen import AboutScreen
from src.gui.screens.gameplay_screen import GameplayScreen
from src.gui.screens.level_selection import LevelSelectionScreen
from src.gui.screens.main_menu import MainMenuScreen
from src.gui.screens.results_screen import ResultsScreen
from src.gui.styles.theme_manager import ThemeManager
from src.gui.styles.tokens import GEOMETRY
from src.gui.view_models import (
    ActionCode,
    ActionResult,
    AnimationToken,
    CardVisibility,
    GameState,
    NotificationSeverity,
    PublicCharacterView,
)


class MainWindow(QMainWindow):
    """Primary PySide6 application window & single presentation facade."""

    # Canonical GUI -> Controller intent signals (STAGE2_API_CONTRACT §C)
    play_requested = Signal()
    about_requested = Signal()
    how_to_play_requested = Signal()
    exit_requested = Signal()
    level_selection_requested = Signal()
    card_selected = Signal(str)
    verdict_requested = Signal(str, object)  # (cell_id, "CRIMINAL" | "INNOCENT")
    clue_selected = Signal(str)
    load_requested = Signal(str)  # puzzle_id
    restart_requested = Signal()
    hint_requested = Signal()
    auto_solve_requested = Signal()
    back_requested = Signal()
    # Phase 5 CardFlipAnimation lifecycle handshake (STAGE2_API_CONTRACT §C)
    animation_finished = Signal(str, object)   # (cell_id, AnimationToken | None) — ONLY on completion
    animation_cancelled = Signal(str, object)  # (cell_id, AnimationToken | None) — ONLY on cancel

    DEFAULT_WIDTH = 1600
    DEFAULT_HEIGHT = 900

    def __init__(
        self,
        *,
        theme_manager: Optional[ThemeManager] = None,
        pixmap_loader: Optional[PixmapLoader] = None,
        demo_navigation: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveMainWindow")
        self.setWindowTitle("GRIDUCTIVE — Detective Case Files")

        self._theme_manager = theme_manager or ThemeManager()
        self._pixmap_loader = pixmap_loader or default_pixmap_loader()
        self._demo_navigation = bool(demo_navigation)
        self._active_help_dialog: Optional[HowToPlayDialog] = None
        self._active_notification_dialog: Optional[NotificationDialog] = None

        # App emblem icon (prefer non-destructive circular cartoon detective A04 emblem)
        app_icon = self._pixmap_loader.load_icon(AssetId.A04_APP_EMBLEM, prefer_derived=True)
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        # Window sizing: supports 960x640 floor through 1280x720, 1366x768, 1600x900, 1920x1080
        self.setMinimumSize(GEOMETRY.window_min_width, GEOMETRY.window_min_height)
        self._apply_initial_size()

        # Central container + ScreenRouter
        central = QWidget(self)
        central.setObjectName("GriductiveCentralRoot")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self._router = ScreenRouter(central)
        central_layout.addWidget(self._router)
        self.setCentralWidget(central)

        # Register single instances of all screens inside ScreenRouter
        self._main_menu_screen = MainMenuScreen(
            pixmap_loader=self._pixmap_loader,
            demo_mode=self._demo_navigation,
            parent=self._router,
        )
        self._about_screen = AboutScreen(
            pixmap_loader=self._pixmap_loader,
            parent=self._router,
        )
        self._level_selection_screen = LevelSelectionScreen(
            pixmap_loader=self._pixmap_loader,
            demo_mode=self._demo_navigation,
            parent=self._router,
        )
        self._gameplay_screen = GameplayScreen(
            pixmap_loader=self._pixmap_loader,
            demo_mode=self._demo_navigation,
            parent=self._router,
        )
        self._results_screen = ResultsScreen(
            pixmap_loader=self._pixmap_loader,
            parent=self._router,
        )

        self._router.register_screen(ScreenId.MAIN_MENU, self._main_menu_screen)
        self._router.register_screen(ScreenId.ABOUT, self._about_screen)
        self._router.register_screen(ScreenId.LEVEL_SELECTION, self._level_selection_screen)
        self._router.register_screen(ScreenId.GAMEPLAY, self._gameplay_screen)
        self._router.register_screen(ScreenId.RESULTS, self._results_screen)

        # Apply global theme if QApplication has no stylesheet yet (supports isolated widget tests)
        app = QApplication.instance()
        if app is not None and not app.styleSheet():
            self._theme_manager.apply_to_application(app)
        elif app is None:
            self._theme_manager.apply_to_widget(self)

        self._wire_signals()
        self.show_main_menu()

    def _apply_initial_size(self) -> None:
        target_w, target_h = self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT
        app = QApplication.instance()
        if app is not None:
            screen = app.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                if avail.width() > 0 and avail.height() > 0:
                    target_w = min(target_w, max(GEOMETRY.window_min_width, avail.width() - 40))
                    target_h = min(target_h, max(GEOMETRY.window_min_height, avail.height() - 60))
        self.resize(target_w, target_h)

    def _wire_signals(self) -> None:
        # Forward child screen intents ONCE up to MainWindow facade
        self._main_menu_screen.play_requested.connect(self.play_requested.emit)
        self._main_menu_screen.about_requested.connect(self.about_requested.emit)
        self._main_menu_screen.how_to_play_requested.connect(self.how_to_play_requested.emit)
        self._main_menu_screen.exit_requested.connect(self.exit_requested.emit)

        # Presentation-only About screen opens directly from Main Menu and returns cleanly
        # without resetting Gameplay state or creating extra windows.
        self._main_menu_screen.about_requested.connect(self.show_about)
        self._about_screen.back_requested.connect(self.show_main_menu)
        self._about_screen.back_requested.connect(self.back_requested.emit)

        self._level_selection_screen.back_requested.connect(self.back_requested.emit)
        self._level_selection_screen.load_requested.connect(self.load_requested.emit)

        self._gameplay_screen.card_selected.connect(self.card_selected.emit)
        self._gameplay_screen.verdict_requested.connect(self.verdict_requested.emit)
        self._gameplay_screen.clue_selected.connect(self.clue_selected.emit)
        self._gameplay_screen.level_selection_requested.connect(self.level_selection_requested.emit)
        self._gameplay_screen.restart_requested.connect(self.restart_requested.emit)
        self._gameplay_screen.hint_requested.connect(self.hint_requested.emit)
        self._gameplay_screen.auto_solve_requested.connect(self.auto_solve_requested.emit)
        self._gameplay_screen.back_requested.connect(self.back_requested.emit)
        self._gameplay_screen.animation_finished.connect(self.animation_finished.emit)
        self._gameplay_screen.animation_cancelled.connect(self.animation_cancelled.emit)

        self._results_screen.restart_requested.connect(self.restart_requested.emit)
        self._results_screen.load_requested.connect(self.load_requested.emit)
        self._results_screen.level_selection_requested.connect(self.level_selection_requested.emit)
        self._results_screen.back_requested.connect(self.back_requested.emit)

        if self._demo_navigation:
            # Isolated standalone GUI demo routing using synthetic PUBLIC MOCK DATA ONLY.
            # NEVER invokes DPLL, GameEngine, LogicAgent, or mutates cards on verdict click.
            self._demo_flip_seq = 0
            self._main_menu_screen.play_requested.connect(self._demo_open_level_selection)
            self._main_menu_screen.how_to_play_requested.connect(self.show_how_to_play)
            self._main_menu_screen.exit_requested.connect(self.close)

            self._level_selection_screen.back_requested.connect(self.show_main_menu)
            self._level_selection_screen.load_requested.connect(self._demo_open_case_by_id)
            self._level_selection_screen.demo_gameplay_requested.connect(self._demo_open_gameplay_label)

            self._gameplay_screen.level_selection_requested.connect(self._demo_open_level_selection)
            self._gameplay_screen.demo_results_requested.connect(self._demo_open_results)
            self._gameplay_screen.demo_size_requested.connect(self._demo_load_scenario)
            self._gameplay_screen.demo_notification_requested.connect(self._demo_show_notification)
            self._gameplay_screen.demo_flip_requested.connect(self._demo_trigger_mock_flip)
            self._gameplay_screen.demo_reduced_motion_toggled.connect(self.set_reduced_motion)
            self._gameplay_screen.clue_selected.connect(self._demo_on_clue_selected)
            self._gameplay_screen.verdict_requested.connect(self._demo_on_verdict_requested)
            self._gameplay_screen.hint_requested.connect(self._demo_on_hint_requested)
            self._gameplay_screen.auto_solve_requested.connect(self._demo_on_auto_solve_requested)
            self._gameplay_screen.restart_requested.connect(self._demo_on_restart_requested)
            self._gameplay_screen.back_requested.connect(self.show_main_menu)

            self._results_screen.demo_gameplay_requested.connect(self.show_gameplay)
            self._results_screen.demo_levels_requested.connect(self._demo_open_level_selection)
            self._results_screen.load_requested.connect(self._demo_open_case_by_id)
            self._results_screen.back_requested.connect(self.show_main_menu)

    # ------------------------------------------------------------------
    # Standalone Demo Helpers (NEVER active when demo_navigation=False)
    # ------------------------------------------------------------------

    def _demo_open_level_selection(self) -> None:
        from src.gui.demo_fixtures import build_official_public_level_catalog

        if not self._level_selection_screen.levels:
            self._level_selection_screen.set_levels(build_official_public_level_catalog())
        self.show_level_selection()

    def _demo_open_gameplay_label(self, grid_label: str) -> None:
        size_map = {"3x3": 3, "4x4": 4, "5x5": 5}
        grid_size = size_map.get(grid_label.strip().lower(), 3)
        self._demo_load_scenario(grid_size)
        self.show_gameplay()

    def _demo_open_case_by_id(self, puzzle_id: str) -> None:
        pid = puzzle_id.strip()
        if "5x5" in pid.lower():
            gs = 5
        elif "4x4" in pid.lower():
            gs = 4
        else:
            gs = 3
        self._demo_load_scenario(gs, puzzle_id=pid)
        self.show_gameplay()

    def _demo_load_scenario(self, grid_size: int, *, puzzle_id: Optional[str] = None) -> None:
        from src.gui.demo_fixtures import (
            OFFICIAL_PUZZLE_IDS,
            build_demo_snapshot,
            build_demo_trace,
            build_official_public_snapshot,
        )

        target_pid = (puzzle_id or f"{grid_size}x{grid_size}_01").strip()
        if target_pid in OFFICIAL_PUZZLE_IDS:
            snap = build_official_public_snapshot(target_pid, include_demo_reveals=True)
        else:
            snap = build_demo_snapshot(grid_size, puzzle_id=puzzle_id)
        self._gameplay_screen.reset_for_new_case(snap)
        self._gameplay_screen.set_deduction_trace(
            build_demo_trace(grid_size, session_id=snap.session_id)
        )
        self._gameplay_screen.set_game_status(GameState.READY)

    def _demo_show_notification(self, code: ActionCode) -> None:
        from src.gui.demo_fixtures import build_demo_notification

        cell_id = self._gameplay_screen.game_board.selected_cell_id or "C1"
        self.show_notification(build_demo_notification(code, cell_id=cell_id))

    def _demo_on_verdict_requested(self, cell_id: str, verdict: object) -> None:
        # Demo explicitly demonstrates that GUI NEVER flips a card on click without Controller!
        self.show_notification(
            ActionResult(
                code=ActionCode.NOT_PROVABLE,
                message=(
                    f"[MẪU DEMO] Đã phát signal verdict_requested({cell_id}, {verdict}). "
                    "GUI độc lập không tự lật thẻ hay chạy SAT — chờ GameController (Hiệp) xử lý."
                ),
                cell_id=cell_id,
                severity=NotificationSeverity.INFO,
            )
        )

    def _demo_on_hint_requested(self) -> None:
        from src.gui.demo_fixtures import build_demo_hint

        cell_id = self._gameplay_screen.game_board.selected_cell_id or "C1"
        self.show_hint(build_demo_hint(cell_id=cell_id))

    def _demo_on_auto_solve_requested(self) -> None:
        self.show_notification(
            ActionResult(
                code=ActionCode.BUSY,
                message=(
                    "[MẪU DEMO] Đã phát signal auto_solve_requested(). "
                    "Chế độ tự giải tuần tự cần GameController (Hiệp) + LogicAgent (Tài)."
                ),
                severity=NotificationSeverity.INFO,
            )
        )

    def _demo_on_restart_requested(self) -> None:
        gs = self._gameplay_screen.game_board.grid_size or 3
        pid = self._gameplay_screen.game_board.puzzle_id or None
        self._demo_load_scenario(gs, puzzle_id=pid)

    def _demo_open_results(self) -> None:
        from src.gui.demo_fixtures import build_demo_results_view

        gs = self._gameplay_screen.game_board.grid_size or 3
        pid = self._gameplay_screen.game_board.puzzle_id or f"MOCK_{gs}x{gs}_01"
        self.show_results(build_demo_results_view(puzzle_id=pid, grid_size=gs))

    def _demo_on_clue_selected(self, clue_id: str) -> None:
        # Standalone demo simulator: reads ONLY already-projected mock referenced_cells
        # (never parses Clue parameters or regions inside GUI).
        clue = next(
            (c for c in self._gameplay_screen.clue_panel.clues if c.clue_id == clue_id),
            None,
        )
        if clue is not None and clue.referenced_cells:
            self.highlight_cells(clue.referenced_cells)
        else:
            self.clear_highlights()

    def _demo_trigger_mock_flip(self) -> None:
        # Developer QA helper: simulates an authorized Controller reveal_card() call on a hidden card
        board = self._gameplay_screen.game_board
        if board.is_animating:
            return
        cid = board.selected_cell_id
        card = board.cards_by_id.get(cid) if cid else None
        if card is None or card.is_revealed:
            # Pick first hidden card purely for standalone QA demonstration
            card = next((c for c in board.cards_by_id.values() if not c.is_revealed), None)
        if card is None:
            return
        d = card.public_data
        self._demo_flip_seq += 1
        mock_verdict = "INNOCENT" if (self._demo_flip_seq % 2 == 1) else "CRIMINAL"
        revealed_view = PublicCharacterView(
            cell_id=d.cell_id,
            name=d.name,
            profession=d.profession,
            row=d.row,
            col=d.col,
            visibility=CardVisibility.REVEALED,
            verdict=mock_verdict,
            has_public_clue=True,
        )
        tok = AnimationToken(
            session_id="demo-mock-flip",
            request_id=self._demo_flip_seq,
            kb_version=1,
            cell_id=d.cell_id,
        )
        self.show_notification(
            ActionResult(
                code=ActionCode.ACCEPTED,
                message=f"[MẪU DEMO QA] Mô phỏng Controller gọi reveal_card({d.cell_id}) -> {mock_verdict}.",
                cell_id=d.cell_id,
            )
        )
        self.reveal_card(d.cell_id, revealed_view, tok)

    # ------------------------------------------------------------------
    # Public Properties
    # ------------------------------------------------------------------

    @property
    def router(self) -> ScreenRouter:
        return self._router

    @property
    def theme_manager(self) -> ThemeManager:
        return self._theme_manager

    @property
    def pixmap_loader(self) -> PixmapLoader:
        return self._pixmap_loader

    @property
    def current_screen(self) -> Optional[ScreenId]:
        return self._router.current_screen

    @property
    def main_menu_screen(self) -> MainMenuScreen:
        return self._main_menu_screen

    @property
    def about_screen(self) -> AboutScreen:
        return self._about_screen

    @property
    def level_selection_screen(self) -> LevelSelectionScreen:
        return self._level_selection_screen

    @property
    def gameplay_screen(self) -> GameplayScreen:
        return self._gameplay_screen

    @property
    def results_screen(self) -> ResultsScreen:
        return self._results_screen

    # ------------------------------------------------------------------
    # Public Screen Navigation & ViewPort Presentation API
    # ------------------------------------------------------------------

    def show_screen(self, screen_id: ScreenId | str) -> bool:
        """Navigate to a registered screen by ScreenId or string name."""
        return self._router.navigate_to(screen_id)

    def show_main_menu(self) -> None:
        self.cancel_animations(revert_to_original=False)
        self._router.navigate_to(ScreenId.MAIN_MENU)

    def show_about(self) -> None:
        """Open the single-instance AboutScreen without resetting Gameplay state."""
        self._router.navigate_to(ScreenId.ABOUT)
        self._about_screen.setFocus()

    def show_level_selection(self, levels: Optional[Iterable[Any]] = None) -> None:
        """Open Level Selection screen, populating ``levels`` when provided."""
        self.cancel_animations(revert_to_original=False)
        if levels is not None:
            self._level_selection_screen.set_levels(levels)
        elif self._demo_navigation and not self._level_selection_screen.levels:
            from src.gui.demo_fixtures import build_official_public_level_catalog

            self._level_selection_screen.set_levels(build_official_public_level_catalog())
        self._router.navigate_to(ScreenId.LEVEL_SELECTION)

    def show_gameplay(self, snapshot: Any = None) -> None:
        """Open GameplayScreen; if ``snapshot`` is provided, reset and render it."""
        if snapshot is not None:
            self._gameplay_screen.reset_for_new_case(snapshot)
        elif self._demo_navigation and self._gameplay_screen.game_board.card_count == 0:
            self._demo_load_scenario(3)
        self._router.navigate_to(ScreenId.GAMEPLAY)

    def set_board(self, snapshot: Any) -> None:
        """Render a committed public N×N board snapshot on GameplayScreen."""
        self._gameplay_screen.set_board(snapshot)

    def update_character(self, public_character: Any) -> bool:
        """Update one character card in-place from a public view."""
        return self._gameplay_screen.update_character(public_character)

    def set_clues(self, clues: Iterable[Any]) -> None:
        """Replace displayed public clues in CluePanel."""
        self._gameplay_screen.set_clues(clues)

    def set_selection(self, cell_id: Optional[str]) -> bool:
        """Programmatically select a card without emitting ``card_selected``."""
        return self._gameplay_screen.set_selection(cell_id)

    def set_selected_card(self, cell_id: Optional[str]) -> bool:
        """Alias of ``set_selection`` for Controller convenience."""
        return self.set_selection(cell_id)

    def clear_selection(self) -> None:
        """Programmatically clear card selection."""
        self._gameplay_screen.clear_selection()

    def append_deduction_step(self, step: Any) -> bool:
        """Append one accepted deduction step to DeductionPanel (idempotent)."""
        return self._gameplay_screen.append_deduction_step(step)

    def set_deduction_trace(self, steps: Iterable[Any]) -> None:
        """Replace the entire accepted deduction trace in DeductionPanel."""
        self._gameplay_screen.set_deduction_trace(steps)

    def clear_deduction_trace(self) -> None:
        """Clear all entries from DeductionPanel."""
        self._gameplay_screen.clear_deduction_trace()

    def show_hint(self, hint: Any) -> None:
        """Display a non-mutating HintView in DeductionPanel's dedicated Hint area."""
        self._gameplay_screen.show_hint(hint)

    def clear_hint(self) -> None:
        """Hide and clear the current HintView."""
        self._gameplay_screen.clear_hint()

    def highlight_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        """Highlight a set of cell IDs on the GameBoard with luminous cyan glow."""
        return self._gameplay_screen.highlight_cells(cell_ids)

    def set_highlighted_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        """Alias of ``highlight_cells`` matching Phase 5 §6.3."""
        return self.highlight_cells(cell_ids)

    def clear_highlights(self) -> None:
        """Clear all visual highlight overlays on the GameBoard."""
        self._gameplay_screen.clear_highlights()

    def clear_highlight(self) -> None:
        """Alias of ``clear_highlights`` matching Phase 5 §6.3."""
        self.clear_highlights()

    def reveal_card(
        self,
        cell_id: str,
        public_data: Any,
        token: object = None,
    ) -> bool:
        """Start an authorized physical 3D reveal flip for one card (ViewPort §D)."""
        return self._gameplay_screen.reveal_card(cell_id, public_data, token=token)

    def animate_card_reveal(
        self,
        cell_id: str,
        public_character: Any,
        token: object = None,
    ) -> bool:
        """Alias of ``reveal_card`` matching Phase 5 §9."""
        return self.reveal_card(cell_id, public_character, token=token)

    def cancel_animations(self, *, revert_to_original: bool = True) -> bool:
        """Stop active card reveal animations safely without emitting ``animation_finished``."""
        return self._gameplay_screen.cancel_animations(revert_to_original=revert_to_original)

    def cancel_active_animation(self, *, revert_to_original: bool = True) -> bool:
        """Alias of ``cancel_animations`` matching Phase 5 §9."""
        return self.cancel_animations(revert_to_original=revert_to_original)

    def set_reduced_motion(self, enabled: bool) -> None:
        """Toggle reduced-motion accessibility mode across theme, board & notifications."""
        flag = bool(enabled)
        self._theme_manager.set_reduced_motion(flag)
        self._gameplay_screen.set_reduced_motion(flag)

    def set_animation_enabled(self, enabled: bool) -> None:
        """Inverse alias of ``set_reduced_motion`` matching Phase 5 §9."""
        self.set_reduced_motion(not bool(enabled))

    @property
    def reduced_motion(self) -> bool:
        return self._gameplay_screen.game_board.reduced_motion

    def set_progress(self, revealed: int, total: int) -> None:
        """Update public revealed/total counts in ProgressPanel."""
        self._gameplay_screen.set_progress(revealed, total)

    def set_busy(self, state: GameState | str) -> None:
        """Canonical ``ViewPort.set_busy(state)`` updating status & action locks."""
        self._gameplay_screen.set_busy(state)

    def set_game_status(self, state: GameState | str) -> None:
        """Alias of ``set_busy(state)`` matching Phase 4 §15 naming."""
        self._gameplay_screen.set_game_status(state)

    def set_actions_enabled(self, state: GameState | str) -> None:
        """Alias of ``set_busy(state)`` matching Phase 4 §15 naming."""
        self._gameplay_screen.set_actions_enabled(state)

    def show_notification(self, result: Any, *, modal: bool = False) -> None:
        """Display a Controller ``ActionResult`` as non-blocking banner (or modal dialog)."""
        if not modal and self.current_screen is ScreenId.GAMEPLAY:
            self._gameplay_screen.show_notification(result)
            return
        if self._active_notification_dialog is not None:
            self._active_notification_dialog.close()
        dialog = NotificationDialog(result, parent=self)
        self._active_notification_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_results(self, results: Any = None) -> None:
        """Open ResultsScreen, rendering ``results`` if provided."""
        self.cancel_animations(revert_to_original=False)
        if results is not None:
            self._results_screen.set_results(results)
        elif self._demo_navigation and self._results_screen.results is None:
            from src.gui.demo_fixtures import build_demo_results_view

            gs = self._gameplay_screen.game_board.grid_size or 3
            pid = self._gameplay_screen.game_board.puzzle_id or f"MOCK_{gs}x{gs}_01"
            self._results_screen.set_results(build_demo_results_view(puzzle_id=pid, grid_size=gs))
        self._router.navigate_to(ScreenId.RESULTS)

    def show_how_to_play(self) -> None:
        """Open the How to Play modal dialog cleanly."""
        if self._active_help_dialog is None:
            self._active_help_dialog = HowToPlayDialog(
                pixmap_loader=self._pixmap_loader,
                parent=self,
            )
        self._active_help_dialog.show()
        self._active_help_dialog.raise_()
        self._active_help_dialog.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.cancel_animations(revert_to_original=False)
        self._gameplay_screen.game_board.motion_coordinator.reset_visuals(
            self._gameplay_screen.game_board.cards_by_id
        )
        if self._active_help_dialog is not None:
            self._active_help_dialog.close()
        if self._active_notification_dialog is not None:
            self._active_notification_dialog.close()
        super().closeEvent(event)
