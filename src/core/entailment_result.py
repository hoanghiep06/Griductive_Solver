"""Stable contract between the Entailment Checker and GameEngine."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntailmentStatus(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True, slots=True)
class EntailmentResult:
    """Classification produced from SAT queries against one PublicKB version.

    ``criminal_assumption_satisfiable`` represents SAT(KB AND C_i).
    ``innocent_assumption_satisfiable`` represents SAT(KB AND NOT C_i).
    The factory method encodes the project's entailment definitions and
    prevents callers from reimplementing the truth table inconsistently.
    """

    character_id: str
    status: EntailmentStatus
    kb_version: int
    kb_satisfiable: bool
    criminal_assumption_satisfiable: Optional[bool] = None
    innocent_assumption_satisfiable: Optional[bool] = None

    def __post_init__(self) -> None:
        if not isinstance(self.character_id, str) or not self.character_id.strip():
            raise ValueError("character_id must be a non-empty string")
        if not isinstance(self.status, EntailmentStatus):
            raise TypeError("status must be an EntailmentStatus")
        if type(self.kb_version) is not int or self.kb_version < 0:
            raise ValueError("kb_version must be a non-negative integer")
        if type(self.kb_satisfiable) is not bool:
            raise TypeError("kb_satisfiable must be bool")
        for name in ("criminal_assumption_satisfiable", "innocent_assumption_satisfiable"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be bool or None")

        if self.status is EntailmentStatus.INCONSISTENT:
            if self.kb_satisfiable:
                raise ValueError("INCONSISTENT requires an unsatisfiable base KB")
            if self.criminal_assumption_satisfiable is not None or self.innocent_assumption_satisfiable is not None:
                raise ValueError("Assumption queries must be omitted when the base KB is UNSAT")
            return

        if not self.kb_satisfiable:
            raise ValueError("A satisfiable entailment status requires a satisfiable base KB")
        c_sat = self.criminal_assumption_satisfiable
        i_sat = self.innocent_assumption_satisfiable
        if type(c_sat) is not bool or type(i_sat) is not bool:
            raise ValueError("A satisfiable base KB requires both assumption SAT results")
        expected = self._classify(self.kb_satisfiable, c_sat, i_sat)
        if expected is not self.status:
            raise ValueError(
                f"Entailment status {self.status.value} conflicts with SAT evidence "
                f"({expected.value})"
            )

    @staticmethod
    def _classify(kb_sat: bool, criminal_sat: bool, innocent_sat: bool) -> EntailmentStatus:
        if not kb_sat:
            return EntailmentStatus.INCONSISTENT
        if criminal_sat and innocent_sat:
            return EntailmentStatus.UNKNOWN
        if criminal_sat and not innocent_sat:
            return EntailmentStatus.CRIMINAL
        if not criminal_sat and innocent_sat:
            return EntailmentStatus.INNOCENT
        raise ValueError("Both assumptions cannot be UNSAT when the base KB is SAT")

    @classmethod
    def from_sat_results(
        cls,
        character_id: str,
        kb_version: int,
        kb_satisfiable: bool,
        criminal_assumption_satisfiable: Optional[bool] = None,
        innocent_assumption_satisfiable: Optional[bool] = None,
    ) -> "EntailmentResult":
        if type(kb_satisfiable) is not bool:
            raise TypeError("kb_satisfiable must be bool")
        if not kb_satisfiable:
            return cls(
                character_id=character_id,
                status=EntailmentStatus.INCONSISTENT,
                kb_version=kb_version,
                kb_satisfiable=False,
            )
        if type(criminal_assumption_satisfiable) is not bool or type(innocent_assumption_satisfiable) is not bool:
            raise TypeError("Both assumption SAT results must be bool when the base KB is SAT")
        status = cls._classify(
            kb_satisfiable,
            criminal_assumption_satisfiable,
            innocent_assumption_satisfiable,
        )
        return cls(
            character_id=character_id,
            status=status,
            kb_version=kb_version,
            kb_satisfiable=True,
            criminal_assumption_satisfiable=criminal_assumption_satisfiable,
            innocent_assumption_satisfiable=innocent_assumption_satisfiable,
        )
