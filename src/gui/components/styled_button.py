"""StyledButton accessible desktop button primitive (Design System V2).

Supports clear multi-tier visual hierarchy across both Nocturne (dark) and
Warm Paper (editorial) surfaces:
    - Dark surfaces:  primary (Brass/Gold CTA), secondary (Editorial Ink-Outline),
                      ghost (Quiet minimal), tertiary (Subtle text/hairline),
                      danger (Crimson verdict), success (Innocent Teal verdict)
    - Paper surfaces: inkPrimary (Deep Ink CTA), paperSecondary (Ivory Ink-Outline),
                      paperGhost (Quiet archival link-button)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget

from src.gui.styles.tokens import GEOMETRY

VALID_BUTTON_VARIANTS = frozenset(
    {
        "primary",
        "secondary",
        "danger",
        "success",
        "ghost",
        "tertiary",
        "inkPrimary",
        "paperSecondary",
        "paperGhost",
    }
)

_VARIANT_CANONICAL: dict[str, str] = {v.lower(): v for v in VALID_BUTTON_VARIANTS}


class StyledButton(QPushButton):
    """Consistent, accessible themed QPushButton (>=44px tap target, pointer cursor)."""

    def __init__(
        self,
        text: str = "",
        *,
        variant: str = "secondary",
        min_height: int = GEOMETRY.button_min_height,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("widgetKind", "styledButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(min_height)
        self._variant = "secondary"
        self.set_variant(variant)

    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, variant: str) -> None:
        key = variant.strip().lower()
        canonical = _VARIANT_CANONICAL.get(key)
        if canonical is None:
            raise ValueError(
                f"Unsupported StyledButton variant {variant!r}; "
                f"expected one of {sorted(VALID_BUTTON_VARIANTS)}"
            )
        self._variant = canonical
        self.setProperty("variant", canonical)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()
