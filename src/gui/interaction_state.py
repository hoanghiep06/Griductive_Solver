"""Transient presentation state; never participates in logical proofs."""

from dataclasses import dataclass, field

from src.gui.view_models import ActionResult, HintView


@dataclass
class InteractionState:
    selected_clue_id: str | None = None
    highlighted_targets: tuple[str, ...] = ()
    active_hint: HintView | None = None
    error_feedback: ActionResult | None = None
    is_auto_solving: bool = False
    solved_clues: set[str] = field(default_factory=set)
    hint_count: int = 0
    mistake_count: int = 0
