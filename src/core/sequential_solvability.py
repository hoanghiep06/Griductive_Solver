"""Exhaustive sequential-solvability analysis for small puzzles.

This checker is intended for puzzle authoring and regression tests, not as the
runtime deduction agent. It deliberately uses the direct semantic evaluator
and enumerates complete assignments, so it is independent from the CNF Encoder
and DPLL implementation.
"""

from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Mapping, TYPE_CHECKING

from src.core.puzzle import Puzzle

if TYPE_CHECKING:  # Avoid a runtime import cycle with PuzzleValidator.
    from src.core.puzzle_validator import PuzzleValidator


class SequentialAnalysisStatus(str, Enum):
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    INCONSISTENT = "INCONSISTENT"
    TOO_LARGE = "TOO_LARGE"


@dataclass(frozen=True, slots=True)
class SequentialStep:
    step: int
    character_id: str
    status: str
    revealed_clue_id: str
    models_before: int
    models_after: int


@dataclass(frozen=True, slots=True)
class SequentialSolvabilityReport:
    status: SequentialAnalysisStatus
    steps: tuple[SequentialStep, ...]
    unresolved_character_ids: tuple[str, ...]
    initial_model_count: int | None
    remaining_model_count: int | None
    checked_assignments: int
    max_characters: int

    @property
    def is_solvable(self) -> bool | None:
        if self.status is SequentialAnalysisStatus.TOO_LARGE:
            return None
        return self.status is SequentialAnalysisStatus.SOLVED


class SequentialSolvabilityChecker:
    """Check whether a puzzle can be solved without guessing, card by card.

    Only initially revealed statuses/clues and later logically forced
    statuses/revealed clues are used at each simulated step. Hidden statuses
    are consulted only to seed cards that are initially face-up, exactly as in
    the actual game.
    """

    def __init__(self, validator: "PuzzleValidator") -> None:
        self._validator = validator

    def analyze(
        self,
        puzzle: Puzzle,
        *,
        max_characters: int = 9,
    ) -> SequentialSolvabilityReport:
        if type(max_characters) is not int or max_characters < 1:
            raise ValueError("max_characters must be a positive integer")

        character_count = len(puzzle.characters)
        checked_assignments = 1 << character_count
        if character_count > max_characters:
            return SequentialSolvabilityReport(
                status=SequentialAnalysisStatus.TOO_LARGE,
                steps=(),
                unresolved_character_ids=tuple(
                    c.id for c in sorted(puzzle.characters, key=lambda c: (c.row, c.col, c.id))
                    if c.id not in puzzle.initial_revealed
                ),
                initial_model_count=None,
                remaining_model_count=None,
                checked_assignments=checked_assignments,
                max_characters=max_characters,
            )

        characters = puzzle.characters_by_id
        clues_by_owner = puzzle.clues_by_owner
        row_major_ids = tuple(
            character.id
            for character in sorted(
                puzzle.characters, key=lambda c: (c.row, c.col, c.id)
            )
        )
        all_assignments = tuple(
            dict(zip(row_major_ids, values))
            for values in product((False, True), repeat=character_count)
        )

        # A face-up initial card publicly exposes both its status and clue.
        known_statuses: dict[str, bool] = {
            char_id: puzzle.hidden_solution[char_id]
            for char_id in puzzle.initial_revealed
        }
        active_clues = [clues_by_owner[char_id] for char_id in puzzle.initial_revealed]

        def current_models() -> list[Mapping[str, bool]]:
            return [
                assignment
                for assignment in all_assignments
                if all(assignment[cid] is status for cid, status in known_statuses.items())
                and all(
                    self._validator.evaluate_clue(
                        clue, assignment, characters, puzzle.grid_size
                    )
                    for clue in active_clues
                )
            ]

        models = current_models()
        if not models:
            return SequentialSolvabilityReport(
                status=SequentialAnalysisStatus.INCONSISTENT,
                steps=(),
                unresolved_character_ids=tuple(
                    cid for cid in row_major_ids if cid not in known_statuses
                ),
                initial_model_count=0,
                remaining_model_count=0,
                checked_assignments=checked_assignments,
                max_characters=max_characters,
            )

        initial_model_count = len(models)
        steps: list[SequentialStep] = []

        while len(known_statuses) < character_count:
            selected_id: str | None = None
            selected_status: bool | None = None

            # Deterministic first-forced selection in row-major order.
            for char_id in row_major_ids:
                if char_id in known_statuses:
                    continue
                possible = {model[char_id] for model in models}
                if len(possible) == 1:
                    selected_id = char_id
                    selected_status = next(iter(possible))
                    break

            if selected_id is None or selected_status is None:
                return SequentialSolvabilityReport(
                    status=SequentialAnalysisStatus.STUCK,
                    steps=tuple(steps),
                    unresolved_character_ids=tuple(
                        cid for cid in row_major_ids if cid not in known_statuses
                    ),
                    initial_model_count=initial_model_count,
                    remaining_model_count=len(models),
                    checked_assignments=checked_assignments,
                    max_characters=max_characters,
                )

            models_before = len(models)
            known_statuses[selected_id] = selected_status
            newly_revealed_clue = clues_by_owner[selected_id]
            active_clues.append(newly_revealed_clue)
            models = current_models()

            if not models:
                return SequentialSolvabilityReport(
                    status=SequentialAnalysisStatus.INCONSISTENT,
                    steps=tuple(steps),
                    unresolved_character_ids=tuple(
                        cid for cid in row_major_ids if cid not in known_statuses
                    ),
                    initial_model_count=initial_model_count,
                    remaining_model_count=0,
                    checked_assignments=checked_assignments,
                    max_characters=max_characters,
                )

            steps.append(
                SequentialStep(
                    step=len(steps) + 1,
                    character_id=selected_id,
                    status="CRIMINAL" if selected_status else "INNOCENT",
                    revealed_clue_id=newly_revealed_clue.clue_id,
                    models_before=models_before,
                    models_after=len(models),
                )
            )

        return SequentialSolvabilityReport(
            status=SequentialAnalysisStatus.SOLVED,
            steps=tuple(steps),
            unresolved_character_ids=(),
            initial_model_count=initial_model_count,
            remaining_model_count=len(models),
            checked_assignments=checked_assignments,
            max_characters=max_characters,
        )
