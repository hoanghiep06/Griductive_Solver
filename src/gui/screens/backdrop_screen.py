"""Shared base QWidget providing a cached full-bleed backdrop + scrim layer (Phase 2)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from src.gui.asset_registry import AssetId
from src.gui.components.asset_image_view import AssetImageView, ImageScaleMode
from src.gui.resources.pixmap_loader import PixmapLoader


class BackdropScreen(QWidget):
    """QWidget stacking a cached COVER backdrop image beneath a foreground layout."""

    def __init__(
        self,
        backdrop_asset: AssetId,
        *,
        scrim_rgba: tuple[int, int, int, int],
        pixmap_loader: Optional[PixmapLoader] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pixmap_loader = pixmap_loader

        stack = QGridLayout(self)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)

        self._backdrop = AssetImageView(
            backdrop_asset,
            scale_mode=ImageScaleMode.COVER,
            prefer_derived=False,
            scrim_rgba=scrim_rgba,
            pixmap_loader=pixmap_loader,
            parent=self,
        )
        stack.addWidget(self._backdrop, 0, 0)

        self._foreground = QWidget(self)
        self._foreground.setObjectName("GriductiveBackdropForeground")
        self._body_layout = QVBoxLayout(self._foreground)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        stack.addWidget(self._foreground, 0, 0)
        self._foreground.raise_()

    @property
    def backdrop(self) -> AssetImageView:
        return self._backdrop

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._body_layout
