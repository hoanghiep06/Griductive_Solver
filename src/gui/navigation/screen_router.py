"""Application-level ScreenRouter built on QStackedWidget.

Distinction:
    ``ScreenRouter`` ONLY handles Presentation-layer screen switching between
    registered QWidget pages. It owns NO game state, NO GameEngine, and NO
    Logic Agent state. In Phase 2 standalone demo mode, MainWindow wires simple
    preview navigation; in later phases, Hiệp's GameController drives screen
    transitions via MainWindow's ViewPort methods.
"""

from __future__ import annotations

from enum import Enum
import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QWidget

logger = logging.getLogger(__name__)


class ScreenId(str, Enum):
    """Canonical UI screen identities."""

    MAIN_MENU = "MAIN_MENU"
    ABOUT = "ABOUT"
    LEVEL_SELECTION = "LEVEL_SELECTION"
    GAMEPLAY = "GAMEPLAY"
    RESULTS = "RESULTS"


class ScreenRouter(QStackedWidget):
    """Deterministic single-instance screen stack with graceful invalid-route handling."""

    screen_changed = Signal(object)  # Emits ScreenId

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("GriductiveScreenRouter")
        self._screens: dict[ScreenId, QWidget] = {}
        self._current_screen: Optional[ScreenId] = None

    @property
    def current_screen(self) -> Optional[ScreenId]:
        return self._current_screen

    @property
    def registered_screens(self) -> tuple[ScreenId, ...]:
        return tuple(self._screens.keys())

    def register_screen(self, screen_id: ScreenId, widget: QWidget) -> None:
        """Register one screen instance per ScreenId; rejects duplicate registrations."""
        if not isinstance(screen_id, ScreenId):
            raise TypeError(f"screen_id must be ScreenId, got {type(screen_id).__name__}")
        if not isinstance(widget, QWidget):
            raise TypeError(f"widget must be QWidget, got {type(widget).__name__}")
        if screen_id in self._screens:
            raise ValueError(f"Screen {screen_id.value!r} is already registered")

        self._screens[screen_id] = widget
        self.addWidget(widget)
        if self._current_screen is None:
            self._current_screen = screen_id
            self.setCurrentWidget(widget)

    def get_screen(self, screen_id: ScreenId) -> Optional[QWidget]:
        return self._screens.get(screen_id)

    def has_screen(self, screen_id: ScreenId) -> bool:
        return screen_id in self._screens

    def navigate_to(self, screen_id: ScreenId | str) -> bool:
        """Switch to a registered screen. Returns False gracefully on invalid/unregistered IDs."""
        resolved = self._coerce_screen_id(screen_id)
        if resolved is None or resolved not in self._screens:
            logger.warning("Ignoring navigation request to unknown/unregistered screen: %r", screen_id)
            return False

        target = self._screens[resolved]
        changed = resolved is not self._current_screen
        self.setCurrentWidget(target)
        self._current_screen = resolved
        if changed:
            self.screen_changed.emit(resolved)
        return True

    @staticmethod
    def _coerce_screen_id(value: ScreenId | str) -> Optional[ScreenId]:
        if isinstance(value, ScreenId):
            return value
        if isinstance(value, str):
            try:
                return ScreenId(value.strip().upper())
            except ValueError:
                return None
        return None
