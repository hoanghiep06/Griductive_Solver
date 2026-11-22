"""Cached QPixmap and QIcon loader built on top of Phase 1 AssetRegistry.

Design goals:
    - Never decode large PNG source files inside paintEvent.
    - Prefer non-destructive alpha-cleaned derived PNGs for A04/A07 by default.
    - Handle missing or unreadable assets gracefully (return null QPixmap + log warning).
    - Keep aspect-ratio scaling and Cover cropping deterministic and smooth.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

from src.gui.asset_registry import AssetId, AssetRegistry, DEFAULT_REGISTRY

logger = logging.getLogger(__name__)


class PixmapLoader:
    """In-memory cache of decoded QPixmap/QIcon objects backed by AssetRegistry."""

    def __init__(self, registry: AssetRegistry = DEFAULT_REGISTRY) -> None:
        self._registry = registry
        self._pixmap_cache: dict[tuple[AssetId, bool], QPixmap] = {}
        self._clue_icon_cache: dict[tuple[str, bool], QPixmap] = {}
        self._scaled_clue_cache: dict[tuple[str, int, int, int, bool], QPixmap] = {}
        self._icon_cache: dict[tuple[AssetId, bool], QIcon] = {}
        self._warnings: list[str] = []

    @property
    def registry(self) -> AssetRegistry:
        return self._registry

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    def clear_cache(self) -> None:
        self._pixmap_cache.clear()
        self._clue_icon_cache.clear()
        self._scaled_clue_cache.clear()
        self._icon_cache.clear()

    def load_clue_icon(
        self,
        clue_type: str,
        *,
        prefer_vietnamese: bool = True,
    ) -> QPixmap:
        """Load and cache the full-resolution (512x512 RGBA) Vietnamese clue icon."""
        key = (clue_type.strip().upper(), bool(prefer_vietnamese))
        cached = self._clue_icon_cache.get(key)
        if cached is not None:
            return cached

        res = self._registry.resolve_clue_icon(key[0], prefer_vietnamese=key[1])
        if res is None or not res.exists or res.path is None:
            empty = QPixmap()
            self._clue_icon_cache[key] = empty
            return empty

        pixmap = QPixmap(str(res.path))
        if pixmap.isNull():
            msg = f"Qt failed to decode clue icon for {key[0]}: {res.path}"
            self._warnings.append(msg)
            logger.warning(msg)

        self._clue_icon_cache[key] = pixmap
        return pixmap

    def load_clue_icon_scaled(
        self,
        clue_type: str,
        target_size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
        prefer_vietnamese: bool = True,
    ) -> QPixmap:
        """Load and cache a High-DPI crisp square clue icon preserving aspect ratio."""
        dpr = max(1.0, float(device_pixel_ratio))
        dpr_key = int(round(dpr * 100))
        cache_key = (
            clue_type.strip().upper(),
            target_size.width(),
            target_size.height(),
            dpr_key,
            bool(prefer_vietnamese),
        )
        cached = self._scaled_clue_cache.get(cache_key)
        if cached is not None:
            return cached

        raw = self.load_clue_icon(clue_type, prefer_vietnamese=prefer_vietnamese)
        if raw.isNull() or target_size.width() <= 0 or target_size.height() <= 0:
            empty = QPixmap()
            self._scaled_clue_cache[cache_key] = empty
            return empty

        phys_size = QSize(
            max(1, int(round(target_size.width() * dpr))),
            max(1, int(round(target_size.height() * dpr))),
        )
        scaled = self.scale_contain(raw, phys_size, allow_upscale=False)
        if dpr > 1.0 and not scaled.isNull():
            scaled.setDevicePixelRatio(dpr)
        self._scaled_clue_cache[cache_key] = scaled
        return scaled

    def load_pixmap(self, asset_id: AssetId, *, prefer_derived: bool = True) -> QPixmap:
        """Load and cache the full-resolution QPixmap for ``asset_id``."""
        key = (asset_id, prefer_derived)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            return cached

        res = self._registry.resolve(asset_id, prefer_derived=prefer_derived)
        if res.warning:
            self._warnings.append(res.warning)
            logger.warning(res.warning)

        if not res.exists or res.path is None:
            empty = QPixmap()
            self._pixmap_cache[key] = empty
            return empty

        pixmap = QPixmap(str(res.path))
        if pixmap.isNull():
            msg = f"Qt failed to decode image for {asset_id.value}: {res.path}"
            self._warnings.append(msg)
            logger.warning(msg)

        self._pixmap_cache[key] = pixmap
        return pixmap

    def load_icon(self, asset_id: AssetId, *, prefer_derived: bool = True) -> QIcon:
        """Load and cache a multi-size QIcon for window/button identity."""
        key = (asset_id, prefer_derived)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        base = self.load_pixmap(asset_id, prefer_derived=prefer_derived)
        icon = QIcon()
        if not base.isNull():
            for dim in (16, 24, 32, 48, 64, 128, 256):
                scaled = base.scaled(
                    dim,
                    dim,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                icon.addPixmap(scaled)
        self._icon_cache[key] = icon
        return icon

    @staticmethod
    def scale_contain(pixmap: QPixmap, target_size: QSize, *, allow_upscale: bool = False) -> QPixmap:
        """Scale ``pixmap`` to fit inside ``target_size`` while preserving aspect ratio."""
        if pixmap.isNull() or target_size.width() <= 0 or target_size.height() <= 0:
            return QPixmap()
        if not allow_upscale and pixmap.width() <= target_size.width() and pixmap.height() <= target_size.height():
            return pixmap
        return pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    @staticmethod
    def scale_cover(pixmap: QPixmap, target_size: QSize) -> QPixmap:
        """Scale ``pixmap`` to fill ``target_size`` preserving aspect ratio, center-cropped."""
        if pixmap.isNull() or target_size.width() <= 0 or target_size.height() <= 0:
            return QPixmap()
        expanded = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (expanded.width() - target_size.width()) // 2)
        y = max(0, (expanded.height() - target_size.height()) // 2)
        return expanded.copy(QRect(x, y, target_size.width(), target_size.height()))


_DEFAULT_LOADER: Optional[PixmapLoader] = None


def default_pixmap_loader() -> PixmapLoader:
    """Return a lazily-created shared PixmapLoader (must be used after QApplication exists)."""
    global _DEFAULT_LOADER
    if _DEFAULT_LOADER is None:
        _DEFAULT_LOADER = PixmapLoader(DEFAULT_REGISTRY)
    return _DEFAULT_LOADER
