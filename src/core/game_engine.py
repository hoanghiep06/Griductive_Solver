"""GameEngine for Griductive.

This class owns the complete puzzle, including hidden labels and unrevealed
clues. External components should receive only ``PublicKBSnapshot`` objects.
A verdict is accepted only when an EntailmentResult proves that the requested
status is forced by the *current public KB version*.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.core.character import Character
from src.core.clue import Clue
from src.core.entailment_result import EntailmentResult, EntailmentStatus
from src.core.public_kb import PublicKB, PublicKBSnapshot
from src.core.puzzle import Puzzle
from src.core.puzzle_loader import PuzzleLoader
from src.core.variable_map import VariableMap


class GameEngineIntegrityError(RuntimeError):
    """Internal consistency failure between public entailment and puzzle key.

    The message intentionally contains no hidden status or character details;
    applications should log this as an internal solver/puzzle error, not present
    hidden-answer information to the player.
    """


class VerdictResponse(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"
    ALREADY_SOLVED = "ALREADY_SOLVED"
    STALE_PROOF = "STALE_PROOF"


class GameEngine:
    """Own hidden game state and mediate all accepted reveals."""

    def __init__(self, puzzle_json_path: str | Path, loader: Optional[PuzzleLoader] = None) -> None:
        self._loader = loader or PuzzleLoader()
        self._puzzle: Puzzle
        self._var_map: VariableMap
        self._public_kb: PublicKB
        self._characters_by_id: dict[str, Character]
        self._clues_by_owner: dict[str, Clue]
        self._hidden_solution: dict[str, bool]
        self._puzzle_path: Path
        self.load_puzzle(puzzle_json_path)

    def load_puzzle(self, puzzle_json_path: str | Path) -> None:
        """Load and validate a puzzle, then atomically replace the game state.

        If loading or validation fails, the currently loaded game is preserved.
        """
        path = Path(puzzle_json_path)
        puzzle = self._loader.load(path)

        # Build the complete new runtime state in local variables first.
        variable_map = VariableMap()
        variable_map.register_characters(puzzle.characters)
        variable_map.freeze_primary_variables()

        previous_kb = getattr(self, "_public_kb", None)
        initial_version = previous_kb.version + 1 if previous_kb is not None else 0
        public_kb = PublicKB(variable_map, initial_version=initial_version)
        characters_by_id = {character.id: character for character in puzzle.characters}
        clues_by_owner = {clue.owner_id: clue for clue in puzzle.clues}

        for char_id in puzzle.initial_revealed:
            public_kb.record_reveal(
                char_id, puzzle.hidden_solution[char_id], clues_by_owner[char_id]
            )

        self._puzzle = puzzle
        self._var_map = variable_map
        self._public_kb = public_kb
        self._characters_by_id = characters_by_id
        self._clues_by_owner = clues_by_owner
        self._hidden_solution = dict(puzzle.hidden_solution)
        self._puzzle_path = path

    def restart(self) -> None:
        """Restore the initially revealed cards without changing variable IDs."""
        # Never reuse a version number from a previous game state: a proof
        # created before Restart/Load must remain stale even if the visible KB
        # contents later happen to look similar.
        public_kb = PublicKB(
            self._var_map, initial_version=self._public_kb.version + 1
        )
        for char_id in self._puzzle.initial_revealed:
            public_kb.record_reveal(
                char_id, self._hidden_solution[char_id], self._clues_by_owner[char_id]
            )
        self._public_kb = public_kb

    @property
    def grid_size(self) -> int:
        return self._puzzle.grid_size

    @property
    def puzzle_id(self) -> str:
        return self._puzzle.puzzle_id

    @property
    def var_map(self) -> VariableMap:
        """Stable primary mapping; it is frozen after puzzle loading."""
        return self._var_map

    @property
    def public_kb_version(self) -> int:
        return self._public_kb.version

    @property
    def characters(self) -> tuple[Character, ...]:
        """Immutable character metadata for GUI rendering."""
        return self._puzzle.characters

    def get_public_snapshot(self) -> PublicKBSnapshot:
        return self._public_kb.get_snapshot()

    def get_character(self, char_id: str) -> Character:
        try:
            return self._characters_by_id[char_id]
        except KeyError as exc:
            raise KeyError(f"Unknown character ID: {char_id!r}") from exc

    def get_character_info(self, char_id: str) -> dict[str, Any]:
        """Return a detached dictionary for presentation-layer compatibility."""
        return self.get_character(char_id).to_dict()

    def get_revealed_clues(self) -> tuple[Clue, ...]:
        """Return revealed immutable Clue objects (same type as the snapshot)."""
        return self._public_kb.revealed_clues

    def get_proved_verdicts(self) -> dict[str, bool]:
        return self._public_kb.proved_verdicts

    def get_public_state(self) -> dict[str, Any]:
        """Return JSON-ready public state; hidden solution/clues are excluded."""
        snapshot = self._public_kb.get_snapshot()
        return {
            "puzzle_id": self._puzzle.puzzle_id,
            "grid_size": self._puzzle.grid_size,
            "characters": [character.to_dict() for character in self._puzzle.characters],
            "proved_verdicts": {
                char_id: "CRIMINAL" if status else "INNOCENT"
                for char_id, status in snapshot.proved_verdicts.items()
            },
            "revealed_clues": [clue.to_dict() for clue in snapshot.revealed_clues],
            "kb_version": snapshot.version,
        }

    def submit_verdict(
        self,
        char_id: str,
        claimed_status: bool,
        entailment: EntailmentResult,
    ) -> tuple[VerdictResponse, Optional[dict[str, Any]]]:
        """Submit a verdict backed by an EntailmentResult for the current KB.

        ``claimed_status`` is True for CRIMINAL and False for INNOCENT.
        UNKNOWN always maps to NOT_PROVABLE, regardless of the hidden answer.
        CONTRADICTED is returned only when the *opposite public entailment* is
        forced. A stale proof is rejected after any KB update.

        The Entailment Checker is a trusted project component and must create
        this result from the two SAT assumption queries described in the brief.
        This object is an application contract, not a cryptographic certificate.
        """
        if not isinstance(char_id, str) or char_id not in self._characters_by_id:
            raise KeyError(f"Unknown character ID: {char_id!r}")
        if type(claimed_status) is not bool:
            raise TypeError("claimed_status must be bool (True=CRIMINAL, False=INNOCENT)")
        if not isinstance(entailment, EntailmentResult):
            raise TypeError(
                "entailment must be EntailmentResult; a Boolean 'is_forced_by_logic' is not accepted"
            )
        if entailment.character_id != char_id:
            raise ValueError(
                f"Entailment result is for {entailment.character_id!r}, not {char_id!r}"
            )

        if self._public_kb.is_proved(char_id):
            return VerdictResponse.ALREADY_SOLVED, None
        if entailment.kb_version != self._public_kb.version:
            return VerdictResponse.STALE_PROOF, None
        if entailment.status is EntailmentStatus.INCONSISTENT:
            return VerdictResponse.INCONSISTENT, None
        if entailment.status is EntailmentStatus.UNKNOWN:
            return VerdictResponse.NOT_PROVABLE, None

        forced_status = entailment.status is EntailmentStatus.CRIMINAL
        if claimed_status != forced_status:
            return VerdictResponse.CONTRADICTED, None

        # Defense-in-depth: a logically forced status must agree with the
        # validated puzzle key. This is an internal fatal error, never a player
        # feedback category. It catches upstream CNF/DPLL/entailment defects.
        if forced_status is not self._hidden_solution[char_id]:
            raise GameEngineIntegrityError(
                "Internal solver/puzzle consistency check failed."
            )

        # Apply verdict + clue reveal as one KB transaction, then swap.
        updated_kb = self._public_kb.clone()
        clue = self._clues_by_owner[char_id]
        updated_kb.record_reveal(char_id, forced_status, clue)
        self._public_kb = updated_kb
        return VerdictResponse.ACCEPTED, clue.to_dict()

    def is_solved(self) -> bool:
        return set(self._public_kb.proved_verdicts) == set(self._characters_by_id)

    def get_unsolved_characters(self) -> list[str]:
        """Return unresolved character IDs in deterministic row-major order."""
        solved = self._public_kb.proved_verdicts
        ordered = sorted(
            self._puzzle.characters,
            key=lambda character: (character.row, character.col, character.id),
        )
        return [character.id for character in ordered if character.id not in solved]

    def get_clue_for_character(self, char_id: str) -> Optional[dict[str, Any]]:
        """Return a clue only after its owner card has been revealed."""
        if char_id not in self._characters_by_id:
            raise KeyError(f"Unknown character ID: {char_id!r}")
        clue = self._clues_by_owner[char_id]
        if clue.clue_id not in {item.clue_id for item in self._public_kb.get_snapshot().revealed_clues}:
            return None
        return clue.to_dict()
