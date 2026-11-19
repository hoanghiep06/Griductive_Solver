"""Reusable PySide6 UI primitives, CharacterCard & Phase 4 Dashboard Components."""

from src.gui.components.action_bar import ActionBar
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.components.case_tile import CaseTile
from src.gui.components.character_card import (
    CARD_DIMENSIONS_BY_MODE,
    CardDisplayMode,
    CharacterCard,
)
from src.gui.components.clue_panel import CluePanel
from src.gui.components.deduction_panel import DeductionPanel
from src.gui.components.notification_dialog import (
    HowToPlayDialog,
    NotificationBanner,
    NotificationDialog,
)
from src.gui.components.page_header import PageHeader
from src.gui.components.progress_panel import ProgressPanel
from src.gui.components.section_placeholder import SectionPlaceholder
from src.gui.components.status_label import StatusLabel
from src.gui.components.styled_button import StyledButton
from src.gui.components.styled_panel import StyledPanel

__all__ = [
    "ActionBar",
    "AssetImageView",
    "CARD_DIMENSIONS_BY_MODE",
    "CardDisplayMode",
    "CaseTile",
    "CharacterCard",
    "CluePanel",
    "DeductionPanel",
    "HowToPlayDialog",
    "ImageScaleMode",
    "NotificationBanner",
    "NotificationDialog",
    "PageHeader",
    "ProgressPanel",
    "SectionPlaceholder",
    "StatusLabel",
    "StyledButton",
    "StyledPanel",
]
