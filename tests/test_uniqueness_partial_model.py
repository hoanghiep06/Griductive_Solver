"""Test check_uniqueness với solver trả về model MỘT PHẦN (biến tự do bị bỏ qua)."""

from itertools import product

from src.agent.uniqueness import (
    UniquenessStatus,
    _build_blocking_clause,
    _decode_model,
    check_uniqueness,
)


class PartialModelSolver:
    """Solver vét cạn, chỉ trả về các biến XUẤT HIỆN trong CNF (giống DPLL dừng sớm)."""

    def __init__(self):
        self._stats = {"decisions": 0, "propagations": 0, "backtracks": 0, "runtime": 0.0}

    def solve_with_model(self, cnf):
        variables = sorted({abs(lit) for clause in cnf for lit in clause})
        for values in product([False, True], repeat=len(variables)):
            model = dict(zip(variables, values))
            if all(any(model[abs(l)] == (l > 0) for l in clause) for clause in cnf):
                return True, model
        return False, None

    def get_stats(self):
        return dict(self._stats)


MAP = {1: "A1", 2: "A2", 3: "A3"}


def test_free_primary_variable_is_not_reported_unique():
    # A2, A3 hoàn toàn tự do → có 4 nghiệm. Bản cũ báo UNIQUE vì blocking clause chỉ có [-1].
    result = check_uniqueness([[1]], [1, 2, 3], MAP, PartialModelSolver())
    assert result.status is UniquenessStatus.NON_UNIQUE
    assert result.first_model is not None and result.second_model is not None
    assert result.first_model != result.second_model


def test_truly_unique_is_still_unique():
    result = check_uniqueness([[1], [-2], [3]], [1, 2, 3], MAP, PartialModelSolver())
    assert result.status is UniquenessStatus.UNIQUE
    assert result.first_model == {"A1": "CRIMINAL", "A2": "INNOCENT", "A3": "CRIMINAL"}


def test_unsat():
    result = check_uniqueness([[1], [-1]], [1, 2, 3], MAP, PartialModelSolver())
    assert result.status is UniquenessStatus.UNSAT


def test_blocking_clause_covers_all_primary_vars():
    clause = _build_blocking_clause({1: True}, [1, 2, 3])
    assert sorted(clause, key=abs) == [-1, 2, 3]


def test_decode_fills_missing_with_innocent():
    decoded = _decode_model({1: True}, [1, 2, 3], MAP)
    assert decoded == {"A1": "CRIMINAL", "A2": "INNOCENT", "A3": "INNOCENT"}


def test_aux_variables_are_ignored():
    # Biến 9 là aux, không nằm trong primary: không được xuất hiện trong blocking clause.
    clause = _build_blocking_clause({1: True, 2: False, 9: True}, [1, 2])
    assert sorted(clause, key=abs) == [-1, 2]