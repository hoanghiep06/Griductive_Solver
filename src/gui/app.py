"""Standalone PySide6 GUI Foundation bootstrap & launcher (Phase 2).

Run from any working directory with the project virtual environment:

    .venv/bin/python -m src.gui.app

Note:
    ``main.py`` at the repository root is reserved for Hiệp's Stage 2
    Composition Root (wiring GameEngine, LogicAgent, GameController and
    MainWindow together). This module provides a clean standalone presentation
    launcher for Phase 2 UI Foundation demo & testing without requiring
    DPLL, Encoder, LogicAgent or GameController.
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from src.gui.asset_registry import DEFAULT_REGISTRY


def _require_pyside6() -> None:
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required to launch the Griductive GUI. "
            "Install it in the project virtual environment with:\n"
            "    pip --python .venv/bin/python install PySide6"
        ) from exc


def create_application(argv: Optional[Sequence[str]] = None):
    """Create or reuse the QApplication instance and configure global theming."""
    _require_pyside6()
    from PySide6.QtWidgets import QApplication

    from src.gui.styles.theme_manager import ThemeManager

    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
        app.setApplicationName("GRIDUCTIVE — Detective Case Files")
        app.setOrganizationName("HCMUS-CSC14003")

    theme_manager = ThemeManager()
    theme_manager.apply_to_application(app)
    return app, theme_manager


def build_main_window(
    *,
    theme_manager=None,
    demo_navigation: bool = True,
):
    """Construct the configured MainWindow with Phase 1 AssetRegistry & ThemeManager."""
    _require_pyside6()
    from src.gui.app_window import MainWindow
    from src.gui.resources.pixmap_loader import PixmapLoader
    from src.gui.styles.theme_manager import ThemeManager

    tm = theme_manager or ThemeManager()
    loader = PixmapLoader(DEFAULT_REGISTRY)
    return MainWindow(
        theme_manager=tm,
        pixmap_loader=loader,
        demo_navigation=demo_navigation,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Launch the Phase 2 UI Foundation standalone demo."""
    try:
        app, theme_manager = create_application(argv)
    except RuntimeError as exc:
        print(f"[GRIDUCTIVE GUI] {exc}", file=sys.stderr)
        return 1

    window = build_main_window(theme_manager=theme_manager, demo_navigation=True)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
