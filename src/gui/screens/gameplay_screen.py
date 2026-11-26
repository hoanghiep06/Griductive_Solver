"""GameplayScreen integrating GĐ3 GameBoard with GĐ4 Dashboard panels.

Layout:
    - Top Bar: GRIDUCTIVE logo | Case ID & grid size | Demo switcher (dev-only) | GameState pill
    - Non-blocking NotificationBanner (auto-hides when dismissed; never covers GameBoard)
    - Main Workspace (QSplitter ~70% Board / ~30% Sidebar):
        * Left: ``GameBoard``. Each revealed card carries its own public clue in a
          strip right under the name frame (the old CluePanel is gone).
        * Right: public counts + a fixed-size ``ClueReader``; tabbed personal
          scratchpad (Nháp) and deduction journal.
    - Bottom: ``ActionBar`` (Verdict Strip + Game Action Controls) | ``ProgressPanel``

Clue visibility ("ẩn manh mối không quan trọng"):
    A clue is *spent* when every cell it mentions is already revealed, or the player
    double-clicked it. Spent clues collapse to a tiny chip. Fresh clues (owner just
    flipped), the selected clue, and everything while "Hiện tất cả" is on stay open.

Clue preview: hovering a clue strip previews its board effect (highlight + connectors);
leaving restores the selected clue (or the previous highlight).

Strictly presentation & signal forwarding ONLY — contains ZERO SAT, DPLL,
Hint, Auto-Solve, or GameEngine logic.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.asset_registry import AssetId
from src.gui.case_catalog import format_gameplay_case_header
from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.components.action_bar import ActionBar
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.character_card import ClueNote
from src.gui.components.clue_reader import ClueReader
from src.gui.components.deduction_panel import DeductionPanel
from src.gui.components.interaction_dialog import InteractionDialog
from src.gui.components.notification_dialog import NotificationBanner
from src.gui.components.progress_panel import ProgressPanel
from src.gui.components.scratchpad_panel import ScratchpadPanel
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.grid_view import GameBoard
from src.gui.interaction_state import InteractionState
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.screens.backdrop_screen import BackdropScreen
from src.gui.styles.tokens import COLORS, GEOMETRY, SPACING
from src.gui.styles.investigation import TABS_STYLE
from src.gui.view_models import (
    ActionCode,
    CardVisibility,
    GameState,
    PublicBoardSnapshot,
    PublicCharacterView,
    PublicClueView,
    coerce_game_state,
    normalize_board_snapshot,
    normalize_clue_view,
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

_COMPARATIVE_TYPES = frozenset({"SAME", "DIFFERENT", "COUNT_COMPARE", "IMPLIES"})

_RELATION_LABELS: dict[str, str] = {
    "FACT": "SỰ THẬT",
    "SAME": "= CÙNG PHE",
    "DIFFERENT": "≠ KHÁC PHE",
    "EXACTLY": "CHÍNH XÁC",
    "AT_LEAST": "ÍT NHẤT",
    "AT_MOST": "NHIỀU NHẤT",
    "PARITY": "CHẴN / LẺ",
    "COUNT_COMPARE": "SO SÁNH",
    "IMPLIES": "NẾU → THÌ",
}


def _relation_label(clue: PublicClueView) -> str:
    """Badge text for the board effects.

    PARITY: prefer ``scope_label`` ("Số chẵn" / "Số lẻ"), else read the clue text so
    even/odd stays unambiguous. COUNT_COMPARE: append the operator symbol held in
    ``scope_label`` (=, ≠, ≤, ≥, <, >).
    """
    ctype = clue.clue_type
    if ctype == "PARITY":
        if clue.scope_label:
            return clue.scope_label.upper()
        low = clue.text.lower()
        has_odd, has_even = "lẻ" in low, "chẵn" in low
        if has_odd and not has_even:
            return "SỐ LẺ"
        if has_even and not has_odd:
            return "SỐ CHẴN"
    if ctype == "COUNT_COMPARE" and clue.scope_label:
        return f"SO SÁNH {clue.scope_label}"
    return _RELATION_LABELS.get(ctype, "")


class _TopBrandPlaque(QWidget):
    """Centered vintage dark-navy & antique-brass nameplate for GameplayScreen Top Bar."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(264, 42)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Decorative brass side curls flanking the nameplate
        p.setPen(QPen(QColor("#B68D46"), 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cy = h * 0.5
        for sign in (-1.0, 1.0):
            x_edge = 24.0 if sign < 0 else (w - 24.0)
            p.drawLine(QPointF(x_edge, cy), QPointF(x_edge + sign * 14.0, cy))
            p.drawEllipse(QPointF(x_edge + sign * 16.0, cy), 2.2, 2.2)

        # Notched navy-and-brass medallion plaque
        r = QRectF(24.0, 2.0, w - 48.0, h - 4.0)
        cut = 8.0
        poly = QPolygonF(
            [
                QPointF(r.left() + cut, r.top()),
                QPointF(r.right() - cut, r.top()),
                QPointF(r.right(), r.center().y()),
                QPointF(r.right() - cut, r.bottom()),
                QPointF(r.left() + cut, r.bottom()),
                QPointF(r.left(), r.center().y()),
            ]
        )
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, QColor("#21344D"))
        grad.setColorAt(1.0, QColor("#121E2E"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#D2AA5C"), 1.7))
        p.drawPolygon(poly)

        title_font = QFont("Georgia")
        title_font.setPixelSize(13)
        title_font.setBold(True)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.7)
        p.setFont(title_font)
        p.setPen(QColor("#F2D492"))
        p.drawText(QRectF(r.left() + 10.0, r.top() + 3.0, r.width() - 20.0, 18.0), Qt.AlignmentFlag.AlignCenter, "GRIDUCTIVE SOLVER")

        sub_font = QFont("Georgia")
        sub_font.setPixelSize(10)
        sub_font.setItalic(True)
        p.setFont(sub_font)
        p.setPen(QColor("#D8C9A8"))
        p.drawText(QRectF(r.left() + 10.0, r.top() + 20.0, r.width() - 20.0, 14.0), Qt.AlignmentFlag.AlignCenter, "Hồ Sơ Phá Án")
        p.end()


class _CaseTitleLabel(QLabel):
    """Keep the full accessible title, eliding cleanly when the header is narrow."""

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        area = self.contentsRect()
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, area.width())
        painter.drawText(area, self.alignment(), text)


class _GameplayHeader(QFrame):
    """Equal side columns keep the plaque on the actual window centerline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(SPACING.space_3, 4, SPACING.space_3, 4)
        self._grid.setHorizontalSpacing(12)
        self.left = QWidget(self)
        self.left_layout = QHBoxLayout(self.left)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(SPACING.space_2)
        self.plaque = _TopBrandPlaque(self)
        self.right = QWidget(self)
        self.controls = QHBoxLayout(self.right)
        self.controls.setContentsMargins(0, 0, 0, 0)
        self.controls.setSpacing(SPACING.space_2)
        self._grid.addWidget(self.left, 0, 0)
        self._grid.addWidget(self.plaque, 0, 1, Qt.AlignmentFlag.AlignCenter)
        self._grid.addWidget(self.right, 0, 2, Qt.AlignmentFlag.AlignRight)
        self._rebalance_timer = QTimer(self)
        self._rebalance_timer.setSingleShot(True)
        self._rebalance_timer.timeout.connect(self.rebalance)
        self.right.installEventFilter(self)

    def rebalance(self):
        controls_width = self.controls.sizeHint().width()
        margins = self._grid.contentsMargins()
        required = 2 * controls_width + self.plaque.width() + 24 + margins.left() + margins.right()
        centered = self.width() >= max(1450, required)
        self.plaque.setVisible(centered)
        for column in (0, 2):
            self._grid.setColumnMinimumWidth(column, controls_width if centered else 0)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(2, 1 if centered else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.rebalance()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.LayoutRequest:
            self._rebalance_timer.start(0)
        return super().eventFilter(watched, event)


class GameplayScreen(BackdropScreen):
    """Completed Phase 4 Gameplay Screen hosting GĐ3 ``GameBoard`` + dashboard."""

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
    tutorial_requested = Signal()
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
            scrim_rgba=(20, 31, 43, 244),
            pixmap_loader=pixmap_loader,
            parent=parent,
        )
        self.setObjectName("GameplayScreen")
        self._demo_mode = bool(demo_mode)
        self._game_state: GameState = GameState.NO_PUZZLE
        self._current_kb_version: Optional[int] = None
        self.ui_state = InteractionState()

        # Public clues now live here (displayed under each revealed card)
        self._clues: tuple[PublicClueView, ...] = ()
        self._focused_clue_ids: frozenset[str] = frozenset()
        self._show_all_clues: bool = False
        self._fresh_owner_ids: frozenset[str] = frozenset()
        self._prev_revealed: Optional[frozenset[str]] = None

        # Hover preview of a clue (does not change the selected clue / strip states)
        self._preview_clue_id: Optional[str] = None
        self._preview_saved_targets: tuple[str, ...] = ()

        # ------------------------------------------------------------------
        # 1. VINTAGE BRASS TOP BAR: Logo + Case | Center Brand Plaque | Nav + Status
        # ------------------------------------------------------------------
        top_bar = _GameplayHeader(self)
        top_bar.setObjectName("GameplayVintageTopBar")
        top_bar.setProperty("widgetKind", "pageHeader")
        top_bar.setStyleSheet(
            "QFrame#GameplayVintageTopBar {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FBF5E8, stop:1 #EFE2C7);"
            "  border-bottom: 2px solid #C6A262;"
            "}"
        )
        top_bar.setMinimumHeight(52)
        self._top_bar = top_bar
        top_layout = top_bar.controls

        compact_logo = AssetImageView(
            AssetId.A04_LOGO_WIDE,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=top_bar,
        )
        compact_logo.setFixedSize(90, 30)
        top_bar.left_layout.addWidget(compact_logo)

        self._case_label = _CaseTitleLabel("Hồ sơ: Chưa nạp vụ án", top_bar)
        self._case_label.setTextFormat(Qt.TextFormat.PlainText)
        self._case_label.setProperty("role", "paperSubheading")
        self._case_label.setStyleSheet("color: #202836; font-weight: 700; font-size: 13.5px; background: transparent;")
        self._case_label.setMinimumWidth(0)
        self._case_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top_bar.left_layout.addWidget(self._case_label, 1)

        # Centered ornate GRIDUCTIVE SOLVER · Hồ Sơ Phá Án brass plaque
        self._brand_plaque = top_bar.plaque

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

            demo_lbl = QLabel("MẪU THỬ", demo_group)
            demo_lbl.setProperty("role", "demoGroupLabel")
            demo_row.addWidget(demo_lbl)

            for sz in (3, 4, 5):
                btn = StyledButton(f"Mẫu {sz}×{sz}", variant="ghost", min_height=30, parent=demo_group)
                btn.setProperty("compact", "true")
                btn.setToolTip(
                    f"Dữ liệu mẫu công khai {sz}×{sz}"
                )
                btn.clicked.connect(lambda _checked=False, n=sz: self.demo_size_requested.emit(n))
                demo_row.addWidget(btn)
                self._demo_size_buttons[sz] = btn

            for code, label in (
                (ActionCode.NOT_PROVABLE, "Thử: Chưa rõ"),
                (ActionCode.CONTRADICTED, "Thử: Mâu thuẫn"),
            ):
                nbtn = StyledButton(label, variant="ghost", min_height=30, parent=demo_group)
                nbtn.setProperty("compact", "true")
                nbtn.setToolTip(
                    f"Xem thử thông báo mẫu"
                )
                nbtn.clicked.connect(
                    lambda _checked=False, c=code: self.demo_notification_requested.emit(c)
                )
                demo_row.addWidget(nbtn)
                self._demo_notify_buttons[code] = nbtn

            self._demo_flip_btn = StyledButton("Thử lật 3D", variant="ghost", min_height=30, parent=demo_group)
            self._demo_flip_btn.setProperty("compact", "true")
            self._demo_flip_btn.setToolTip(
                "Mô phỏng hiệu ứng lật thẻ 3D cho thẻ đang chọn"
            )
            self._demo_flip_btn.clicked.connect(self.demo_flip_requested.emit)
            demo_row.addWidget(self._demo_flip_btn)

            self._demo_reduced_btn = StyledButton("Giảm hiệu ứng: Tắt", variant="ghost", min_height=30, parent=demo_group)
            self._demo_reduced_btn.setProperty("compact", "true")
            self._demo_reduced_btn.setToolTip("Bật hoặc tắt chế độ giảm chuyển động")
            self._demo_reduced_btn.clicked.connect(self._on_demo_reduced_clicked)
            demo_row.addWidget(self._demo_reduced_btn)

            # Collapsed by default to keep Gameplay Top Bar clean and focused; toggle via compact QA button
            self._demo_group = demo_group
            self._demo_group.setVisible(False)
            top_layout.addWidget(demo_group)

            self._demo_qa_toggle_btn = StyledButton("Công cụ thử", variant="ghost", min_height=28, parent=top_bar)
            self._demo_qa_toggle_btn.setProperty("compact", "true")
            self._demo_qa_toggle_btn.setToolTip("Ẩn hoặc hiện thanh công cụ xem thử nhanh")
            self._demo_qa_toggle_btn.clicked.connect(
                lambda: self._demo_group.setVisible(not self._demo_group.isVisible())
            )
            top_layout.addWidget(self._demo_qa_toggle_btn)
        else:
            self._demo_group = None
            self._demo_qa_toggle_btn = None
            self._demo_flip_btn = None
            self._demo_reduced_btn = None

        self._tutorial_button = StyledButton("? Tân thủ", variant="ghost", min_height=32, parent=top_bar)
        self._tutorial_button.setToolTip("Mở bài hướng dẫn riêng; giữ nguyên ván hiện tại")
        self._tutorial_button.clicked.connect(self.tutorial_requested.emit)
        top_layout.addWidget(self._tutorial_button)

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
        banner_wrap.setContentsMargins(SPACING.space_3, 2, SPACING.space_3, 0)
        self._notification_banner = NotificationBanner(parent=self)
        banner_wrap.addWidget(self._notification_banner)
        self.body_layout.addLayout(banner_wrap)

        # ------------------------------------------------------------------
        # 3. MAIN WORKSPACE: Full-Height QSplitter over Cozy Dark Study Desk
        #    Left (~58%): Hero GameBoard (clues hang under each revealed card)
        #    Right: readable public clue + tabbed Nháp / deduction journal
        # ------------------------------------------------------------------
        workspace_wrap = QHBoxLayout()
        workspace_wrap.setContentsMargins(SPACING.space_3, 6, SPACING.space_3, 6)
        workspace_wrap.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setObjectName("GameplaySplitter")
        self._splitter.setChildrenCollapsible(False)

        # Left column: Dominant full-height GameBoard
        self._left_column = QWidget(self._splitter)
        self._left_column.setObjectName("GameplayHeroColumn")
        self._left_column.setMinimumWidth(460)
        left_layout = QVBoxLayout(self._left_column)
        left_layout.setContentsMargins(0, 0, SPACING.space_2, 0)
        left_layout.setSpacing(0)

        self._board_panel = StyledPanel(
            variant="translucent",
            padding=3,
            accent_bar=None,
            parent=self._left_column,
        )
        self._board_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._board_panel.setMinimumWidth(440)

        self._game_board = GameBoard(
            pixmap_loader=pixmap_loader,
            motion_config=MotionConfig(card_flip_duration=DEFAULT_MOTION.assisted_flip_duration),
            parent=self._board_panel,
        )
        self._game_board.card_selected.connect(self._on_board_card_selected)
        self._game_board.background_clicked.connect(self.clear_highlights)
        self._game_board.animation_finished.connect(self._on_board_animation_finished)
        self._game_board.animation_cancelled.connect(self.animation_cancelled.emit)
        self._game_board.clue_clicked.connect(self._on_clue_selected)
        self._game_board.clue_hovered.connect(self._on_clue_hovered)
        self._game_board.clue_hover_left.connect(self._on_clue_hover_left)
        self._game_board.clue_used_toggled.connect(self._on_clue_used_toggled)
        self._game_board.draft_marks_changed.connect(self._refresh_draft_summary)
        self._board_panel.content_layout.addWidget(self._game_board, 1)
        left_layout.addWidget(self._board_panel, 1)

        self._splitter.addWidget(self._left_column)

        # Right column: clue visibility toggle + public counts + Nháp + Deduction trace
        self._sidebar_widget = QWidget(self._splitter)
        self._sidebar_widget.setObjectName("GameplaySidebar")
        self._sidebar_widget.setMinimumWidth(320)
        self._sidebar_widget.setMaximumWidth(460)
        sidebar_layout = QVBoxLayout(self._sidebar_widget)
        sidebar_layout.setContentsMargins(SPACING.space_2, 0, 0, 0)
        sidebar_layout.setSpacing(8)

        self._clue_tools_panel = QFrame(self._sidebar_widget)
        self._clue_tools_panel.setObjectName("InvestigationSummary")
        self._clue_tools_panel.setStyleSheet(
            "QFrame#InvestigationSummary {background:#F3EBD9; border:1px solid #CDBB98; border-radius:8px;}"
            "QFrame#InvestigationSummary QLabel {color:#33475A; background:transparent; border:none;}"
        )
        summary_layout = QVBoxLayout(self._clue_tools_panel)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(5)
        clue_tools = QHBoxLayout()
        clue_tools.setContentsMargins(0, 0, 0, 0)
        clue_tools.setSpacing(6)
        self._clue_hint_label = QLabel("SỔ ĐIỀU TRA", self._clue_tools_panel)
        self._clue_hint_label.setTextFormat(Qt.TextFormat.PlainText)
        self._clue_hint_label.setStyleSheet(
            "color: #536073; font-size: 11px; font-weight: 700; background: transparent;"
        )
        clue_tools.addWidget(self._clue_hint_label, 1)
        self._show_all_btn = StyledButton(
            "Hiện tất cả manh mối", variant="ghost", min_height=30, parent=self._sidebar_widget
        )
        self._show_all_btn.setProperty("compact", "true")
        self._show_all_btn.setToolTip(
            "Mặc định manh mối đã dùng hết (mọi ô liên quan đã lật) được thu gọn. "
            "Bấm để hiện lại tất cả."
        )
        self._show_all_btn.clicked.connect(self._on_show_all_clicked)
        clue_tools.addWidget(self._show_all_btn)
        summary_layout.addLayout(clue_tools)

        # Public counts (replaces CluePanel.global_card): only already-proved verdicts
        self._public_counts_label = QLabel("Công khai: chưa có ô nào được chứng minh", self._sidebar_widget)
        self._public_counts_label.setTextFormat(Qt.TextFormat.PlainText)
        self._public_counts_label.setStyleSheet(
            "color: #263D51; font-size: 12px; font-weight: 600; background: transparent;"
        )
        self._public_counts_label.setWordWrap(True)
        summary_layout.addWidget(self._public_counts_label)
        sidebar_layout.addWidget(self._clue_tools_panel)

        self._clue_reader = ClueReader(parent=self._sidebar_widget)
        sidebar_layout.addWidget(self._clue_reader, 2)

        self._sidebar_tabs = QTabWidget(self._sidebar_widget)
        self._sidebar_tabs.setObjectName("InvestigationTabs")
        self._sidebar_tabs.setStyleSheet(TABS_STYLE)

        self._scratchpad = ScratchpadPanel(parent=self._sidebar_widget)
        self._sidebar_tabs.addTab(self._scratchpad, "Nháp cá nhân")

        self._deduction_panel = DeductionPanel(parent=self._sidebar_widget)
        self._deduction_panel.hint_changed.connect(self._on_hint_changed)
        self._sidebar_tabs.addTab(self._deduction_panel, "Nhật ký suy luận")
        sidebar_layout.addWidget(self._sidebar_tabs, 3)

        self._splitter.addWidget(self._sidebar_widget)
        self._splitter.setStretchFactor(0, 70)
        self._splitter.setStretchFactor(1, 30)
        self._splitter.setSizes([930, 400])

        workspace_wrap.addWidget(self._splitter, 1)
        self.body_layout.addLayout(workspace_wrap, 1)

        # ------------------------------------------------------------------
        # 4. UNIFIED BOTTOM PARCHMENT DOCK: ActionBar (Left) | ProgressPanel (Right)
        # ------------------------------------------------------------------
        bottom_dock = QFrame(self)
        bottom_dock.setObjectName("GameplayBottomDock")
        bottom_dock.setStyleSheet(
            "QFrame#GameplayBottomDock {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FBF5E8, stop:1 #EFE2C6);"
            "  border-top: 2px solid #C6A262;"
            "}"
        )
        dock_row = QHBoxLayout(bottom_dock)
        dock_row.setContentsMargins(SPACING.space_3, 4, SPACING.space_3, 4)
        dock_row.setSpacing(12)

        self._action_bar = ActionBar(demo_mode=self._demo_mode, parent=bottom_dock)
        self._action_bar.verdict_requested.connect(self.verdict_requested.emit)
        self._action_bar.level_selection_requested.connect(self.level_selection_requested.emit)
        self._action_bar.restart_requested.connect(self.restart_requested.emit)
        self._action_bar.restart_confirmation_requested.connect(self._show_restart_dialog)
        self._action_bar.hint_requested.connect(self.hint_requested.emit)
        self._action_bar.auto_solve_requested.connect(self.auto_solve_requested.emit)
        self._action_bar.auto_solve_speed_changed.connect(self.auto_solve_speed_changed.emit)
        self._action_bar.back_requested.connect(self.back_requested.emit)
        self._action_bar.demo_results_requested.connect(self.demo_results_requested.emit)
        # Dock navigation capsule (Đổi hồ sơ | Chơi lại | Trang chủ) into Top Bar
        self._action_bar.dock_navigation_bar(top_layout, top_layout.indexOf(self._status_pill))
        dock_row.addWidget(self._action_bar, 62)

        dock_divider = QFrame(bottom_dock)
        dock_divider.setFixedSize(1, 44)
        dock_divider.setStyleSheet("background-color: #D0B88C; border: none;")
        dock_row.addWidget(dock_divider, 0, Qt.AlignmentFlag.AlignVCenter)

        self._progress_panel = ProgressPanel(parent=bottom_dock)
        self._progress_panel.setObjectName("ProgressPanel")
        self._progress_panel.setStyleSheet(
            "QFrame#ProgressPanel { background: transparent; border: none; }"
        )
        self._action_bar.session_stats_updated.connect(self._progress_panel.set_session_metrics)
        dock_row.addWidget(self._progress_panel, 38)

        self.body_layout.addWidget(bottom_dock, 0)

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

    def set_board(self, snapshot: Any, *, preserve_hint: bool = False) -> None:
        """Render a complete public snapshot, syncing clues, progress, and selection."""
        norm: PublicBoardSnapshot = normalize_board_snapshot(snapshot)
        prev_kb = self._current_kb_version

        self._game_board.set_board(norm)
        self._current_kb_version = norm.kb_version

        n = self._game_board.grid_size
        pid = self._game_board.puzzle_id
        revealed_ids = frozenset(
            c.cell_id for c in norm.characters if c.visibility is CardVisibility.REVEALED
        )
        revealed_count = len(revealed_ids)
        self._case_label.setText(format_gameplay_case_header(pid, n))
        self._case_label.setToolTip(self._case_label.text())

        # Clue strips: remember which owners were just flipped so their clue stays open
        self._clues = tuple(norm.clues)
        if self._prev_revealed is None:
            self._fresh_owner_ids = frozenset()
        elif revealed_ids != self._prev_revealed:
            self._fresh_owner_ids = revealed_ids - self._prev_revealed
        self._prev_revealed = revealed_ids
        self._preview_clue_id = None
        self._preview_saved_targets = ()
        self._refresh_clue_notes()
        self._refresh_draft_summary()

        # Public verdict counts (only proved verdicts)
        criminals = sum(c.verdict == "CRIMINAL" for c in norm.characters)
        innocent = sum(c.verdict == "INNOCENT" for c in norm.characters)
        self._set_public_counts(criminals, innocent, len(norm.characters) - revealed_count)

        self._progress_panel.set_case_info(pid, n)
        self._progress_panel.set_progress(revealed_count, len(norm.characters))
        self._action_bar.set_session_stats(revealed_count, len(norm.characters),
                                           self.ui_state.hint_count, self.ui_state.mistake_count)

        # Per STAGE2_API_CONTRACT §D: when KB version advances, clear stale Hint
        # (skipped when caller is immediately keeping the active Auto-Solve explanation)
        if not preserve_hint and prev_kb is not None and norm.kb_version != prev_kb:
            self.clear_hint()

        self._sync_selected_character()
        for sz, btn in self._demo_size_buttons.items():
            btn.set_variant("primary" if sz == n else "ghost")

    def reset_for_new_case(self, snapshot: Any) -> None:
        """Prepare screen for a fresh Load/Restart (cancel flips, clear trace/hint/banner/highlights/Nháp)."""
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
        self._reset_clue_and_draft_state()
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
        """Propagate reduced-motion setting across board, panels, banners & dialogs."""
        flag = bool(enabled)
        self._game_board.set_reduced_motion(flag)
        self._notification_banner.set_reduced_motion(flag)
        self._restart_dialog.set_reduced_motion(flag)
        self._feedback_dialog.set_reduced_motion(flag)
        self._deduction_panel.set_reduced_motion(flag)
        self._progress_panel.set_reduced_motion(flag)
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
            self._refresh_clue_notes()
        return updated

    def set_clues(self, clues: Iterable[Any]) -> None:
        """Replace the public clues shown under the revealed cards (deduplicated by clue_id)."""
        seen: set[str] = set()
        normalized: list[PublicClueView] = []
        for raw in clues:
            clue = normalize_clue_view(raw)
            if clue.clue_id in seen:
                continue
            seen.add(clue.clue_id)
            normalized.append(clue)
        self._clues = tuple(normalized)
        self._refresh_clue_notes()

    def append_deduction_step(self, step: Any) -> bool:
        """Append one accepted deduction step (idempotent)."""
        added = self._deduction_panel.append_step(step)
        if added:
            self._sidebar_tabs.setCurrentWidget(self._deduction_panel)
        return added

    def set_deduction_trace(self, steps: Iterable[Any]) -> None:
        """Replace the full accepted deduction trace."""
        self._deduction_panel.set_steps(steps)

    def clear_deduction_trace(self) -> None:
        """Clear all accepted deduction trace steps."""
        self._deduction_panel.clear()

    def show_hint(self, hint: Any) -> None:
        """Render a temporary non-mutating HintView in DeductionPanel."""
        self._deduction_panel.show_hint(hint)
        self._sidebar_tabs.setCurrentWidget(self._deduction_panel)
        self.ui_state.active_hint = hint

    def animate_hint_flow(
        self,
        clue_ids: Iterable[str],
        supporting_cells: Iterable[str],
        target_cell_id: str,
    ) -> bool:
        clue_set = set(clue_ids)
        source_cells = list(supporting_cells)
        for clue in self._clues:
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

        auto_active = (
            self.ui_state.is_auto_solving
            and resolved in (GameState.READY, GameState.PROCESSING, GameState.ANIMATING)
        )
        if auto_active:
            self._status_pill.set_status("ĐANG TỰ GIẢI...", tone="accent")
        else:
            hdr_text, hdr_tone = _HEADER_STATE_STYLE[resolved]
            self._status_pill.set_status(hdr_text, tone=hdr_tone)
        self._progress_panel.set_game_status(resolved)
        self._action_bar.set_game_state(resolved)

        # Per STAGE2_API_CONTRACT §C: lock the board (cards AND their clue strips)
        # during PROCESSING/ANIMATING/auto-solve. The Nháp stays editable at all times.
        interactive = (
            resolved in (GameState.READY, GameState.STUCK, GameState.SOLVED)
            and not auto_active
        )
        self._game_board.set_interactive(interactive)

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
                kicker="CHƯA ĐỦ CHỨNG CỨ",
                title="Kết luận này vẫn còn hai khả năng hợp lệ",
                message=current.message,
                detail=(
                    "Hệ thống suy luận vẫn tìm được ít nhất một phương án hợp lệ cho mỗi giả thiết. "
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
                kicker="XUNG ĐỘT LOGIC",
                title="Giả thiết vừa chọn phá vỡ chuỗi chứng cứ",
                message=current.message,
                detail=(
                    "Giả thiết ngược lại đã được chứng minh từ tập chứng cứ hiện tại. "
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
        self._preview_clue_id = None
        self._preview_saved_targets = ()
        self._game_board.clear_highlights()
        self._focused_clue_ids = frozenset()
        self.ui_state.selected_clue_id = None
        self.ui_state.highlighted_targets = ()
        self._refresh_clue_notes()

    def focus_evidence(self, clue_ids: Iterable[str], cells: Iterable[str] = ()) -> None:
        ids = tuple(clue_ids)
        clues = [c for c in self._clues if c.clue_id in ids]
        cell_seq = list(dict.fromkeys(cells))
        target_cell = cell_seq[-1] if cell_seq else None
        owners = [c.owner_id for c in clues]
        primary = list(cell_seq)
        references: list[str] = []
        for clue in clues:
            primary.append(clue.owner_id)
            references.extend(clue.referenced_cells)
        self._preview_clue_id = None
        self._focused_clue_ids = frozenset(c.clue_id for c in clues)
        self.ui_state.selected_clue_id = clues[0].clue_id if clues else None
        self.ui_state.highlighted_targets = self._game_board.focus_evidence(
            primary,
            references,
            source_owners=owners,
            target_cell_id=target_cell,
        )
        self._refresh_clue_notes()

    # ------------------------------------------------------------------
    # Clue strips (under each revealed card) & clue visibility
    # ------------------------------------------------------------------

    def set_show_all_clues(self, show_all: bool) -> None:
        """Toggle between 'only important clues' and 'every clue expanded'."""
        self._show_all_clues = bool(show_all)
        if self._show_all_clues:
            self._show_all_btn.setText("Chỉ hiện manh mối quan trọng")
            self._show_all_btn.set_variant("primary")
        else:
            self._show_all_btn.setText("Hiện tất cả manh mối")
            self._show_all_btn.set_variant("ghost")
        self._refresh_clue_notes()

    def _on_show_all_clicked(self) -> None:
        self.set_show_all_clues(not self._show_all_clues)

    def _build_clue_notes(self) -> dict[str, ClueNote]:
        cards = self._game_board.cards_by_id
        revealed = {cid for cid, card in cards.items() if card.is_revealed}
        notes: dict[str, ClueNote] = {}
        for clue in self._clues:
            if clue.owner_id not in cards:
                continue
            refs = set(clue.referenced_cells) | set(clue.primary_cells) | set(clue.secondary_cells)
            selected = clue.clue_id in self._focused_clue_ids
            manual_used = clue.clue_id in self.ui_state.solved_clues
            exhausted = (
                bool(refs)
                and refs <= revealed
                and clue.owner_id not in self._fresh_owner_ids
            )
            spent = (
                not self._show_all_clues
                and not selected
                and (manual_used or exhausted)
            )
            notes[clue.owner_id] = ClueNote(
                clue_id=clue.clue_id,
                clue_type=clue.clue_type,
                text=clue.text,
                state="spent" if spent else "normal",
                selected=selected,
            )
        return notes

    def _refresh_clue_notes(self) -> None:
        self._game_board.set_clue_notes(self._build_clue_notes())
        if hasattr(self, "_clue_reader"):
            self._refresh_clue_reader()

    def _refresh_clue_reader(self, clue_id=None) -> None:
        active_id = clue_id or self.ui_state.selected_clue_id
        clue = next((c for c in self._clues if c.clue_id == active_id), None)
        if clue is None:
            clue = next((c for c in self._clues if c.scope == "ALL"), None)
        if clue is None and self._clues:
            clue = next((c for c in self._clues if c.owner_id in self._fresh_owner_ids), self._clues[0])
        self._clue_reader.set_clues((clue,) if clue else ())

    def _on_clue_used_toggled(self, clue_id: str) -> None:
        solved = self.ui_state.solved_clues
        if clue_id in solved:
            solved.discard(clue_id)
        else:
            solved.add(clue_id)
        self._refresh_clue_notes()

    def _render_clue_focus(self, clue_id: str) -> Optional[tuple[str, ...]]:
        """Draw the board focus (highlight + connectors) for one clue. Returns target ids."""
        clue = next((c for c in self._clues if c.clue_id == clue_id), None)
        if clue is None:
            return None
        comparative = clue.clue_type in _COMPARATIVE_TYPES
        primary = list(
            clue.primary_cells
            or (clue.referenced_cells[:1] if comparative else clue.referenced_cells)
        )
        secondary = list(
            clue.secondary_cells
            or (clue.referenced_cells[1:] if comparative else ())
        )
        return self._game_board.focus_clue_relation(
            owner_id=clue.owner_id,
            primary_cells=primary,
            secondary_cells=secondary,
            clue_type=clue.clue_type,
            relation_label=_relation_label(clue),
            scope=clue.scope,
            scope_label=clue.scope_label,
        )

    def _on_clue_selected(self, clue_id: str) -> None:
        # A click ends any hover preview and makes the clue the real focus
        self._preview_clue_id = None
        self._preview_saved_targets = ()
        # Clicking the already-focused clue again releases the focus
        if self.ui_state.selected_clue_id == clue_id and clue_id in self._focused_clue_ids:
            self.clear_highlights()
            return
        targets = self._render_clue_focus(clue_id)
        if targets is None:
            return
        self._focused_clue_ids = frozenset({clue_id})
        self.ui_state.selected_clue_id = clue_id
        self.ui_state.highlighted_targets = targets
        self._refresh_clue_notes()
        self.clue_selected.emit(clue_id)

    def _on_clue_hovered(self, clue_id: str) -> None:
        """Preview a clue's board effect while the pointer rests on its strip."""
        if not self._game_board.is_interactive:
            return
        if self._preview_clue_id is None:
            self._preview_saved_targets = tuple(self.ui_state.highlighted_targets)
        self._preview_clue_id = clue_id
        self._render_clue_focus(clue_id)
        self._refresh_clue_reader(clue_id)

    def _on_clue_hover_left(self, clue_id: str) -> None:
        if self._preview_clue_id != clue_id:
            return
        self._preview_clue_id = None
        selected = self.ui_state.selected_clue_id
        if selected and self._render_clue_focus(selected) is not None:
            pass
        elif self._preview_saved_targets:
            self._game_board.highlight_cells(self._preview_saved_targets)
        else:
            self._game_board.clear_highlights()
        self._preview_saved_targets = ()
        self._refresh_clue_reader()

    # ------------------------------------------------------------------
    # Public counts & Nháp (scratchpad & draft marks)
    # ------------------------------------------------------------------

    def _set_public_counts(self, criminals: int, innocent: int, hidden: int) -> None:
        if criminals + innocent == 0:
            self._public_counts_label.setText("Công khai: chưa có ô nào được chứng minh")
        else:
            self._public_counts_label.setText(
                f"Công khai: {criminals} tội phạm · {innocent} vô tội · {hidden} chưa chứng minh"
            )

    def _refresh_draft_summary(self) -> None:
        marks = self._game_board.draft_marks
        values = list(marks.values())
        self._scratchpad.set_mark_summary(
            values.count("?"), values.count("SUSPECT"), values.count("INNOCENT")
        )

    def _reset_clue_and_draft_state(self) -> None:
        """Forget clues, clue focus/usage, fresh-owner tracking, notes text and draft marks."""
        self._clues = ()
        self._focused_clue_ids = frozenset()
        self._fresh_owner_ids = frozenset()
        self._prev_revealed = None
        self._preview_clue_id = None
        self._preview_saved_targets = ()
        self.ui_state.solved_clues.clear()
        self._game_board.set_clue_notes({})
        self._game_board.clear_draft_marks()
        self._scratchpad.clear()
        self._clue_reader.set_clues(())
        self._sidebar_tabs.setCurrentWidget(self._scratchpad)
        self._set_public_counts(0, 0, 0)

    def _on_feedback_dismissed(self) -> None:
        self.ui_state.error_feedback = None

    def _on_hint_changed(self, hint) -> None:
        self.ui_state.active_hint = hint

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_top_bar"):
            self._top_bar.rebalance()

    @property
    def clue_reader(self) -> ClueReader:
        return self._clue_reader

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        # This filter is installed on QApplication. Modal help/tutorial windows
        # own their input; Escape there must not alter the board underneath.
        if isinstance(watched, QWidget) and watched.window() is not self.window():
            return False
        if self.isVisible():
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.clear_highlights()
                self._notification_banner.dismiss(animated=True)
                self._restart_dialog.close_animated()
                self._feedback_dialog.close_animated()
                return True
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                blank = (self, self._board_panel, self._sidebar_widget)
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
        self._game_board.clear_selection()
        self.ui_state = InteractionState()
        self._reset_clue_and_draft_state()
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
                "Các thẻ đã mở, nhật ký suy luận, highlight, bản nháp và dấu nháp "
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
    def tutorial_button(self) -> StyledButton:
        return self._tutorial_button

    @property
    def board_container(self) -> StyledPanel:
        return self._board_panel

    @property
    def clues(self) -> tuple[PublicClueView, ...]:
        """Public clues currently shown under the revealed cards."""
        return self._clues

    @property
    def show_all_clues(self) -> bool:
        return self._show_all_clues

    @property
    def public_counts_text(self) -> str:
        return self._public_counts_label.text()

    @property
    def scratchpad_panel(self) -> ScratchpadPanel:
        return self._scratchpad

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
