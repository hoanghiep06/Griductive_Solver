"""Notification UI components & reusable How to Play dialog (Phase 4–5).

Provides:
- ``NotificationBanner``: non-blocking, dismissible notification bar with
  restrained Enter/Exit fade motion (210 ms / 170 ms), auto-dismiss for normal
  notices, persistent hold for critical errors, deduplication, and
  reduced-motion support.
- ``NotificationDialog``: optional modal detail dialog for critical/long alerts.
- ``HowToPlayDialog``: clean modal guide explaining No-Guess rules & 6 clue icons.

Strictly presentation-only: displays ``ActionResult`` messages supplied by
Controller without altering game state or revealing cards.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.animations.motion_config import DEFAULT_MOTION, MotionConfig
from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.styles.tokens import SPACING
from src.gui.view_models import (
    ActionCode,
    ActionResult,
    NotificationSeverity,
    normalize_action_result,
)

_SEVERITY_VISUALS: dict[NotificationSeverity, tuple[str, str, str]] = {
    NotificationSeverity.INFO: ("ℹ", "info", "THÔNG TIN"),
    NotificationSeverity.SUCCESS: ("✓", "success", "VERDICT CONFIRMED"),
    NotificationSeverity.WARNING: ("▲", "warning", "INSUFFICIENT EVIDENCE"),
    NotificationSeverity.ERROR: ("✕", "danger", "CONTRADICTED / ERROR"),
}

_ACTION_CODE_TITLES_VI: dict[ActionCode, str] = {
    ActionCode.ACCEPTED: "VERDICT CONFIRMED · Phán quyết được chứng minh (ACCEPTED)",
    ActionCode.NOT_PROVABLE: "INSUFFICIENT EVIDENCE · Chưa đủ cơ sở chứng minh (NOT_PROVABLE)",
    ActionCode.CONTRADICTED: "CONTRADICTED · Phán quyết mâu thuẫn với chứng cứ",
    ActionCode.INCONSISTENT: "INCONSISTENT · Cơ sở tri thức mâu thuẫn (KB UNSAT)",
    ActionCode.ALREADY_SOLVED: "ALREADY_SOLVED · Vụ án đã được phá giải",
    ActionCode.STALE_PROOF: "STALE_PROOF · Kết quả suy luận đã cũ",
    ActionCode.INVALID_REQUEST: "INVALID_REQUEST · Yêu cầu không hợp lệ",
    ActionCode.BUSY: "BUSY · Hệ thống đang xử lý",
    ActionCode.LOAD_FAILED: "LOAD_FAILED · Không thể nạp hồ sơ vụ án",
    ActionCode.CANCELLED: "CANCELLED · Thao tác đã được hủy",
    ActionCode.SOLVER_FAILED: "SOLVER_FAILED · Lỗi bộ giải SAT",
    ActionCode.INTERNAL_ERROR: "INTERNAL_ERROR · Lỗi hệ thống nội bộ",
}

_PERSISTENT_CODES = frozenset(
    {
        ActionCode.CONTRADICTED,
        ActionCode.INCONSISTENT,
        ActionCode.LOAD_FAILED,
        ActionCode.SOLVER_FAILED,
        ActionCode.INTERNAL_ERROR,
    }
)


class NotificationBanner(QFrame):
    """Non-blocking dismissible notification bar with smooth Enter/Exit motion."""

    dismissed = Signal()
    inspect_requested = Signal()

    def __init__(
        self,
        *,
        motion_config: MotionConfig = DEFAULT_MOTION,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NotificationBanner")
        self.setProperty("widgetKind", "notificationBanner")
        self.setProperty("severity", "info")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._motion_config = motion_config
        self._reduced_motion: bool = bool(motion_config.reduced_motion)
        self._current_result: Optional[ActionResult] = None
        self._last_dedup_key: Optional[tuple[ActionCode, Optional[str], str]] = None
        self._show_count: int = 0
        self._is_hiding: bool = False

        # Opacity animation effect for restrained fade-in / fade-out
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.finished.connect(self._on_fade_finished)

        # Auto-dismiss timer for non-critical notices (critical errors persist)
        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._on_auto_dismiss_timeout)

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACING.space_3, SPACING.space_2, SPACING.space_3, SPACING.space_2)
        row.setSpacing(SPACING.space_3)

        self._badge = StatusLabel("ℹ THÔNG TIN", tone="info", parent=self)
        self._badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self._title_label = QLabel("", self)
        self._title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._title_label.setProperty("role", "paperSubheading")
        self._title_label.setWordWrap(True)
        text_col.addWidget(self._title_label)

        self._message_label = QLabel("", self)
        self._message_label.setTextFormat(Qt.TextFormat.PlainText)
        self._message_label.setProperty("role", "paperBody")
        self._message_label.setWordWrap(True)
        self._message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        text_col.addWidget(self._message_label)

        row.addLayout(text_col, 1)

        self.inspect_button = StyledButton("◎ Soi điểm mâu thuẫn", variant="secondary", min_height=34, parent=self)
        self.inspect_button.clicked.connect(self.inspect_requested.emit)
        self.inspect_button.hide()
        row.addWidget(self.inspect_button)

        self._close_btn = StyledButton("Đóng", variant="ghost", min_height=34, parent=self)
        self._close_btn.setProperty("widgetKind", "compactButton")
        self._close_btn.setToolTip("Ẩn thông báo này")
        self._close_btn.clicked.connect(lambda: self.dismiss(animated=False))
        row.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setVisible(False)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)
        if self._reduced_motion and self._fade_anim.state() == QAbstractAnimation.State.Running:
            self._fade_anim.stop()
            if self._is_hiding:
                self._finalize_hidden()
            else:
                self._opacity_effect.setOpacity(1.0)

    def show_result(
        self,
        raw_result: Any,
        *,
        auto_dismiss: bool = True,
    ) -> ActionResult:
        """Display a normalized ``ActionResult`` cleanly with deduplication & enter motion."""
        result = normalize_action_result(raw_result)
        self.inspect_button.hide()
        dedup_key = (result.code, result.cell_id, result.message)

        # Deduplicate repeated identical active notifications cleanly
        if self.isVisible() and not self._is_hiding and dedup_key == self._last_dedup_key:
            self._schedule_auto_dismiss(result, auto_dismiss=auto_dismiss)
            return result

        self._current_result = result
        self._last_dedup_key = dedup_key
        self._show_count += 1
        self._is_hiding = False
        self._auto_dismiss_timer.stop()
        if self._fade_anim.state() == QAbstractAnimation.State.Running:
            self._fade_anim.stop()

        severity = result.severity or NotificationSeverity.INFO
        symbol, pill_tone, short_label = _SEVERITY_VISUALS[severity]
        if result.code is ActionCode.CONTRADICTED:
            short_label = "CONTRADICTED"
        elif result.code is ActionCode.INCONSISTENT:
            short_label = "INCONSISTENT"
        elif result.code in (ActionCode.LOAD_FAILED, ActionCode.SOLVER_FAILED, ActionCode.INTERNAL_ERROR):
            short_label = "ERROR"
        elif result.code is ActionCode.NOT_PROVABLE:
            symbol, short_label = "?", "CHƯA ĐỦ DỮ KIỆN"

        self.setProperty("severity", severity.value.lower())
        self._badge.set_status(f"{symbol} {short_label}", tone=pill_tone)

        title = _ACTION_CODE_TITLES_VI.get(result.code, result.code.value)
        if result.cell_id:
            title = f"{title} · Ô {result.cell_id}"
        self._title_label.setText(title)
        self._message_label.setText(result.message)

        self.style().unpolish(self)
        self.style().polish(self)
        self.setVisible(True)

        if self._reduced_motion:
            self._opacity_effect.setOpacity(1.0)
        else:
            self._opacity_effect.setOpacity(0.0)
            self._fade_anim.setDuration(max(1, int(self._motion_config.notification_enter_duration)))
            self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.start()

        self._schedule_auto_dismiss(result, auto_dismiss=auto_dismiss)
        self.update()
        return result

    def dismiss(self, *, animated: bool = False) -> None:
        """Hide banner immediately (default) or with smooth exit fade."""
        self._auto_dismiss_timer.stop()
        if not self.isVisible():
            self._current_result = None
            self._last_dedup_key = None
            self._is_hiding = False
            return

        if not animated or self._reduced_motion:
            if self._fade_anim.state() == QAbstractAnimation.State.Running:
                self._fade_anim.stop()
            self._finalize_hidden()
            return

        self._is_hiding = True
        if self._fade_anim.state() == QAbstractAnimation.State.Running:
            self._fade_anim.stop()
        self._fade_anim.setDuration(max(1, int(self._motion_config.notification_exit_duration)))
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _schedule_auto_dismiss(self, result: ActionResult, *, auto_dismiss: bool) -> None:
        self._auto_dismiss_timer.stop()
        if not auto_dismiss:
            return
        # Critical errors stay visible until user closes or new notice arrives
        if result.code in _PERSISTENT_CODES or result.severity is NotificationSeverity.ERROR:
            return
        ms = int(self._motion_config.notification_auto_dismiss_ms)
        if ms > 0:
            self._auto_dismiss_timer.start(ms)

    def _on_auto_dismiss_timeout(self) -> None:
        self.dismiss(animated=not self._reduced_motion)

    def _on_fade_finished(self) -> None:
        if self._is_hiding:
            self._finalize_hidden()

    def _finalize_hidden(self) -> None:
        self._is_hiding = False
        self._current_result = None
        self._last_dedup_key = None
        self._opacity_effect.setOpacity(1.0)
        self.setVisible(False)
        self.dismissed.emit()

    @property
    def current_result(self) -> Optional[ActionResult]:
        return self._current_result

    @property
    def show_count(self) -> int:
        return self._show_count

    @property
    def is_auto_dismiss_active(self) -> bool:
        return self._auto_dismiss_timer.isActive()

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def message_label(self) -> QLabel:
        return self._message_label

    @property
    def badge_label(self) -> StatusLabel:
        return self._badge

    @property
    def close_button(self) -> StyledButton:
        return self._close_btn


class NotificationDialog(QDialog):
    """Modal notification dialog for standalone or critical Controller alerts."""

    def __init__(
        self,
        raw_result: Any,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveNotificationDialog")
        self._result = normalize_action_result(raw_result)
        severity = self._result.severity or NotificationSeverity.INFO
        symbol, pill_tone, short_label = _SEVERITY_VISUALS[severity]

        self.setWindowTitle(f"Thông báo — GRIDUCTIVE ({self._result.code.value})")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.space_4, SPACING.space_4, SPACING.space_4, SPACING.space_4)
        root.setSpacing(SPACING.space_3)

        panel = StyledPanel(variant="dossier", padding=SPACING.space_4, accent_bar="brick", parent=self)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(SPACING.space_2)
        badge = StatusLabel(f"{symbol} {short_label}", tone=pill_tone, parent=panel)
        top_row.addWidget(badge)

        title_text = _ACTION_CODE_TITLES_VI.get(self._result.code, self._result.code.value)
        if self._result.cell_id:
            title_text = f"{title_text} · Ô {self._result.cell_id}"
        self._title_label = QLabel(title_text, panel)
        self._title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._title_label.setProperty("role", "paperSubheading")
        self._title_label.setWordWrap(True)
        top_row.addWidget(self._title_label, 1)
        panel.content_layout.addLayout(top_row)

        self._message_label = QLabel(self._result.message, panel)
        self._message_label.setTextFormat(Qt.TextFormat.PlainText)
        self._message_label.setProperty("role", "paperBody")
        self._message_label.setWordWrap(True)
        self._message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        panel.content_layout.addWidget(self._message_label)

        root.addWidget(panel)

        self._close_btn = StyledButton("Đã hiểu", variant="primary", parent=self)
        self._close_btn.clicked.connect(self.accept)
        root.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignRight)

    @property
    def result(self) -> ActionResult:
        return self._result

    @property
    def message_label(self) -> QLabel:
        return self._message_label


class HowToPlayDialog(QDialog):
    """Static UI modal dialog explaining confirmed No-Guess rules & 6 clue types."""

    def __init__(
        self,
        *,
        pixmap_loader: PixmapLoader,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveHowToPlayDialog")
        self.setProperty("surface", "paperCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Hướng dẫn chơi — GRIDUCTIVE")
        self.setMinimumSize(660, 560)
        self.resize(740, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.space_4, SPACING.space_4, SPACING.space_4, SPACING.space_4)
        root.setSpacing(SPACING.space_3)

        scroll = QScrollArea(self)
        scroll.setProperty("widgetKind", "cleanScroll")
        scroll.setWidgetResizable(True)

        body = QWidget(scroll)
        body.setProperty("surface", "paperCanvas")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, SPACING.space_2, 0)
        body_layout.setSpacing(SPACING.space_3)

        rules_panel = StyledPanel(
            title="Nguyên tắc No-Guess (Không đoán)",
            variant="dossier",
            padding=SPACING.space_4,
            accent_bar="brick",
            parent=body,
        )
        rules_text = QLabel(
            "1. Mỗi nghi phạm trên bàn cờ N×N (3×3, 4×4 hoặc 5×5) là CRIMINAL (Tội phạm) hoặc INNOCENT (Vô tội).\n"
            "2. Chỉ những thẻ đã lật mới tiết lộ manh mối công khai ở Bảng Chứng Cứ (CluePanel).\n"
            "3. Bạn chỉ được lật thẻ khi phán quyết CRIMINAL hoặc INNOCENT được chứng minh chắc chắn "
            "bằng logic mệnh đề (CNF + DPLL) từ tập manh mối công khai hiện tại.\n"
            "4. Phán quyết chưa đủ cơ sở sẽ nhận NOT_PROVABLE và KHÔNG lật thẻ; phán quyết trái với điều "
            "đã chứng minh sẽ nhận CONTRADICTED.\n"
            "5. Gợi ý (Hint) chỉ đề xuất một bước hợp lệ mà không tự lật thẻ; Tự giải (Auto Solve) giải từng bước không đoán.",
            rules_panel,
        )
        rules_text.setProperty("role", "paperBody")
        rules_text.setWordWrap(True)
        rules_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        rules_panel.content_layout.addWidget(rules_text)
        body_layout.addWidget(rules_panel)

        atlas_panel = StyledPanel(
            title="6 loại manh mối chuẩn",
            subtitle="FACT · SAME · DIFFERENT · EXACTLY · AT_LEAST · AT_MOST",
            variant="dossier",
            padding=SPACING.space_4,
            accent_bar="brass",
            parent=body,
        )
        atlas_view = AssetImageView(
            AssetId.A10_CLUE_ICON_ATLAS,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=False,
            pixmap_loader=pixmap_loader,
            parent=atlas_panel,
        )
        atlas_view.setMinimumHeight(290)
        atlas_view.setMaximumHeight(350)
        atlas_panel.content_layout.addWidget(atlas_view)
        body_layout.addWidget(atlas_panel)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        close_btn = StyledButton("Đóng hướng dẫn", variant="inkPrimary", parent=self)
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
