"""PySide6 launcher: real gameplay by default, isolated preview with --demo.

Widget construction stays domain-free. Only main() imports the application
controller, keeping standalone UI previews and widget tests independent.
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
        app.setApplicationName("GRIDUCTIVE SOLVER — Hồ Sơ Phá Án")
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
    """Launch real gameplay, or the isolated presentation preview with --demo."""
    try:
        app, theme_manager = create_application(argv)
    except RuntimeError as exc:
        print(f"[GRIDUCTIVE GUI] {exc}", file=sys.stderr)
        return 1

    args = list(argv) if argv is not None else sys.argv[1:]
    demo = "--demo" in args
    window = build_main_window(theme_manager=theme_manager, demo_navigation=demo)
    if not demo:
        from src.controller.play_controller import PlayController
        window.play_controller = PlayController(window)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
