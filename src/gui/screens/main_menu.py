"""MainMenuScreen — Centered Cream Detective Editorial Hero Dossier.

Presents GRIDUCTIVE on a Warm Cream (#F5EFE4) atmospheric canvas over the A03
detective artwork, featuring a visually centered Soft Ivory (#FBF7F0) Case-File
Hero Dossier Card with the cartoon detective A04 medallion, wide A04 logo,
Display Serif headline, concise subtitle, and a clear 3-tier CTA hierarchy
(Play / About / Exit).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.screens.backdrop_screen import BackdropScreen
from src.gui.styles.tokens import COLORS, SPACING


class MainMenuScreen(BackdropScreen):
    """Centered Cream Editorial Main Menu screen preserving Play / About / Exit contracts."""

    play_requested = Signal()
    about_requested = Signal()
    how_to_play_requested = Signal()  # Preserved for backward API compatibility
    exit_requested = Signal()

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        demo_mode: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            AssetId.A03_MAIN_MENU_BACKGROUND,
            scrim_rgba=(0, 0, 0, 0),
            pixmap_loader=pixmap_loader,
            parent=parent,
        )
        self.setObjectName("MainMenuScreen")
        self._demo_mode = bool(demo_mode)

        outer = QVBoxLayout()
        outer.setContentsMargins(SPACING.space_6, SPACING.space_5, SPACING.space_6, SPACING.space_4)
        outer.setSpacing(SPACING.space_3)
        self.body_layout.addLayout(outer, 1)

        outer.addStretch(1)

        # Centered Hero Composition Row
        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch(1)

        # Centered Soft Ivory Case-File Hero Dossier Card
        hero_card = StyledPanel(
            variant="dossier",
            padding=SPACING.space_6,
            accent_bar="brass",
            parent=self,
        )
        hero_card.setMinimumWidth(580)
        hero_card.setMaximumWidth(680)
        hero_card.content_layout.setSpacing(SPACING.space_3)

        # 1. Hidden metadata badges (preserved for API compatibility; hidden to declutter hero card)
        self._demo_badge = StatusLabel("DETECTIVE CASE FILES", tone="paperNeutral", parent=hero_card)
        self._demo_badge.setVisible(False)

        # 2. Centered Deep Ink Brand Medallion Strip (keeps dark-backed A04 logo & emblem crisp)
        brand_wrap = QHBoxLayout()
        brand_wrap.setContentsMargins(0, SPACING.space_1, 0, SPACING.space_1)
        brand_wrap.addStretch(1)

        brand_badge = QFrame(hero_card)
        brand_badge.setProperty("widgetKind", "emblemBadge")
        brand_row = QHBoxLayout(brand_badge)
        brand_row.setContentsMargins(SPACING.space_4, SPACING.space_3, SPACING.space_4, SPACING.space_3)
        brand_row.setSpacing(SPACING.space_4)

        self._emblem_view = AssetImageView(
            AssetId.A04_APP_EMBLEM,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=brand_badge,
        )
        self._emblem_view.setFixedSize(92, 92)
        brand_row.addWidget(self._emblem_view, 0, Qt.AlignmentFlag.AlignVCenter)

        self._logo_view = AssetImageView(
            AssetId.A04_LOGO_WIDE,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=brand_badge,
        )
        self._logo_view.setMinimumSize(290, 102)
        self._logo_view.setMaximumSize(360, 122)
        brand_row.addWidget(self._logo_view, 0, Qt.AlignmentFlag.AlignVCenter)

        brand_wrap.addWidget(brand_badge)
        brand_wrap.addStretch(1)
        hero_card.content_layout.addLayout(brand_wrap)

        # 3. Centered Delicate Brass Rule
        rule_wrap = QHBoxLayout()
        rule_wrap.addStretch(1)
        brass_rule = QFrame(hero_card)
        brass_rule.setProperty("widgetKind", "brassRule")
        brass_rule.setFixedWidth(220)
        rule_wrap.addWidget(brass_rule)
        rule_wrap.addStretch(1)
        hero_card.content_layout.addLayout(rule_wrap)

        # 4. Centered Editorial Display Serif Headline & Concise Tagline
        headline = QLabel("Hồ Sơ Phá Án · Suy Luận Logic", hero_card)
        headline.setProperty("role", "paperTitle")
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setWordWrap(True)
        headline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hero_card.content_layout.addWidget(headline)

        tagline = QLabel(
            "Khám phá manh mối công khai và suy luận danh tính từng nghi phạm bằng tư duy logic.",
            hero_card,
        )
        tagline.setProperty("role", "paperSecondary")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setWordWrap(True)
        tagline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hero_card.content_layout.addWidget(tagline)

        hero_card.content_layout.addSpacing(SPACING.space_2)

        # 5. Centered True 3-Tier Button Hierarchy (preserving exact width=300 & Play/About/Exit order)
        btn_wrap = QHBoxLayout()
        btn_wrap.addStretch(1)

        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 0, 0, 0)
        btn_col.setSpacing(SPACING.space_2)

        self._play_button = StyledButton(
            "Chơi ngay — Mở Kho Hồ Sơ",
            variant="primary",
            min_height=50,
            parent=hero_card,
        )
        self._play_button.setMinimumWidth(300)
        self._play_button.setMaximumWidth(340)
        self._play_button.setToolTip("Mở Kho Hồ Sơ Vụ Án (Level Selection)")
        self._play_button.clicked.connect(self.play_requested.emit)
        btn_col.addWidget(self._play_button)

        self._about_button = StyledButton(
            "About",
            variant="secondary",
            min_height=46,
            parent=hero_card,
        )
        self._about_button.setMinimumWidth(300)
        self._about_button.setMaximumWidth(340)
        self._about_button.setToolTip("Giới thiệu đồ án GRIDUCTIVE SOLVER và thông tin nhóm thực hiện")
        self._about_button.clicked.connect(self.about_requested.emit)
        btn_col.addWidget(self._about_button)

        self._exit_button = StyledButton(
            "Thoát ứng dụng",
            variant="tertiary",
            min_height=44,
            parent=hero_card,
        )
        self._exit_button.setMinimumWidth(300)
        self._exit_button.setMaximumWidth(340)
        self._exit_button.setToolTip("Đóng ứng dụng GRIDUCTIVE")
        self._exit_button.clicked.connect(self.exit_requested.emit)
        btn_col.addWidget(self._exit_button)

        btn_wrap.addLayout(btn_col)
        btn_wrap.addStretch(1)
        hero_card.content_layout.addLayout(btn_wrap)

        center_row.addWidget(hero_card)
        center_row.addStretch(1)
        outer.addLayout(center_row)

        outer.addStretch(1)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

    @property
    def emblem_view(self) -> AssetImageView:
        return self._emblem_view

    @property
    def logo_view(self) -> AssetImageView:
        return self._logo_view

    @property
    def play_button(self) -> StyledButton:
        return self._play_button

    @property
    def about_button(self) -> StyledButton:
        return self._about_button

    @property
    def exit_button(self) -> StyledButton:
        return self._exit_button

    def set_enabled(self, enabled: bool) -> None:
        self._play_button.setEnabled(enabled)
        self._about_button.setEnabled(enabled)
        self._exit_button.setEnabled(enabled)
