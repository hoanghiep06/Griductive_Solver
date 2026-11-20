"""GRIDUCTIVE — Detective Case Files GUI package (Phases 1–4).

Contains design tokens, asset registry, PySide6 application shell,
ScreenRouter, GameBoard/CharacterCard, Phase 4 Dashboard panels
(CluePanel, DeductionPanel, ActionBar, ProgressPanel, NotificationBanner/Dialog,
CaseTile), and completed supporting screens.

Pure-Python modules (``asset_registry``, ``styles.tokens``, ``view_models``)
can be imported without Qt. Widgets require PySide6.
"""

from src.gui.asset_registry import (
    AssetId,
    AssetRegistry,
    AssetResolution,
    AssetValidationReport,
    DEFAULT_REGISTRY,
    get_assets_root,
    resolve_asset,
)
from src.gui.view_models import (
    ActionCode,
    ActionResult,
    AnimationToken,
    CardVisibility,
    DeductionStepView,
    GameState,
    HintView,
    LevelSummary,
    NotificationSeverity,
    PublicBoardSnapshot,
    PublicCharacterView,
    PublicClueView,
    ResultsView,
)

__all__ = [
    "ActionCode",
    "ActionResult",
    "AnimationToken",
    "AssetId",
    "AssetRegistry",
    "AssetResolution",
    "AssetValidationReport",
    "CardVisibility",
    "DEFAULT_REGISTRY",
    "DeductionStepView",
    "GameState",
    "HintView",
    "LevelSummary",
    "NotificationSeverity",
    "PublicBoardSnapshot",
    "PublicCharacterView",
    "PublicClueView",
    "ResultsView",
    "get_assets_root",
    "resolve_asset",
]
