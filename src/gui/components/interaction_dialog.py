"""Cinematic, reusable interaction dialog for restart and logic feedback."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.styled_button import StyledButton
from src.gui.animations.motion_config import DEFAULT_MOTION
from src.gui.animations.motion_tokens import (
    EASE_AWAY,
    EASE_SOFT,
    SHIFT_TABS,
    SPRING_DIALOG,
    build_easing,
)
from src.gui.styles.tokens import SPACING


class InteractionDialog(QDialog):
    """Frameless modal/tool dialog with tone-specific editorial styling."""

    confirmed = Signal()
    inspect_requested = Signal()
    dismissed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveInteractionDialog")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(560)
        self.setMaximumWidth(680)
        self._tone = "info"
        self._closing = False
        self._reduced_motion = bool(DEFAULT_MOTION.reduced_motion)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)

        self.panel = QFrame(self)
        self.panel.setProperty("widgetKind", "interactionDialog")
        self.panel.setProperty("tone", self._tone)
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(8, 15, 28, 145))
        self.panel.setGraphicsEffect(shadow)
        outer.addWidget(self.panel)

        root = QVBoxLayout(self.panel)
        root.setContentsMargins(SPACING.space_4, SPACING.space_4, SPACING.space_4, SPACING.space_4)
        root.setSpacing(SPACING.space_3)

        header = QHBoxLayout()
        header.setSpacing(SPACING.space_3)
        self.icon_label = QLabel("?", self.panel)
        self.icon_label.setProperty("widgetKind", "interactionDialogIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(64, 64)
        header.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.kicker_label = QLabel("PHẢN HỒI SUY LUẬN", self.panel)
        self.kicker_label.setProperty("role", "paperMono")
        self.title_label = QLabel("", self.panel)
        self.title_label.setProperty("role", "pageTitle")
        self.title_label.setWordWrap(True)
        title_col.addWidget(self.kicker_label)
        title_col.addWidget(self.title_label)
        header.addLayout(title_col, 1)
        root.addLayout(header)

        self.message_label = QLabel("", self.panel)
        self.message_label.setProperty("role", "paperBody")
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        root.addWidget(self.message_label)

        self.detail_frame = QFrame(self.panel)
        self.detail_frame.setProperty("widgetKind", "interactionDialogDetail")
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(SPACING.space_3, SPACING.space_2, SPACING.space_3, SPACING.space_2)
        self.detail_label = QLabel("", self.detail_frame)
        self.detail_label.setProperty("role", "paperCaption")
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(self.detail_label)
        root.addWidget(self.detail_frame)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.inspect_button = StyledButton(
            "◎ Soi điểm mâu thuẫn", variant="paperSecondary", parent=self.panel
        )
        self.inspect_button.clicked.connect(self._inspect)
        self.cancel_button = StyledButton("Đóng", variant="paperGhost", parent=self.panel)
        self.cancel_button.clicked.connect(self.close_animated)
        self.confirm_button = StyledButton("Xác nhận", variant="danger", parent=self.panel)
        self.confirm_button.clicked.connect(self._confirm)
        actions.addWidget(self.inspect_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.confirm_button)
        root.addLayout(actions)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._slide = QPropertyAnimation(self, b"pos", self)
        self._motion = QParallelAnimationGroup(self)
        self._motion.addAnimation(self._fade)
        self._motion.addAnimation(self._slide)
        self._motion.finished.connect(self._finish_close_if_needed)

    def configure(
        self,
        *,
        tone: str,
        icon: str,
        kicker: str,
        title: str,
        message: str,
        detail: str,
        confirm_text: str = "",
        cancel_text: str = "Đóng",
        allow_inspect: bool = False,
        modal: bool = False,
    ) -> None:
        self._tone = tone
        self.panel.setProperty("tone", tone)
        self.icon_label.setText(icon)
        self.kicker_label.setText(kicker)
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.detail_label.setText(detail)
        self.detail_frame.setVisible(bool(detail))
        self.inspect_button.setVisible(allow_inspect)
        self.confirm_button.setVisible(bool(confirm_text))
        self.confirm_button.setText(confirm_text or "Xác nhận")
        self.cancel_button.setText(cancel_text)
        self.setModal(modal)
        self.setWindowModality(
            Qt.WindowModality.WindowModal if modal else Qt.WindowModality.NonModal
        )
        self.panel.style().unpolish(self.panel)
        self.panel.style().polish(self.panel)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._closing = False
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            center = parent.mapToGlobal(parent.rect().center())
            target = center - self.rect().center()
            self.move(target)
        target_pos = self.pos()
        if self._reduced_motion:
            self.setWindowOpacity(1.0)
            self.move(target_pos)
            return
        self.setWindowOpacity(0.0)
        self.move(target_pos.x(), target_pos.y() + int(SHIFT_TABS))
        enter_ms = DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.dialog_enter_duration)
        self._fade.setDuration(max(1, enter_ms - 30))
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(build_easing(EASE_SOFT))
        self._slide.setDuration(DEFAULT_MOTION.scaled_ms(SPRING_DIALOG.duration_ms))
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(target_pos)
        self._slide.setEasingCurve(build_easing(SPRING_DIALOG, tempo=DEFAULT_MOTION.tempo))
        self._motion.start()

    def close_animated(self) -> None:
        if self._closing or not self.isVisible():
            return
        if self._reduced_motion:
            self.force_close()
            self.dismissed.emit()
            return
        self._closing = True
        self._motion.stop()
        exit_ms = DEFAULT_MOTION.scaled_ms(DEFAULT_MOTION.dialog_exit_duration)
        self._fade.setDuration(exit_ms)
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(build_easing(EASE_AWAY))
        self._slide.setDuration(exit_ms)
        self._slide.setStartValue(self.pos())
        self._slide.setEndValue(self.pos())
        self._motion.start()

    def _finish_close_if_needed(self) -> None:
        if self._closing:
            self._closing = False
            self.hide()
            self.setWindowOpacity(1.0)
            self.dismissed.emit()

    def _confirm(self) -> None:
        self.confirmed.emit()
        self.close_animated()

    def _inspect(self) -> None:
        self.inspect_requested.emit()
        self.close_animated()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close_animated()
            event.accept()
            return
        super().keyPressEvent(event)

    def force_close(self) -> None:
        if self._motion.state() == QAbstractAnimation.State.Running:
            self._motion.stop()
        self._closing = False
        self.hide()
        self.setWindowOpacity(1.0)

