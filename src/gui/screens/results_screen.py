"""ResultsScreen — Centered Cream Editorial Case-Closed Dossier using A07 emblem.

Presents the post-case summary on a unified Warm Cream (#F5EFE4) canvas with a
consistent Deep Ink top masthead and a centered Soft Ivory (#FBF7F0) Case-Closed
Dossier Sheet showcasing ``A07_case_closed_emblem_clean.png`` and tabular
monospace metrics.
Never claims SOLVED without Controller ``ResultsView`` and never fabricates metrics.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.page_header import PageHeader
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.screens.backdrop_screen import BackdropScreen
from src.gui.styles.tokens import COLORS, SPACING
from src.gui.view_models import ResultsView, normalize_results_view


def _format_elapsed_ms(elapsed_ms: Optional[float]) -> str:
    if elapsed_ms is None:
        return "—"
    seconds = elapsed_ms / 1000.0
    if seconds < 60.0:
        return f"{seconds:.1f} giây"
    minutes = int(seconds // 60)
    rem = seconds - minutes * 60
    return f"{minutes} phút {rem:.1f} giây"


class ResultsScreen(BackdropScreen):
    """Centered Cream Editorial Case-Closed Dossier Results screen."""

    restart_requested = Signal()
    load_requested = Signal(str)  # Next puzzle ID when results.next_puzzle_id is not None
    level_selection_requested = Signal()
    back_requested = Signal()
    # Backward-compatible Phase 2 demo aliases
    demo_gameplay_requested = Signal()
    demo_levels_requested = Signal()

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            AssetId.A05_GAMEPLAY_BACKGROUND,
            scrim_rgba=COLORS.scrim_gameplay_rgba,
            pixmap_loader=pixmap_loader,
            parent=parent,
        )
        self.setObjectName("ResultsScreen")
        self._results: Optional[ResultsView] = None

        # Unified Top Editorial Masthead
        top_back_btn = StyledButton("← Menu chính", variant="ghost", min_height=44, parent=self)
        top_back_btn.clicked.connect(self.back_requested.emit)

        self._mode_badge = StatusLabel("TỔNG KẾT HỒ SƠ · CHƯA CÓ KẾT QUẢ", tone="accent", parent=self)
        header = PageHeader(
            "Biên Bản Khép Án — Case Closed",
            subtitle="Tổng kết hồ sơ điều tra & chỉ số suy luận công khai",
            left_widget=top_back_btn,
            right_widget=self._mode_badge,
            parent=self,
        )
        self.body_layout.addWidget(header)

        outer = QVBoxLayout()
        outer.setContentsMargins(SPACING.space_5, SPACING.space_4, SPACING.space_5, SPACING.space_4)
        outer.setSpacing(SPACING.space_3)
        self.body_layout.addLayout(outer, 1)

        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)

        # Centered Soft Ivory Case-Closed Dossier Sheet
        card = StyledPanel(variant="dossier", padding=SPACING.space_5, accent_bar="brass", parent=self)
        card.setMinimumWidth(600)
        card.setMaximumWidth(760)
        card.content_layout.setSpacing(SPACING.space_3)

        # Compact Centered Deep Ink Emblem Medallion (no oversized dark rectangle)
        emblem_wrap = QHBoxLayout()
        emblem_wrap.addStretch(1)

        emblem_badge = QFrame(card)
        emblem_badge.setProperty("widgetKind", "emblemBadge")
        emblem_badge.setFixedSize(268, 162)
        plate_lay = QVBoxLayout(emblem_badge)
        plate_lay.setContentsMargins(SPACING.space_3, SPACING.space_2, SPACING.space_3, SPACING.space_2)

        self._emblem_view = AssetImageView(
            AssetId.A07_CASE_CLOSED_EMBLEM,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            overlay_text="CASE CLOSED",
            overlay_rect_ratio=(0.17, 0.49, 0.66, 0.16),
            pixmap_loader=pixmap_loader,
            parent=emblem_badge,
        )
        self._emblem_view.setMinimumHeight(138)
        self._emblem_view.setMaximumHeight(146)
        plate_lay.addWidget(self._emblem_view)

        emblem_wrap.addWidget(emblem_badge)
        emblem_wrap.addStretch(1)
        card.content_layout.addLayout(emblem_wrap)

        hero_sub = QLabel("Biên Bản Tổng Kết Điều Tra", card)
        hero_sub.setProperty("role", "paperTitle")
        hero_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.content_layout.addWidget(hero_sub)

        self._notice_label = QLabel("Chưa nhận dữ liệu tổng kết từ Controller.", card)
        self._notice_label.setTextFormat(Qt.TextFormat.PlainText)
        self._notice_label.setProperty("role", "paperCaption")
        self._notice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notice_label.setWordWrap(True)
        self._notice_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card.content_layout.addWidget(self._notice_label)

        # Editorial Ledger Table on Soft Ivory (hairline rows, monospace right-aligned metrics)
        ledger_rule = QFrame(card)
        ledger_rule.setProperty("widgetKind", "paperRule")
        card.content_layout.addWidget(ledger_rule)

        grid = QGridLayout()
        grid.setContentsMargins(SPACING.space_2, SPACING.space_1, SPACING.space_2, SPACING.space_1)
        grid.setHorizontalSpacing(SPACING.space_5)
        grid.setVerticalSpacing(SPACING.space_2)

        stat_keys = (
            ("puzzle_id", "Mã vụ án (Puzzle ID)"),
            ("grid_size", "Kích thước lưới"),
            ("revealed", "Nhân vật đã lật"),
            ("accepted_steps", "Số bước suy luận hợp lệ"),
            ("hint_requests", "Số lần dùng Hint"),
            ("elapsed_ms", "Thời gian hoàn thành"),
            ("sat_calls", "Số truy vấn SAT"),
        )
        self._value_labels: dict[str, QLabel] = {}
        for idx, (key, caption) in enumerate(stat_keys):
            kl = QLabel(caption, card)
            kl.setProperty("role", "paperSecondary")
            vl = QLabel("—", card)
            vl.setTextFormat(Qt.TextFormat.PlainText)
            vl.setProperty("role", "paperMono")
            vl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(kl, idx, 0)
            grid.addWidget(vl, idx, 1)
            self._value_labels[key] = vl
        grid.setColumnStretch(1, 1)

        card.content_layout.addLayout(grid)

        ledger_rule_bot = QFrame(card)
        ledger_rule_bot.setProperty("widgetKind", "paperRule")
        card.content_layout.addWidget(ledger_rule_bot)

        # 3-Tier Editorial Action Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING.space_2)

        self._restart_btn = StyledButton("Chơi lại", variant="paperSecondary", min_height=44, parent=card)
        self._restart_btn.setToolTip("Gửi yêu cầu chơi lại vụ án này")
        self._restart_btn.clicked.connect(self._on_restart_clicked)
        btn_row.addWidget(self._restart_btn, 1)

        self._next_btn = StyledButton("Vụ án tiếp theo →", variant="inkPrimary", min_height=44, parent=card)
        self._next_btn.setEnabled(False)
        self._next_btn.setToolTip("Mở vụ án kế tiếp trong danh mục")
        self._next_btn.clicked.connect(self._on_next_clicked)
        btn_row.addWidget(self._next_btn, 1)

        self._levels_btn = StyledButton("Kho hồ sơ", variant="paperSecondary", min_height=44, parent=card)
        self._levels_btn.setToolTip("Quay lại màn hình chọn vụ án")
        self._levels_btn.clicked.connect(self._on_levels_clicked)
        btn_row.addWidget(self._levels_btn, 1)

        self._menu_btn = StyledButton("Menu chính", variant="paperGhost", min_height=44, parent=card)
        self._menu_btn.setToolTip("Quay lại màn hình chính")
        self._menu_btn.clicked.connect(self.back_requested.emit)
        btn_row.addWidget(self._menu_btn, 1)

        card.content_layout.addLayout(btn_row)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)

        outer.addStretch(1)

    # ------------------------------------------------------------------
    # Public API & Properties (100% preserved)
    # ------------------------------------------------------------------

    def set_results(self, raw_results: Any) -> None:
        results = normalize_results_view(raw_results)
        self._results = results

        if results.is_demo_preview:
            self._mode_badge.set_status("XEM TRƯỚC DEMO · DỮ LIỆU MẪU", tone="warning")
            self._notice_label.setText(
                "CHẾ ĐỘ XEM TRƯỚC GIAO DIỆN (PREVIEW DATA) — Chưa chạy Logic Agent / SAT thật."
            )
        else:
            self._mode_badge.set_status("✓ CASE CLOSED · ĐÃ CHỨNG MINH", tone="success")
            self._notice_label.setText(
                "Vụ án đã được phá giải hoàn toàn theo quy tắc No-Guess."
            )

        self._value_labels["puzzle_id"].setText(results.puzzle_id)
        self._value_labels["grid_size"].setText(
            f"{results.grid_size}×{results.grid_size}" if results.grid_size else "—"
        )
        self._value_labels["revealed"].setText(f"{results.revealed} / {results.total}")
        self._value_labels["accepted_steps"].setText(str(results.accepted_steps))
        self._value_labels["hint_requests"].setText(str(results.hint_requests))
        self._value_labels["elapsed_ms"].setText(_format_elapsed_ms(results.elapsed_ms))
        self._value_labels["sat_calls"].setText(
            str(results.sat_calls) if results.sat_calls is not None else "—"
        )

        has_next = results.next_puzzle_id is not None
        self._next_btn.setEnabled(has_next)
        if has_next:
            self._next_btn.setToolTip(f"Mở vụ án kế tiếp: {results.next_puzzle_id}")
        else:
            self._next_btn.setToolTip("Không có vụ án tiếp theo trong danh mục")

    def clear_results(self) -> None:
        self._results = None
        self._mode_badge.set_status("TỔNG KẾT HỒ SƠ · CHƯA CÓ KẾT QUẢ", tone="accent")
        self._notice_label.setText("Chưa nhận dữ liệu tổng kết từ Controller.")
        for lbl in self._value_labels.values():
            lbl.setText("—")
        self._next_btn.setEnabled(False)

    @property
    def results(self) -> Optional[ResultsView]:
        return self._results

    @property
    def emblem_view(self) -> AssetImageView:
        return self._emblem_view

    @property
    def restart_button(self) -> StyledButton:
        return self._restart_btn

    @property
    def next_puzzle_button(self) -> StyledButton:
        return self._next_btn

    @property
    def levels_button(self) -> StyledButton:
        return self._levels_btn

    @property
    def menu_button(self) -> StyledButton:
        return self._menu_btn

    @property
    def value_labels(self) -> dict[str, QLabel]:
        return dict(self._value_labels)

    @property
    def notice_label(self) -> QLabel:
        return self._notice_label

    def _on_restart_clicked(self) -> None:
        self.restart_requested.emit()
        self.demo_gameplay_requested.emit()

    def _on_next_clicked(self) -> None:
        if self._results is not None and self._results.next_puzzle_id is not None:
            self.load_requested.emit(self._results.next_puzzle_id)

    def _on_levels_clicked(self) -> None:
        self.level_selection_requested.emit()
        self.demo_levels_requested.emit()
