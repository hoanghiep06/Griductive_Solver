"""LevelSelectionScreen — Centered Cream Detective Case Archive.

Displays whitelisted ``LevelSummary`` entries grouped cleanly into 3×3, 4×4, and
5×5 Soft Ivory (#FBF7F0) investigation folders centered on a Warm Cream (#F5EFE4)
canvas, with Paper Beige (#EDE3D2) mats framing the 3 decorative ``A06_case_cover_*.png``
illustrations and a unified Cream Editorial selection bar at the bottom.
Never reads ``puzzles/*.json``, never reads ``hidden_solution``, and never
fabricates difficulty scores.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.case_tile import CaseTile
from src.gui.components.page_header import PageHeader
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.styles.tokens import SPACING
from src.gui.view_models import LevelSummary, normalize_level_summary

_GROUP_SPECS = (
    (3, "3x3", "Hồ sơ cơ bản · 3×3", "Bàn cờ 9 nghi phạm", AssetId.A06_CASE_COVER_3X3, "brass"),
    (4, "4x4", "Hồ sơ nâng cao · 4×4", "Bàn cờ 16 nghi phạm", AssetId.A06_CASE_COVER_4X4, "ink"),
    (5, "5x5", "Hồ sơ phức tạp · 5×5", "Bàn cờ 25 nghi phạm", AssetId.A06_CASE_COVER_5X5, "brick"),
)


class LevelSelectionScreen(QWidget):
    """Centered Cream Editorial Case Archive screen."""

    back_requested = Signal()
    load_requested = Signal(str)  # Canonical STAGE2_API_CONTRACT §C signal: puzzle_id
    demo_gameplay_requested = Signal(str)  # Backward-compatible demo quick-open

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        demo_mode: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LevelSelectionScreen")
        self.setProperty("surface", "paperCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._demo_mode = bool(demo_mode)

        self._levels: list[LevelSummary] = []
        self._tiles_by_id: dict[str, CaseTile] = {}
        self._selected_puzzle_id: Optional[str] = None
        self._cover_views: dict[str, AssetImageView] = {}
        self._preview_buttons: dict[str, StyledButton] = {}
        self._group_list_layouts: dict[int, QVBoxLayout] = {}
        self._group_empty_labels: dict[int, QLabel] = {}
        self._group_panels: dict[int, StyledPanel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Deep Ink Editorial Top Masthead
        self._back_button = StyledButton("← Màn hình chính", variant="ghost", parent=self)
        self._back_button.clicked.connect(self.back_requested.emit)

        self._catalog_badge = StatusLabel("15 VỤ ÁN", tone="accent", parent=self)
        header = PageHeader(
            "Kho Hồ Sơ Vụ Án",
            subtitle="Chọn một hồ sơ vụ án bên dưới để bắt đầu điều tra",
            left_widget=self._back_button,
            right_widget=self._catalog_badge,
            parent=self,
        )
        root.addWidget(header)

        # Scrollable Centered 3-Folder Archival Grid on Warm Cream
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget(self._scroll_area)
        content.setProperty("surface", "paperCanvas")
        outer_row = QHBoxLayout(content)
        outer_row.setContentsMargins(SPACING.space_5, SPACING.space_3, SPACING.space_5, SPACING.space_3)
        outer_row.addStretch(1)

        center_host = QWidget(content)
        center_host.setProperty("surface", "transparent")
        center_host.setMinimumWidth(900)
        center_host.setMaximumWidth(1440)
        center_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(center_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SPACING.space_3)

        groups_row = QHBoxLayout()
        groups_row.setSpacing(SPACING.space_4)

        for grid_size, key, title, subtitle, cover_asset, accent_bar in _GROUP_SPECS:
            panel = StyledPanel(
                title=title,
                subtitle=subtitle,
                variant="dossier",
                padding=SPACING.space_3,
                accent_bar=accent_bar,
                parent=center_host,
            )
            panel.setMinimumWidth(280)
            self._group_panels[grid_size] = panel

            # Decorative A06 4:3 cover framed inside a Paper Beige mat on Soft Ivory
            cover_mat = QFrame(panel)
            cover_mat.setProperty("widgetKind", "coverMat")
            mat_layout = QVBoxLayout(cover_mat)
            mat_layout.setContentsMargins(SPACING.space_2, SPACING.space_2, SPACING.space_2, SPACING.space_2)

            cover = AssetImageView(
                cover_asset,
                scale_mode=ImageScaleMode.CONTAIN,
                prefer_derived=False,
                pixmap_loader=pixmap_loader,
                parent=cover_mat,
            )
            cover.setMinimumHeight(156)
            cover.setMaximumHeight(192)
            mat_layout.addWidget(cover)
            panel.content_layout.addWidget(cover_mat)
            self._cover_views[key] = cover

            # Dynamic CaseTile archival index slips
            tiles_host = QWidget(panel)
            tiles_host.setProperty("surface", "transparent")
            tiles_layout = QVBoxLayout(tiles_host)
            tiles_layout.setContentsMargins(0, SPACING.space_1, 0, SPACING.space_1)
            tiles_layout.setSpacing(SPACING.space_2)

            empty_lbl = QLabel(
                f"Chưa có danh sách vụ án {key}.\nController sẽ nạp danh mục công khai tại đây.",
                tiles_host,
            )
            empty_lbl.setProperty("role", "paperCaption")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setWordWrap(True)
            tiles_layout.addWidget(empty_lbl)

            self._group_list_layouts[grid_size] = tiles_layout
            self._group_empty_labels[grid_size] = empty_lbl
            panel.content_layout.addWidget(tiles_host, 1)

            quick_btn = StyledButton(
                f"Mở nhanh nhóm {key}",
                variant="paperSecondary",
                min_height=40,
                parent=panel,
            )
            quick_btn.clicked.connect(
                lambda _checked=False, gs=grid_size, k=key: self._on_group_quick_open(gs, k)
            )
            quick_btn.setVisible(False)
            panel.content_layout.addWidget(quick_btn)
            self._preview_buttons[key] = quick_btn

            groups_row.addWidget(panel, 1)

        content_layout.addLayout(groups_row, 1)
        outer_row.addWidget(center_host, 10)
        outer_row.addStretch(1)
        self._scroll_area.setWidget(content)
        root.addWidget(self._scroll_area, 1)

        # Sticky Bottom Cream Editorial Selection Bar (Soft Ivory + Brass top accent)
        footer_wrap = QHBoxLayout()
        footer_wrap.setContentsMargins(SPACING.space_5, 0, SPACING.space_5, SPACING.space_3)
        footer_wrap.addStretch(1)

        footer_panel = StyledPanel(
            variant="dossier",
            padding=SPACING.space_2,
            accent_bar="brass",
            parent=self,
        )
        footer_panel.setMinimumWidth(900)
        footer_panel.setMaximumWidth(1440)
        footer_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(SPACING.space_3, 0, SPACING.space_3, 0)
        footer_row.setSpacing(SPACING.space_3)

        self._selection_label = QLabel(
            "CHƯA CHỌN VỤ ÁN: Nhấp vào một hồ sơ ở trên để xem chi tiết và mở bàn cờ.",
            footer_panel,
        )
        self._selection_label.setTextFormat(Qt.TextFormat.PlainText)
        self._selection_label.setProperty("role", "paperSubheading")
        self._selection_label.setWordWrap(True)
        self._selection_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        footer_row.addWidget(self._selection_label, 1)

        self._open_case_btn = StyledButton(
            "Mở hồ sơ vụ án →",
            variant="primary",
            min_height=44,
            parent=footer_panel,
        )
        self._open_case_btn.setEnabled(False)
        self._open_case_btn.clicked.connect(self._on_open_selected_clicked)
        footer_row.addWidget(self._open_case_btn)

        footer_panel.content_layout.addLayout(footer_row)
        footer_wrap.addWidget(footer_panel, 10)
        footer_wrap.addStretch(1)
        root.addLayout(footer_wrap)

    # ------------------------------------------------------------------
    # Public API & Properties (100% preserved)
    # ------------------------------------------------------------------

    def set_levels(self, levels: Iterable[Any]) -> None:
        normalized: list[LevelSummary] = []
        seen: set[str] = set()
        for raw in levels:
            item = normalize_level_summary(raw)
            if item.puzzle_id in seen:
                continue
            seen.add(item.puzzle_id)
            normalized.append(item)

        self._clear_tiles()
        self._levels = normalized

        counts = {3: 0, 4: 0, 5: 0}
        for summary in self._levels:
            layout = self._group_list_layouts.get(summary.grid_size)
            if layout is None:
                continue
            tile = CaseTile(summary, parent=self._group_panels[summary.grid_size])
            tile.case_selected.connect(self._on_tile_selected)
            tile.case_activated.connect(self._on_tile_activated)
            layout.addWidget(tile)
            self._tiles_by_id[summary.puzzle_id] = tile
            counts[summary.grid_size] += 1

        for gs, empty_lbl in self._group_empty_labels.items():
            empty_lbl.setVisible(counts[gs] == 0)

        total = len(self._levels)
        self._catalog_badge.set_status(f"KHO HỒ SƠ · {total} VỤ ÁN", tone="accent")

        if self._selected_puzzle_id not in self._tiles_by_id:
            self._selected_puzzle_id = None
            self._sync_selection_footer()

    def set_selected_puzzle(self, puzzle_id: Optional[str]) -> bool:
        if puzzle_id is None:
            if self._selected_puzzle_id and self._selected_puzzle_id in self._tiles_by_id:
                self._tiles_by_id[self._selected_puzzle_id].set_selected(False)
            self._selected_puzzle_id = None
            self._sync_selection_footer()
            return True

        tile = self._tiles_by_id.get(puzzle_id)
        if tile is None:
            return False
        if self._selected_puzzle_id and self._selected_puzzle_id in self._tiles_by_id:
            self._tiles_by_id[self._selected_puzzle_id].set_selected(False)
        self._selected_puzzle_id = puzzle_id
        tile.set_selected(True)
        self._sync_selection_footer()
        return True

    @property
    def back_button(self) -> StyledButton:
        return self._back_button

    @property
    def open_case_button(self) -> StyledButton:
        return self._open_case_btn

    @property
    def cover_views(self) -> dict[str, AssetImageView]:
        return dict(self._cover_views)

    @property
    def preview_buttons(self) -> dict[str, StyledButton]:
        return dict(self._preview_buttons)

    @property
    def case_tiles(self) -> dict[str, CaseTile]:
        return dict(self._tiles_by_id)

    @property
    def levels(self) -> tuple[LevelSummary, ...]:
        return tuple(self._levels)

    @property
    def selected_puzzle_id(self) -> Optional[str]:
        return self._selected_puzzle_id

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    def _clear_tiles(self) -> None:
        for tile in self._tiles_by_id.values():
            parent_layout = self._group_list_layouts.get(tile.summary.grid_size)
            if parent_layout is not None:
                parent_layout.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()
        self._tiles_by_id.clear()

    def _on_tile_selected(self, puzzle_id: str) -> None:
        self.set_selected_puzzle(puzzle_id)

    def _on_tile_activated(self, puzzle_id: str) -> None:
        if puzzle_id in self._tiles_by_id:
            self.load_requested.emit(puzzle_id)

    def _on_open_selected_clicked(self) -> None:
        if self._selected_puzzle_id and self._selected_puzzle_id in self._tiles_by_id:
            self.load_requested.emit(self._selected_puzzle_id)

    def _on_group_quick_open(self, grid_size: int, grid_key: str) -> None:
        first_in_group = next((lvl for lvl in self._levels if lvl.grid_size == grid_size), None)
        if first_in_group is not None:
            self.set_selected_puzzle(first_in_group.puzzle_id)
            self.load_requested.emit(first_in_group.puzzle_id)
        else:
            self.demo_gameplay_requested.emit(grid_key)

    def _sync_selection_footer(self) -> None:
        tile = self._tiles_by_id.get(self._selected_puzzle_id or "")
        if tile is None:
            self._selection_label.setText(
                "CHƯA CHỌN VỤ ÁN: Nhấp vào một hồ sơ ở trên để xem chi tiết và mở bàn cờ."
            )
            self._open_case_btn.setEnabled(False)
            return
        s = tile.summary
        diff_part = f" · {s.difficulty_label}" if s.difficulty_label else ""
        self._selection_label.setText(
            f"ĐANG CHỌN: [{s.puzzle_id}] {s.title} ({s.grid_size}×{s.grid_size}{diff_part})"
        )
        self._open_case_btn.setEnabled(True)
