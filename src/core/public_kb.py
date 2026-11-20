"""Public Knowledge Base: revealed clues and proved verdicts only."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from src.core.clue import Clue
from src.core.cnf_types import CNFFormula, Literal
from src.core.variable_map import VariableMap


class KnowledgeBaseConflictError(ValueError):
    """Raised when a new public fact conflicts with an existing public fact."""


@dataclass(frozen=True, slots=True)
class PublicKBSnapshot:
    """Read-only point-in-time view supplied to the Logic Agent/Encoder."""

    version: int
    revealed_clues: tuple[Clue, ...]
    proved_verdicts: Mapping[str, bool]
    unit_clauses: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "revealed_clues", tuple(self.revealed_clues))
        object.__setattr__(self, "proved_verdicts", MappingProxyType(dict(self.proved_verdicts)))
        object.__setattr__(self, "unit_clauses", tuple(tuple(clause) for clause in self.unit_clauses))

    def get_unit_clauses_for_verdicts(self) -> CNFFormula:
        """Return a detached list-based CNF fragment for Encoder integration."""
        return [list(clause) for clause in self.unit_clauses]


class PublicKB:
    """Mutable KB owned by GameEngine; consumers should receive snapshots.

    Each successful standalone mutation advances the version once. GameEngine
    uses ``record_reveal`` so the verdict and clue for one card advance it once
    together. The owning GameEngine seeds new/restarted KBs above the previous
    version to prevent proofs from an earlier game state becoming valid again.
    """

    def __init__(self, var_map: VariableMap, *, initial_version: int = 0) -> None:
        if not isinstance(var_map, VariableMap):
            raise TypeError("var_map must be a VariableMap")
        if not var_map.is_frozen:
            raise ValueError("VariableMap must be frozen before constructing PublicKB")
        if type(initial_version) is not int or initial_version < 0:
            raise ValueError("initial_version must be a non-negative integer")
        self._var_map = var_map
        self._revealed_clues: dict[str, Clue] = {}
        self._proved_verdicts: dict[str, bool] = {}
        self._version = initial_version

    @property
    def version(self) -> int:
        return self._version

    @property
    def var_map(self) -> VariableMap:
        """The shared, frozen mapping needed by the CNF Encoder."""
        return self._var_map

    @property
    def revealed_clues(self) -> tuple[Clue, ...]:
        """Return immutable clue objects, matching the snapshot API."""
        return tuple(self._revealed_clues.values())

    @property
    def proved_verdicts(self) -> dict[str, bool]:
        """Return a detached copy of proved character statuses."""
        return dict(self._proved_verdicts)

    def add_revealed_clue(self, clue: Clue) -> bool:
        if not isinstance(clue, Clue):
            raise TypeError("add_revealed_clue expects a validated Clue object")
        self._var_map.get_var(clue.owner_id)
        if clue.owner_id not in self._proved_verdicts:
            raise ValueError(
                f"Cannot reveal clue {clue.clue_id!r} before owner {clue.owner_id!r} is proved"
            )
        existing = self._revealed_clues.get(clue.clue_id)
        if existing is not None:
            if existing.to_dict() == clue.to_dict():
                return False
            raise KnowledgeBaseConflictError(
                f"Clue ID {clue.clue_id!r} already exists with different content"
            )
        if any(existing_clue.owner_id == clue.owner_id for existing_clue in self._revealed_clues.values()):
            raise KnowledgeBaseConflictError(
                f"A clue for owner {clue.owner_id!r} has already been revealed"
            )
        self._revealed_clues[clue.clue_id] = clue
        self._version += 1
        return True

    def record_reveal(self, char_id: str, status: bool, clue: Clue) -> bool:
        """Atomically add one proved verdict and its newly revealed clue.

        A successful card reveal advances the public KB version exactly once,
        regardless of the two pieces of information (verdict + clue) added.
        """
        self._var_map.get_var(char_id)
        if type(status) is not bool:
            raise TypeError("status must be bool (True=CRIMINAL, False=INNOCENT)")
        if not isinstance(clue, Clue):
            raise TypeError("record_reveal expects a validated Clue object")
        if clue.owner_id != char_id:
            raise ValueError(
                f"Clue owner {clue.owner_id!r} does not match revealed character {char_id!r}"
            )

        existing_status = self._proved_verdicts.get(char_id)
        if existing_status is not None and existing_status is not status:
            raise KnowledgeBaseConflictError(
                f"Conflicting verdict for {char_id!r}: existing public status differs"
            )

        existing_clue = self._revealed_clues.get(clue.clue_id)
        if existing_clue is not None and existing_clue.to_dict() != clue.to_dict():
            raise KnowledgeBaseConflictError(
                f"Clue ID {clue.clue_id!r} already exists with different content"
            )
        if existing_clue is None and any(
            item.owner_id == char_id for item in self._revealed_clues.values()
        ):
            raise KnowledgeBaseConflictError(
                f"A clue for owner {char_id!r} has already been revealed"
            )

        verdict_added = char_id not in self._proved_verdicts
        clue_added = existing_clue is None
        if not verdict_added and not clue_added:
            return False

        # All validations occur before mutation, so this operation is atomic.
        if verdict_added:
            self._proved_verdicts[char_id] = status
        if clue_added:
            self._revealed_clues[clue.clue_id] = clue
        self._version += 1
        return True

    def add_proved_verdict(self, char_id: str, status: bool) -> bool:
        self._var_map.get_var(char_id)
        if type(status) is not bool:
            raise TypeError("status must be bool (True=CRIMINAL, False=INNOCENT)")
        if char_id in self._proved_verdicts:
            if self._proved_verdicts[char_id] == status:
                return False
            raise KnowledgeBaseConflictError(
                f"Conflicting verdict for {char_id!r}: "
                f"already {self._status_name(self._proved_verdicts[char_id])}, "
                f"cannot replace with {self._status_name(status)}"
            )
        self._proved_verdicts[char_id] = status
        self._version += 1
        return True

    @staticmethod
    def _status_name(status: bool) -> str:
        return "CRIMINAL" if status else "INNOCENT"

    def get_unit_clauses_for_verdicts(self) -> CNFFormula:
        """Encode proved statuses as deterministic unit clauses."""
        unit_clauses: CNFFormula = []
        ordered = sorted(self._proved_verdicts.items(), key=lambda item: self._var_map.get_var(item[0]))
        for char_id, status in ordered:
            literal: Literal = self._var_map.to_literal(char_id, status)
            unit_clauses.append([literal])
        return unit_clauses

    def is_proved(self, char_id: str) -> bool:
        self._var_map.get_var(char_id)
        return char_id in self._proved_verdicts

    def get_status(self, char_id: str) -> bool:
        self._var_map.get_var(char_id)
        if char_id not in self._proved_verdicts:
            raise KeyError(f"[PublicKB] Status for {char_id!r} has not been proved")
        return self._proved_verdicts[char_id]

    def get_revealed_clue(self, clue_id: str) -> Clue:
        try:
            return self._revealed_clues[clue_id]
        except KeyError as exc:
            raise KeyError(f"Clue {clue_id!r} has not been revealed") from exc

    def get_snapshot(self) -> PublicKBSnapshot:
        unit_clauses = []
        ordered_verdicts = sorted(
            self._proved_verdicts.items(), key=lambda item: self._var_map.get_var(item[0])
        )
        for char_id, status in ordered_verdicts:
            unit_clauses.append((self._var_map.to_literal(char_id, status),))
        return PublicKBSnapshot(
            version=self._version,
            revealed_clues=tuple(self._revealed_clues.values()),
            proved_verdicts=self._proved_verdicts,
            unit_clauses=tuple(unit_clauses),
        )

    def clone(self) -> "PublicKB":
        """Clone KB state while sharing the same immutable variable mapping."""
        cloned = PublicKB(self._var_map)
        cloned._revealed_clues = dict(self._revealed_clues)
        cloned._proved_verdicts = dict(self._proved_verdicts)
        cloned._version = self._version
        return cloned

    def __repr__(self) -> str:
        return (
            f"<PublicKB version={self._version}, clues={len(self._revealed_clues)}, "
            f"verdicts={len(self._proved_verdicts)}>"
        )
