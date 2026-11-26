"""StatusLabel compact accessible pill primitive (Design System V2)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

VALID_STATUS_TONES = frozenset(
    {
        "neutral",
        "accent",
        "info",
        "success",
        "warning",
        "danger",
        "paperNeutral",
        "paperAccent",
        "paperInfo",
        "paperSuccess",
        "paperDanger",
    }
)
_TONE_CANONICAL: dict[str, str] = {t.lower(): t for t in VALID_STATUS_TONES}


class StatusLabel(QLabel):
    """Compact pill label for screen/application/dossier status display."""

    def __init__(
        self,
        text: str = "",
        *,
        tone: str = "neutral",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("widgetKind", "statusPill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tone = "neutral"
        self.set_tone(tone)

    @property
    def tone(self) -> str:
        return self._tone

    def set_tone(self, tone: str) -> None:
        canonical = _TONE_CANONICAL.get(tone.strip().lower())
        if canonical is None:
            raise ValueError(
                f"Unsupported StatusLabel tone {tone!r}; expected one of {sorted(VALID_STATUS_TONES)}"
            )
        if self._tone == canonical and self.property("tone") == canonical:
            return
        self._tone = canonical
        self.setProperty("tone", canonical)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def set_status(self, text: str, *, tone: Optional[str] = None) -> None:
        """Update pill text (plain text) and optionally switch semantic tone."""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(text)
        if tone is not None:
            self.set_tone(tone)
