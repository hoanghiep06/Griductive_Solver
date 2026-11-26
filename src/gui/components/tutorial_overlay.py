"""Spotlight layer with live widget/scene coordinates and guarded input.

The underlying view supplies rectangles in overlay coordinates. No grid pixel
sizes are hardcoded here; resize, scroll and graphics-view transforms all use
the same mapping for painting and hit testing.
"""

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class TutorialOverlay(QWidget):
    next_requested = Signal()
    skip_requested = Signal()
    activated = Signal(str)

    def __init__(self, parent, geometry_provider, tooltip_slot, skip_slot):
        super().__init__(parent)
        self.setObjectName("TutorialOverlay")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self._provider = geometry_provider
        self._tooltip_slot = tooltip_slot
        self._skip_slot = skip_slot
        self._phase = 0.0
        self._reduced_motion = False
        self._target = None
        self._step_index = -1
        self._can_advance = False
        self._busy = False

        self.panel = QFrame(self)
        self.panel.setObjectName("TutorialCoach")
        self.panel.setStyleSheet(
            "QFrame#TutorialCoach {background:#FBF6EB; border:1px solid #CDBB98; border-radius:10px;}"
            "QFrame#TutorialCoach QLabel {color:#233247; background:transparent; border:none; font-size:14px;}"
            "QFrame#TutorialCoach QLabel#TutorialTitle {font-size:18px; font-weight:700; color:#142438;}"
            "QFrame#TutorialCoach QLabel#TutorialProgress {color:#796035; font-size:11px; font-weight:700;}"
            "QFrame#TutorialCoach QLabel#TutorialFeedback {color:#77501C; font-weight:600;}"
            "QFrame#TutorialCoach QScrollArea, QFrame#TutorialCoach QWidget#TutorialCopy {background:transparent; border:none;}"
            "QFrame#TutorialCoach QPushButton {min-height:32px; padding:3px 12px; border:1px solid #B49359;"
            "border-radius:6px; background:#233950; color:#FFF4DB; font-weight:700;}"
            "QFrame#TutorialCoach QPushButton:disabled {background:#DED5C2; color:#6E6657;}"
            "QFrame#TutorialCoach QPushButton:focus {border:2px solid #229FC2;}"
        )
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)
        self.progress_label = QLabel(self.panel)
        self.progress_label.setObjectName("TutorialProgress")
        layout.addWidget(self.progress_label)
        self.title_label = QLabel(self.panel)
        self.title_label.setObjectName("TutorialTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.scroll = QScrollArea(self.panel)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        copy = QWidget(self.scroll)
        copy.setObjectName("TutorialCopy")
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 6, 0)
        copy_layout.setSpacing(9)
        self.copy_labels = []
        for _ in range(3):
            label = QLabel(copy)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setAlignment(Qt.AlignmentFlag.AlignTop)
            copy_layout.addWidget(label)
            self.copy_labels.append(label)
        copy_layout.addStretch(1)
        self.scroll.setWidget(copy)
        layout.addWidget(self.scroll, 1)

        self.feedback_label = QLabel(self.panel)
        self.feedback_label.setObjectName("TutorialFeedback")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.feedback_label)
        row = QHBoxLayout()
        self.select_button = QPushButton(self.panel)
        self.select_button.clicked.connect(self._select_target)
        row.addWidget(self.select_button)
        self.next_button = QPushButton("Tiếp tục →", self.panel)
        self.next_button.clicked.connect(self.next_requested.emit)
        self.next_button.setAutoDefault(False)
        row.addWidget(self.next_button)
        layout.addLayout(row)
        self.skip_button = QPushButton("Bỏ qua hướng dẫn ×", self)
        self.skip_button.setAutoDefault(False)
        self.skip_button.setStyleSheet(
            "QPushButton {background:#233247; color:#FFF1D2; border:1px solid #CCAA66;"
            "border-radius:6px; padding:7px 12px;} QPushButton:focus {border:2px solid #55CCEB;}"
        )
        self.skip_button.clicked.connect(self.skip_requested.emit)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def present(self, step, index, total, *, can_advance, selected=False, busy=False, message=""):
        from html import escape

        self._target = step.target
        self._can_advance, self._busy = can_advance, busy
        self.progress_label.setText(f"HỒ SƠ TÂN THỦ  •  BƯỚC {index + 1}/{total}")
        self.title_label.setText(step.title)
        if self._step_index != index:
            for label, title, value in zip(
                self.copy_labels,
                ("Quan sát manh mối", "Phân tích điều kiện", "Suy ra kết quả"),
                (step.observation, step.analysis, step.conclusion),
            ):
                label.setText(f"<b>{title}</b><br>{escape(value)}")
            self.scroll.verticalScrollBar().setValue(0)
            self._step_index = index
        self.next_button.setText("Hoàn thành ✓" if step.focus == "complete" else "Tiếp tục →")
        self.next_button.setEnabled(can_advance and not busy)
        self.select_button.setText(f"Chọn ô {step.target}")
        self.select_button.setVisible(bool(step.target) and not can_advance and not selected and not busy)
        if not message:
            if busy:
                message = "Đang mở thẻ đã được chứng minh…"
            elif step.target and can_advance:
                message = f"✓ Đã mở {step.target}. Bấm Tiếp tục để đọc bước kế."
            elif step.target and selected:
                message = f"Đã chọn {step.target} · Hãy bấm phán quyết ở bên dưới."
            elif step.target:
                message = f"Đến lượt bạn: chạm ô {step.target} đang sáng."
            else:
                message = "Chạm nền tối hoặc bấm Tiếp tục. Esc để thoát."
        self.feedback_label.setText(message)
        self.refresh_geometry()
        self.update()

    def _select_target(self):
        if self._target and not self._can_advance and not self._busy:
            self.activated.emit(f"cell:{self._target}")

    def set_reduced_motion(self, enabled):
        self._reduced_motion = bool(enabled)
        if enabled:
            self._timer.stop()
            self._phase = 0.0
        elif self.isVisible():
            self._timer.start()
        self.update()

    def refresh_geometry(self):
        self.setGeometry(self.parentWidget().rect())
        slot = self._tooltip_slot
        origin = self.mapFromGlobal(slot.mapToGlobal(slot.rect().topLeft()))
        self.panel.setGeometry(origin.x(), origin.y(), slot.width(), slot.height())
        skip_rect = self._skip_slot.rect()
        origin = self.mapFromGlobal(self._skip_slot.mapToGlobal(skip_rect.topLeft()))
        self.skip_button.setGeometry(origin.x(), origin.y(), skip_rect.width(), skip_rect.height())
        self.raise_()

    def _tick(self):
        self._phase += 0.14
        self.update()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.refresh_geometry()
        if not self._reduced_motion:
            self._timer.start()

    def hideEvent(self, event):  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):  # noqa: N802
        highlights, _, pointer = self._provider()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        holes = QPainterPath()
        for rect in highlights:
            if rect.isEmpty():
                continue
            hole = QPainterPath()
            hole.addRoundedRect(rect, 7, 7)
            holes = holes.united(hole)
        backdrop = QPainterPath()
        backdrop.addRect(QRectF(self.rect()))
        p.fillPath(backdrop.subtracted(holes), QColor(8, 14, 23, 155))
        pulse = 0.5 + 0.5 * math.sin(self._phase)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for rect in highlights:
            for spread, alpha in ((3, 16), (2, 28), (1, 60)):
                p.setPen(QPen(QColor(255, 207, 105, int(alpha + pulse * 20)), spread * 2))
                p.drawRoundedRect(rect, 7, 7)
            p.setPen(QPen(QColor("#FFE3A0"), 2))
            p.drawRoundedRect(rect, 7, 7)
        if pointer is not None and not pointer.isEmpty() and not self._busy:
            # Arrowhead ends on the current live target boundary.
            above = pointer.top() >= 70
            sign = -1 if above else 1
            tip = QPointF(pointer.center().x(), pointer.top() if above else pointer.bottom())
            bounce = 0 if self._reduced_motion else 4 * math.sin(self._phase)
            base = tip + QPointF(0, sign * (18 + bounce))
            end = base + QPointF(0, sign * 20)
            p.setPen(QPen(QColor("#15263A"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(end, base)
            p.setPen(QPen(QColor("#FFE1A0"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(end, base)
            p.setPen(QPen(QColor("#15263A"), 2))
            p.setBrush(QColor("#FFE1A0"))
            p.drawPolygon(QPolygonF([tip, base + QPointF(-9, 0), base + QPointF(9, 0)]))
        p.end()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._activate_at(event.position())
        event.accept()

    def _activate_at(self, position):
        _, actions, _ = self._provider()
        if not self._busy:
            for key, rect in actions:
                if rect.contains(position):
                    self.activated.emit(key)
                    return
            if self._can_advance:
                self.next_requested.emit()

    def event(self, event):
        if event.type() in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            if event.type() == QEvent.Type.TouchEnd and event.points():
                # Use the same global-to-overlay mapping as widget targets.
                # This also handles touch events delivered from a native window.
                point = self.mapFromGlobal(event.points()[0].globalPosition().toPoint())
                self._activate_at(point)
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.skip_requested.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self._can_advance and not self._busy:
                self.next_requested.emit()
            else:
                self._select_target()
        else:
            super().keyPressEvent(event)
