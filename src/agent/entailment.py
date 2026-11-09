"""No-guess entailment over public CNF; no game or private puzzle input.

The injected solver must implement ``solve(clauses) -> bool``. Use an explicit
SolverAdapter when the team's DPLL eventually returns a different result type.
No SAT algorithm or fallback is implemented here.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any, Protocol

from src.core.cnf_types import CNFFormula, validate_cnf
from src.core.entailment_result import EntailmentResult, EntailmentStatus
from src.core.variable_map import VariableMap

Verdict = EntailmentStatus  # Reuse TV1's enum, including its identity.


class SolverProtocolError(RuntimeError):
    """Solver returned an invalid status or contradictory SAT evidence."""


class SATSolver(Protocol):
    def solve(self, clauses: CNFFormula) -> bool:
        """Return exactly True (SAT) or False (UNSAT), never a partial model."""
        ...


class SolverAdapter:
    """Explicit bridge for a non-boolean solver API; never infer truthiness.

    ``decode`` must reject timeouts/UNKNOWN/errors and return an actual bool.
    Ownership/metrics of the wrapped solver are left with the caller.
    """

    def __init__(self, solve: Callable[[CNFFormula], Any], decode: Callable[[Any], bool]):
        if not callable(solve) or not callable(decode):
            raise TypeError("solve and decode must be callable")
        self._solve = solve
        self._decode = decode

    def solve(self, clauses: CNFFormula) -> bool:
        result = self._decode(self._solve(clauses))
        if type(result) is not bool:
            raise SolverProtocolError("Solver adapter must decode exactly bool SAT/UNSAT")
        return result


@dataclass(frozen=True, slots=True)
class SATQuery:
    assumption: int | None
    satisfiable: bool
    sequence: int  # 1-based within one classify/classify_all invocation.


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    verdict: Verdict
    queries: tuple[SATQuery, ...]

    @property
    def sat_calls(self) -> int:
        return len(self.queries)

    def to_engine_result(self, character_id: str, kb_version: int) -> EntailmentResult:
        """Attach the caller's public character/version metadata to SAT evidence.

        Caller must use the same snapshot and VariableMap used to encode CNF.
        This is a trusted component contract, not a cryptographic proof.
        """
        assumptions = {q.assumption: q.satisfiable for q in self.queries[1:]}
        criminal = next((sat for lit, sat in assumptions.items() if lit > 0), None)
        innocent = next((sat for lit, sat in assumptions.items() if lit < 0), None)
        return EntailmentResult.from_sat_results(
            character_id=character_id,
            kb_version=kb_version,
            kb_satisfiable=self.queries[0].satisfiable,
            criminal_assumption_satisfiable=criminal,
            innocent_assumption_satisfiable=innocent,
        )


@dataclass(frozen=True, slots=True)
class BatchResult:
    results: Mapping[str, ClassificationResult]
    queries: tuple[SATQuery, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", MappingProxyType(dict(self.results)))

    @property
    def verdicts(self) -> Mapping[str, Verdict]:
        return MappingProxyType({cid: result.verdict for cid, result in self.results.items()})

    @property
    def sat_calls(self) -> int:
        """Count actual calls, without recounting the shared base query."""
        return len(self.queries)


def row_major_key(cell_id: str) -> tuple[int, int]:
    """Sort A1,B1,...,A2,... numerically; support multi-letter columns."""
    if not isinstance(cell_id, str):
        raise TypeError("cell ID must be a string")
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", cell_id)
    if match is None:
        raise ValueError(f"Invalid cell ID: {cell_id!r}; expected e.g. A1")
    col = 0
    for letter in match[1]:
        col = col * 26 + ord(letter) - ord("A") + 1
    return int(match[2]), col


class EntailmentChecker:
    """Classify public CNF via one base check and two assumptions per variable.

    Supply the official frozen VariableMap in game integration to reject
    auxiliary IDs and mismatched cell-to-variable mappings. In standalone CNF
    tests the caller supplies the authoritative primary mapping in unresolved.
    """

    def __init__(self, solver: SATSolver, *, variable_map: VariableMap | None = None):
        if not callable(getattr(solver, "solve", None)):
            raise TypeError("solver must provide solve(clauses) -> bool")
        if variable_map is not None:
            if not isinstance(variable_map, VariableMap):
                raise TypeError("variable_map must be the official VariableMap")
            if not variable_map.is_frozen:
                raise ValueError("Freeze primary variables before constructing checker")
        self._solver = solver
        self._variable_map = variable_map

    def _validate_variable(self, variable: int) -> None:
        if type(variable) is not int:
            raise TypeError("SAT variable ID must be an integer, not bool")
        if variable <= 0:
            raise ValueError("SAT variable ID must be positive")
        if self._variable_map is not None:
            if variable not in self._variable_map.primary_mapping.values():
                raise ValueError("Only allocated primary variables may be classified")

    def _copy_cnf(self, clauses: Sequence[Sequence[int]]) -> CNFFormula:
        if not isinstance(clauses, (list, tuple)):
            raise TypeError("CNF must be a list or tuple of clauses")
        if any(not isinstance(clause, (list, tuple)) for clause in clauses):
            raise TypeError("Each clause must be a list or tuple of integer literals")
        validate_cnf(
            clauses,
            variable_count=self._variable_map.total_variables if self._variable_map else None,
        )
        return [list(clause) for clause in clauses]

    def _query(self, cnf: CNFFormula, assumption: int | None, sequence: int) -> SATQuery:
        # Detach *every* clause for *every* call, even from a mutating solver.
        temporary_cnf = [clause[:] for clause in cnf]
        if assumption is not None:
            temporary_cnf.append([assumption])
        satisfiable = self._solver.solve(temporary_cnf)
        if type(satisfiable) is not bool:
            raise SolverProtocolError("solve() must return exactly bool SAT/UNSAT")
        return SATQuery(assumption, satisfiable, sequence)

    def _classify_consistent(
        self, cnf: CNFFormula, variable: int, base: SATQuery, sequence: int,
    ) -> ClassificationResult:
        innocent = self._query(cnf, -variable, sequence)
        criminal = self._query(cnf, variable, sequence + 1)
        if not innocent.satisfiable and not criminal.satisfiable:
            raise SolverProtocolError("Base KB is SAT but both assumptions are UNSAT")
        verdict = (
            Verdict.CRIMINAL if not innocent.satisfiable else
            Verdict.INNOCENT if not criminal.satisfiable else Verdict.UNKNOWN
        )
        return ClassificationResult(verdict, (base, innocent, criminal))

    def classify(self, clauses: Sequence[Sequence[int]], variable: int) -> ClassificationResult:
        self._validate_variable(variable)
        cnf = self._copy_cnf(clauses)
        base = self._query(cnf, None, 1)
        if not base.satisfiable:
            return ClassificationResult(Verdict.INCONSISTENT, (base,))
        return self._classify_consistent(cnf, variable, base, 2)

    def classify_all(
        self, clauses: Sequence[Sequence[int]], unresolved: Mapping[str, int],
    ) -> BatchResult:
        cnf = self._copy_cnf(clauses)
        if not isinstance(unresolved, Mapping):
            raise TypeError("unresolved must map cell IDs to primary variable IDs")
        items = list(unresolved.items())
        seen: set[int] = set()
        for cid, variable in items:
            row_major_key(cid)
            self._validate_variable(variable)
            if variable in seen:
                raise ValueError("Multiple characters share one primary variable ID")
            seen.add(variable)
            if self._variable_map is not None and self._variable_map.get_var(cid) != variable:
                raise ValueError(f"Variable ID for {cid!r} differs from VariableMap")
        items.sort(key=lambda item: row_major_key(item[0]))
        base = self._query(cnf, None, 1)
        queries = [base]
        results: dict[str, ClassificationResult] = {}
        for cid, variable in items:
            if base.satisfiable:
                result = self._classify_consistent(cnf, variable, base, len(queries) + 1)
                queries.extend(result.queries[1:])
            else:
                result = ClassificationResult(Verdict.INCONSISTENT, (base,))
            results[cid] = result
        return BatchResult(results, tuple(queries))

    def first_forced(
        self, clauses: Sequence[Sequence[int]], unresolved: Mapping[str, int],
    ) -> tuple[str, ClassificationResult] | None:
        """Return first row-major forced result; None for unknown/inconsistent.

        Uses classify_all (1+2n calls when SAT). Use its full BatchResult when
        recording an experiment, including terminal INCONSISTENT states.
        """
        batch = self.classify_all(clauses, unresolved)
        for cid, result in batch.results.items():
            if result.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT):
                return cid, result
        return None
