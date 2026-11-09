"""Independent tests use bounded exhaustive SAT, never a production fallback."""

import copy
from dataclasses import FrozenInstanceError
from itertools import product

import pytest

from src.agent.entailment import (
    EntailmentChecker, SolverAdapter, SolverProtocolError, Verdict, row_major_key,
)
from src.core.entailment_result import EntailmentResult, EntailmentStatus
from src.core.variable_map import VariableMap


class ExhaustiveTestSolver:
    """Truth-table oracle for at most 8 variables, only in this test module."""

    def __init__(self):
        self.calls = []

    def solve(self, clauses):
        self.calls.append(copy.deepcopy(clauses))
        variables = sorted({abs(lit) for clause in clauses for lit in clause})
        assert len(variables) <= 8, "Test oracle is deliberately bounded"
        for values in product((False, True), repeat=len(variables)):
            model = dict(zip(variables, values))
            if all(any(model[abs(lit)] == (lit > 0) for lit in clause) for clause in clauses):
                return True
        return False


@pytest.mark.parametrize("clauses,variable,expected", [
    ([[1]], 1, Verdict.CRIMINAL),
    ([[-1]], 1, Verdict.INNOCENT),
    ([[1, 2]], 1, Verdict.UNKNOWN),
    ([[1], [-1]], 1, Verdict.INCONSISTENT),
    ([[1, 2], [-1, 2]], 2, Verdict.CRIMINAL),
    ([], 1, Verdict.UNKNOWN),
    ([[]], 1, Verdict.INCONSISTENT),
    ([[1, -1]], 1, Verdict.UNKNOWN),
    ([[1]], 8, Verdict.UNKNOWN),
])
def test_classification(clauses, variable, expected):
    solver = ExhaustiveTestSolver()
    result = EntailmentChecker(solver).classify(clauses, variable)
    assert result.verdict is expected
    assert result.sat_calls == (1 if expected is Verdict.INCONSISTENT else 3)
    assert [q.sequence for q in result.queries] == list(range(1, result.sat_calls + 1))
    assert result.queries[0].assumption is None
    if result.sat_calls == 3:
        assert [q.assumption for q in result.queries] == [None, -variable, variable]


def test_immutability_repeated_calls_even_with_mutating_solver():
    class MutatingSolver(ExhaustiveTestSolver):
        def solve(self, clauses):
            answer = super().solve(clauses)
            if clauses:
                clauses[0].append(999)
            clauses.clear()
            return answer

    clauses = [[1, 2], [-1, 2]]
    before = copy.deepcopy(clauses)
    solver = MutatingSolver()
    checker = EntailmentChecker(solver)
    assert checker.classify(clauses, 2) == checker.classify(clauses, 2)
    assert clauses == before
    assert solver.calls[0] == before
    assert solver.calls[1] == before + [[-2]]
    assert solver.calls[2] == before + [[2]]


def test_batch_checks_consistency_once_and_tracks_calls():
    solver = ExhaustiveTestSolver()
    batch = EntailmentChecker(solver).classify_all([[1], [-2]], {"C1": 3, "B1": 2, "A1": 1})
    assert dict(batch.verdicts) == {"A1": Verdict.CRIMINAL, "B1": Verdict.INNOCENT, "C1": Verdict.UNKNOWN}
    assert batch.sat_calls == len(solver.calls) == 7
    assert [q.sequence for q in batch.queries] == list(range(1, 8))
    assert sum(q.assumption is None for q in batch.queries) == 1
    with pytest.raises(TypeError):
        batch.results["A1"] = None
    with pytest.raises(FrozenInstanceError):
        batch.queries[0].satisfiable = False


@pytest.mark.parametrize("clauses,expected_calls", [([[1], [-1]], 1), ([], 1)])
def test_batch_inconsistent_or_empty(clauses, expected_calls):
    unresolved = {"A1": 1, "B1": 2} if clauses else {}
    batch = EntailmentChecker(ExhaustiveTestSolver()).classify_all(clauses, unresolved)
    assert batch.sat_calls == expected_calls
    assert all(v is Verdict.INCONSISTENT for v in batch.verdicts.values())


def test_first_forced_is_row_major_independent_of_mapping_and_variable_ids():
    checker = EntailmentChecker(ExhaustiveTestSolver())
    chosen = checker.first_forced([[3], [-1], [2]], {"A2": 1, "B1": 2, "A1": 3})
    assert chosen[0] == "A1"
    assert chosen[1].verdict is Verdict.CRIMINAL
    assert sorted(["A10", "AA1", "B2", "Z1"], key=row_major_key) == ["Z1", "AA1", "B2", "A10"]


@pytest.mark.parametrize("clauses", [[], [[1], [-1]]])
def test_first_forced_never_selects_unknown_or_inconsistent(clauses):
    assert EntailmentChecker(ExhaustiveTestSolver()).first_forced(clauses, {"A1": 1}) is None


@pytest.mark.parametrize("clauses,error", [
    (None, TypeError), ({}, TypeError), ("1", TypeError),
    ([1], TypeError), (["1"], TypeError), ([{1}], TypeError),
    ([[0]], ValueError), ([[True]], TypeError), ([[1.0]], TypeError),
    ([["1"]], TypeError), ([[None]], TypeError),
])
def test_invalid_cnf(clauses, error):
    solver = ExhaustiveTestSolver()
    with pytest.raises(error):
        EntailmentChecker(solver).classify(clauses, 1)
    assert solver.calls == []


@pytest.mark.parametrize("variable,error", [(0, ValueError), (-1, ValueError), (True, TypeError),
                                             (1.0, TypeError), ("1", TypeError), (None, TypeError)])
def test_invalid_variable(variable, error):
    with pytest.raises(error):
        EntailmentChecker(ExhaustiveTestSolver()).classify([], variable)


@pytest.mark.parametrize("unresolved,error", [
    ([], TypeError), (None, TypeError), ({"A1": 1, "B1": 1}, ValueError),
    ({"A0": 1}, ValueError), ({"a1": 1}, ValueError), ({1: 1}, TypeError),
    ({"A1": True}, TypeError), ({"A1": 0}, ValueError),
])
def test_invalid_unresolved(unresolved, error):
    solver = ExhaustiveTestSolver()
    with pytest.raises(error):
        EntailmentChecker(solver).classify_all([], unresolved)
    assert not solver.calls


@pytest.mark.parametrize("output", [None, 0, 1, "SAT", "UNSAT", {}, {1: True}, (True, {})])
def test_invalid_solver_status_never_uses_truthiness(output):
    class BadSolver:
        def solve(self, clauses):
            return output
    with pytest.raises(SolverProtocolError):
        EntailmentChecker(BadSolver()).classify([], 1)


def test_invalid_both_assumptions_unsat_raises():
    class BadSolver:
        def __init__(self):
            self.answers = iter([True, False, False])
        def solve(self, clauses):
            return next(self.answers)
    with pytest.raises(SolverProtocolError, match="both assumptions"):
        EntailmentChecker(BadSolver()).classify([], 1)


@pytest.mark.parametrize("answers", [[True, None], [True, True, "UNSAT"]])
def test_invalid_assumption_status_is_rejected(answers):
    class BadSolver:
        def solve(self, clauses):
            return answers.pop(0)
    with pytest.raises(SolverProtocolError):
        EntailmentChecker(BadSolver()).classify([], 1)


def test_explicit_solver_adapter_and_error_propagation():
    solver = ExhaustiveTestSolver()
    adapter = SolverAdapter(lambda clauses: {"sat": solver.solve(clauses)}, lambda raw: raw["sat"])
    assert EntailmentChecker(adapter).classify([[1]], 1).verdict is Verdict.CRIMINAL
    with pytest.raises(SolverProtocolError):
        EntailmentChecker(SolverAdapter(lambda _: "UNKNOWN", lambda raw: raw)).classify([], 1)
    def timeout(_):
        raise TimeoutError("solver timed out")
    with pytest.raises(TimeoutError):
        EntailmentChecker(SolverAdapter(timeout, lambda raw: raw)).classify([], 1)


def test_constructor_contract():
    with pytest.raises(TypeError):
        EntailmentChecker(lambda _: True)
    with pytest.raises(TypeError):
        EntailmentChecker(ExhaustiveTestSolver(), variable_map={})
    with pytest.raises(ValueError):
        EntailmentChecker(ExhaustiveTestSolver(), variable_map=VariableMap())
    with pytest.raises(TypeError):
        SolverAdapter(None, bool)


def test_official_map_rejects_auxiliaries_mismatches_and_unallocated_literals():
    vm = VariableMap()
    vm.register_character("B1")
    vm.register_character("A1")
    vm.freeze_primary_variables()
    aux = vm.allocate_auxiliary_variable()
    checker = EntailmentChecker(ExhaustiveTestSolver(), variable_map=vm)
    with pytest.raises(ValueError, match="primary"):
        checker.classify([], aux)
    with pytest.raises(ValueError, match="differs"):
        checker.classify_all([], {"A1": 1})
    with pytest.raises(ValueError):
        checker.classify([[aux + 1]], 1)
    batch = checker.classify_all([[aux], [2]], {"B1": 1, "A1": 2})
    assert list(batch.verdicts) == ["A1", "B1"]
    assert batch.verdicts["A1"] is Verdict.CRIMINAL


@pytest.mark.parametrize("clauses", [[[1]], [[-1]], [], [[1], [-1]]])
def test_bridge_uses_official_entailment_result(clauses):
    result = EntailmentChecker(ExhaustiveTestSolver()).classify(clauses, 1)
    proof = result.to_engine_result("A1", 17)
    assert type(proof) is EntailmentResult
    assert proof.status is result.verdict
    assert proof.character_id == "A1" and proof.kb_version == 17
    assert Verdict is EntailmentStatus


def test_privacy_checker_only_accepts_public_cnf_and_mapping():
    # Same public input yields same result regardless of any external secret.
    public = [[1, 2]]
    checker = EntailmentChecker(ExhaustiveTestSolver())
    for hidden_key in ({1: True, 2: False}, {1: False, 2: True}):
        assert checker.classify(public, 1).verdict is Verdict.UNKNOWN
        with pytest.raises(TypeError):
            checker.classify(public, 1, hidden_solution=hidden_key)
