"""AboutScreen — Warm-Paper Editorial Case Dossier (Design System V2).

Breaks completely from dark dashboard boxes: presents GRIDUCTIVE SOLVER on an
archival Warm Paper (#F3E9D6) canvas with a single centered Pale Ivory (#FAF7F0)
case dossier sheet, a Deep Ink brand plate (so dark-mode A04 logo & cartoon
emblem stay razor-sharp), Display Serif headings, hairline dividers, clean
typographic team roster, and centralized GitHub / YouTube links.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
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
from src.gui.project_info import (
    COURSE_LABEL,
    GITHUB_REPO_URL,
    PROJECT_INTRO_PARAGRAPHS,
    PROJECT_SUBTITLE,
    PROJECT_TITLE,
    TEAM_MEMBERS,
    TECH_SPECS,
    YOUTUBE_DEMO_URL,
    TeamMemberInfo,
    is_valid_external_url,
)
from src.gui.resources.pixmap_loader import PixmapLoader
from src.gui.styles.tokens import SPACING


def _default_open_url(url: str) -> bool:
    return bool(QDesktopServices.openUrl(QUrl(url)))


class _TeamMemberRow(QFrame):
    """Editorial hairline-separated roster row (replaces heavy dark bordered boxes)."""

    def __init__(
        self,
        index: int,
        member: TeamMemberInfo,
        *,
        is_last: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("widgetKind", "teamMemberRow")
        self.setProperty("isLast", "true" if is_last else "false")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, SPACING.space_2, 0, SPACING.space_2)
        row.setSpacing(SPACING.space_3)

        num_lbl = QLabel(f"{index:02d}", self)
        num_lbl.setTextFormat(Qt.TextFormat.PlainText)
        num_lbl.setProperty("role", "paperKicker")
        num_lbl.setFixedWidth(22)
        row.addWidget(num_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(1)

        name_lbl = QLabel(member.full_name, self)
        name_lbl.setTextFormat(Qt.TextFormat.PlainText)
        name_lbl.setProperty("role", "paperSubheading")
        info_col.addWidget(name_lbl)

        role_lbl = QLabel(member.stage2_role, self)
        role_lbl.setTextFormat(Qt.TextFormat.PlainText)
        role_lbl.setProperty("role", "paperCaption")
        info_col.addWidget(role_lbl)

        row.addLayout(info_col, 1)

        mssv_lbl = StatusLabel(member.student_id, tone="paperAccent", parent=self)
        mssv_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row.addWidget(mssv_lbl, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class AboutScreen(QWidget):
    """Editorial Case-Dossier About page on Warm Paper canvas."""

    back_requested = Signal()
    external_link_opened = Signal(str)

    def __init__(
        self,
        *,
        pixmap_loader: Optional[PixmapLoader] = None,
        github_url: str = GITHUB_REPO_URL,
        youtube_url: Optional[str] = YOUTUBE_DEMO_URL,
        url_opener: Optional[Callable[[str], bool]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AboutScreen")
        self.setProperty("surface", "paperCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._github_url = github_url
        self._youtube_url = youtube_url
        self._url_opener = url_opener or _default_open_url

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ------------------------------------------------------------------
        # 1. DEEP INK EDITORIAL MASTHEAD
        # ------------------------------------------------------------------
        self._back_button = StyledButton("← Quay lại", variant="ghost", min_height=44, parent=self)
        self._back_button.setToolTip("Trở về Màn hình chính (Esc)")
        self._back_button.clicked.connect(self.back_requested.emit)

        header = PageHeader(
            "ABOUT GRIDUCTIVE",
            subtitle="Detective Case Files",
            left_widget=self._back_button,
            right_widget=StatusLabel(COURSE_LABEL, tone="accent", parent=self),
            parent=self,
        )
        root.addWidget(header)

        # ------------------------------------------------------------------
        # 2. SCROLLABLE WARM PAPER ARCHIVE WITH CENTERED IVORY DOSSIER SHEET
        # ------------------------------------------------------------------
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setProperty("widgetKind", "cleanScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        canvas = QWidget(self._scroll_area)
        canvas.setProperty("surface", "paperCanvas")
        canvas_layout = QHBoxLayout(canvas)
        canvas_layout.setContentsMargins(
            SPACING.space_5,
            SPACING.space_4,
            SPACING.space_5,
            SPACING.space_5,
        )

        canvas_layout.addStretch(1)

        dossier = StyledPanel(
            variant="dossier",
            padding=SPACING.space_5,
            accent_bar="brick",
            parent=canvas,
        )
        dossier.setMinimumWidth(780)
        dossier.setMaximumWidth(1200)
        dossier.content_layout.setSpacing(SPACING.space_4)

        # Cream Editorial Dossier Masthead (compact emblem badges only — zero stacked navy blocks!)
        brand_header = QFrame(dossier)
        brand_header.setProperty("surface", "transparent")
        brand_row = QHBoxLayout(brand_header)
        brand_row.setContentsMargins(0, 0, 0, SPACING.space_1)
        brand_row.setSpacing(SPACING.space_4)

        emblem_frame = QFrame(brand_header)
        emblem_frame.setProperty("widgetKind", "emblemBadge")
        emblem_lay = QHBoxLayout(emblem_frame)
        emblem_lay.setContentsMargins(6, 6, 6, 6)
        self._emblem_view = AssetImageView(
            AssetId.A04_APP_EMBLEM,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=emblem_frame,
        )
        self._emblem_view.setFixedSize(82, 82)
        emblem_lay.addWidget(self._emblem_view)
        brand_row.addWidget(emblem_frame, 0, Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(4)

        kicker_top = QLabel("HỒ SƠ ĐỒ ÁN TRINH THÁM · CASE FILE DOSSIER", brand_header)
        kicker_top.setProperty("role", "paperKicker")
        title_col.addWidget(kicker_top)

        self._project_title_label = QLabel(PROJECT_TITLE, brand_header)
        self._project_title_label.setTextFormat(Qt.TextFormat.PlainText)
        self._project_title_label.setProperty("role", "paperTitle")
        title_col.addWidget(self._project_title_label)

        self._project_subtitle_label = QLabel(PROJECT_SUBTITLE, brand_header)
        self._project_subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        self._project_subtitle_label.setProperty("role", "paperSecondary")
        title_col.addWidget(self._project_subtitle_label)

        brand_row.addLayout(title_col, 1)

        logo_frame = QFrame(brand_header)
        logo_frame.setProperty("widgetKind", "emblemBadge")
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(SPACING.space_3, 6, SPACING.space_3, 6)
        self._logo_view = AssetImageView(
            AssetId.A04_LOGO_WIDE,
            scale_mode=ImageScaleMode.CONTAIN,
            prefer_derived=True,
            pixmap_loader=pixmap_loader,
            parent=logo_frame,
        )
        self._logo_view.setMinimumSize(210, 82)
        self._logo_view.setMaximumSize(260, 92)
        logo_lay.addWidget(self._logo_view)
        brand_row.addWidget(logo_frame, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        dossier.content_layout.addWidget(brand_header)

        header_rule = QFrame(dossier)
        header_rule.setProperty("widgetKind", "paperRule")
        dossier.content_layout.addWidget(header_rule)

        # Asymmetric Editorial Spread (54% Narrative & Specs | 1px Rule | 46% Team & Links)
        spread = QHBoxLayout()
        spread.setContentsMargins(0, SPACING.space_1, 0, 0)
        spread.setSpacing(SPACING.space_5)

        # ==================== LEFT EDITORIAL COLUMN ====================
        left_col = QVBoxLayout()
        left_col.setSpacing(SPACING.space_3)

        kicker_intro = QLabel("HỒ SƠ ĐỒ ÁN · PROJECT OVERVIEW", dossier)
        kicker_intro.setProperty("role", "paperKicker")
        left_col.addWidget(kicker_intro)

        # Lead paragraph in refined archival pull-bar
        lead_frame = QFrame(dossier)
        lead_frame.setProperty("widgetKind", "editorialPullQuote")
        lead_lay = QVBoxLayout(lead_frame)
        lead_lay.setContentsMargins(SPACING.space_3, SPACING.space_2, SPACING.space_3, SPACING.space_2)
        lead_lbl = QLabel(PROJECT_INTRO_PARAGRAPHS[0], lead_frame)
        lead_lbl.setTextFormat(Qt.TextFormat.PlainText)
        lead_lbl.setProperty("role", "paperSubheading")
        lead_lbl.setWordWrap(True)
        lead_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lead_lay.addWidget(lead_lbl)
        left_col.addWidget(lead_frame)

        self._intro_labels: list[QLabel] = [lead_lbl]
        for para in PROJECT_INTRO_PARAGRAPHS[1:]:
            lbl = QLabel(para, dossier)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            lbl.setProperty("role", "paperBody")
            lbl.setWordWrap(True)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            left_col.addWidget(lbl)
            self._intro_labels.append(lbl)

        left_col.addStretch(1)
        left_col.addStretch(1)

        # Vertical Hairline Parchment Divider
        v_rule = QFrame(dossier)
        v_rule.setProperty("widgetKind", "paperVRule")

        # ==================== RIGHT EDITORIAL COLUMN ====================
        right_col = QVBoxLayout()
        right_col.setSpacing(SPACING.space_2)

        team_kicker = QLabel("NHÓM THỰC HIỆN · CSC14003", dossier)
        team_kicker.setProperty("role", "paperKicker")
        right_col.addWidget(team_kicker)

        team_heading = QLabel("Development Team — Nhóm thực hiện", dossier)
        team_heading.setProperty("role", "paperHeading")
        right_col.addWidget(team_heading)

        self._member_cards: list[_TeamMemberRow] = []
        total_members = len(TEAM_MEMBERS)
        for idx, member in enumerate(TEAM_MEMBERS, start=1):
            row_card = _TeamMemberRow(
                idx,
                member,
                is_last=(idx == total_members),
                parent=dossier,
            )
            right_col.addWidget(row_card)
            self._member_cards.append(row_card)

        right_col.addSpacing(SPACING.space_2)
        rule_links = QFrame(dossier)
        rule_links.setProperty("widgetKind", "paperRule")
        right_col.addWidget(rule_links)

        links_kicker = QLabel("LIÊN KẾT DỰ ÁN · PROJECT LINKS", dossier)
        links_kicker.setProperty("role", "paperKicker")
        right_col.addWidget(links_kicker)

        links_row = QHBoxLayout()
        links_row.setSpacing(SPACING.space_2)

        self._github_button = StyledButton(
            "GitHub Repository",
            variant="inkPrimary",
            min_height=46,
            parent=dossier,
        )
        self._github_button.setProperty("compactLinks", "true")
        self._github_button.clicked.connect(self._on_github_clicked)
        links_row.addWidget(self._github_button, 4)

        self._youtube_button = StyledButton(
            "YouTube Demo",
            variant="paperSecondary",
            min_height=46,
            parent=dossier,
        )
        self._youtube_button.setProperty("compactLinks", "true")
        self._youtube_button.clicked.connect(self._on_youtube_clicked)
        links_row.addWidget(self._youtube_button, 6)
        right_col.addLayout(links_row)

        self._github_caption = QLabel(f"GitHub: {self._github_url}", dossier)
        self._github_caption.setTextFormat(Qt.TextFormat.PlainText)
        self._github_caption.setProperty("role", "paperCaption")
        self._github_caption.setWordWrap(True)
        right_col.addWidget(self._github_caption)

        right_col.addStretch(1)

        spread.addLayout(left_col, 54)
        spread.addWidget(v_rule)
        spread.addLayout(right_col, 46)
        dossier.content_layout.addLayout(spread, 1)

        canvas_layout.addWidget(dossier, 1)
        canvas_layout.addStretch(1)

        self._scroll_area.setWidget(canvas)
        root.addWidget(self._scroll_area, 1)

        self._sync_link_buttons()

    # ------------------------------------------------------------------
    # Public API & Properties (100% preserved)
    # ------------------------------------------------------------------

    @property
    def back_button(self) -> StyledButton:
        return self._back_button

    @property
    def github_button(self) -> StyledButton:
        return self._github_button

    @property
    def youtube_button(self) -> StyledButton:
        return self._youtube_button

    @property
    def github_url(self) -> str:
        return self._github_url

    @property
    def youtube_url(self) -> Optional[str]:
        return self._youtube_url

    @property
    def emblem_view(self) -> AssetImageView:
        return self._emblem_view

    @property
    def logo_view(self) -> AssetImageView:
        return self._logo_view

    @property
    def scroll_area(self) -> QScrollArea:
        return self._scroll_area

    @property
    def member_cards(self) -> tuple[_TeamMemberRow, ...]:
        return tuple(self._member_cards)

    def set_youtube_url(self, url: Optional[str]) -> None:
        self._youtube_url = url
        self._sync_link_buttons()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.back_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Internal Handlers
    # ------------------------------------------------------------------

    def _sync_link_buttons(self) -> None:
        gh_valid = is_valid_external_url(self._github_url)
        self._github_button.setEnabled(gh_valid)
        self._github_button.setToolTip(
            f"Mở kho mã nguồn trên trình duyệt mặc định:\n{self._github_url}"
            if gh_valid
            else "Liên kết GitHub chưa hợp lệ"
        )

        yt_valid = is_valid_external_url(self._youtube_url)
        if yt_valid:
            self._youtube_button.setText("YouTube Demo")
            self._youtube_button.setEnabled(True)
            self._youtube_button.setToolTip(
                f"Mở video minh họa trên trình duyệt mặc định:\n{self._youtube_url}"
            )
        else:
            self._youtube_button.setText("YouTube Demo — Chưa cập nhật")
            self._youtube_button.setEnabled(False)
            self._youtube_button.setToolTip(
                "Video demo YouTube chưa được cập nhật (chỉnh tại src/gui/project_info.py)."
            )

    def _on_github_clicked(self) -> None:
        if is_valid_external_url(self._github_url):
            self._url_opener(self._github_url)
            self.external_link_opened.emit(self._github_url)

    def _on_youtube_clicked(self) -> None:
        if is_valid_external_url(self._youtube_url):
            assert self._youtube_url is not None
            self._url_opener(self._youtube_url)
            self.external_link_opened.emit(self._youtube_url)
