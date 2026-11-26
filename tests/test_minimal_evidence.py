"""Test tập chứng cứ tối tiểu (evidence.py) và build_step với chứng cứ tối tiểu."""

from itertools import product

from src.agent.deduction_trace import DeductionTrace, build_step
from src.agent.evidence import minimize_support


class BruteForceSolver:
    def __init__(self):
        self.calls = 0

    def solve(self, cnf):
        self.calls += 1
        variables = sorted({abs(lit) for clause in cnf for lit in clause})
        for values in product([False, True], repeat=len(variables)):
            model = dict(zip(variables, values))
            if all(any(model[abs(l)] == (l > 0) for l in clause) for clause in cnf):
                return True
        return False


def _ids(groups):
    return [key for _, key, _ in groups]


def test_drops_irrelevant_clues():
    # Muốn chứng minh x1 = True (¬C là -1).
    # c1: x1 ∨ x2 ; c2: ¬x2 ; c3, c4: không liên quan.
    groups = [
        ("clue", "c1", [[1, 2]]),
        ("clue", "c2", [[-2]]),
        ("clue", "c3", [[3, 4]]),
        ("clue", "c4", [[-4, 5]]),
    ]
    support = minimize_support(groups, opposite_literal=-1, solver=BruteForceSolver())
    assert _ids(support) == ["c1", "c2"]


def test_keeps_proved_cells_that_are_needed():
    # ô A2 đã chứng minh INNOCENT (x2 = False) là bắt buộc cùng c1.
    groups = [
        ("clue", "c1", [[1, 2]]),
        ("cell", "A2", [[-2]]),
        ("cell", "A3", [[3]]),
    ]
    support = minimize_support(groups, opposite_literal=-1, solver=BruteForceSolver())
    assert [(k, i) for k, i, _ in support] == [("clue", "c1"), ("cell", "A2")]


def test_result_is_subset_minimal():
    groups = [
        ("clue", "c1", [[1, 2]]),
        ("clue", "c2", [[-2]]),
        ("clue", "c3", [[1, 3]]),   # dư thừa: c1 + c2 đã đủ
        ("clue", "c4", [[-3, 6]]),
    ]
    solver = BruteForceSolver()
    support = minimize_support(groups, opposite_literal=-1, solver=solver)

    def unsat(gs):
        clauses = [c for _, _, cs in gs for c in cs] + [[-1]]
        return not solver.solve(clauses)

    assert unsat(support)
    for g in support:  # bỏ bất kỳ nhóm nào cũng không còn mâu thuẫn
        assert not unsat([x for x in support if x is not g])


def test_on_solve_called_once_per_group():
    groups = [("clue", "c1", [[1]]), ("clue", "c2", [[2]])]
    calls = []
    minimize_support(groups, -1, BruteForceSolver(), on_solve=lambda: calls.append(1))
    assert len(calls) == len(groups)


def test_build_step_uses_minimal_evidence():
    step = build_step(
        step_index=1,
        character_id="A1",
        verdict="CRIMINAL",
        kb_version=3,
        revealed_clues=[{"clue_id": "c1"}, {"clue_id": "c2"}, {"clue_id": "c3"}],
        sat_metrics_list=[{"decisions": 2}, {}],
        evidence_clue_ids=["c1", "c2"],
        support_cell_ids=["B2"],
    )
    assert step.clue_ids == ("c1", "c2")
    assert step.support_cell_ids == ("B2",)
    assert step.minimal_evidence is True
    assert "c3" not in step.explanation
    assert "B2" in step.explanation
    assert step.metrics.sat_calls == 2
    assert step.to_dict()["minimal_evidence"] is True


def test_build_step_fallback_uses_all_clues():
    step = build_step(
        step_index=1,
        character_id="A1",
        verdict="INNOCENT",
        kb_version=0,
        revealed_clues=[{"clue_id": "c1"}, {"clue_id": "c2"}],
        sat_metrics_list=[{}],
    )
    assert step.clue_ids == ("c1", "c2")
    assert step.minimal_evidence is False
    assert step.support_cell_ids == ()


def test_trace_roundtrip_to_json():
    trace = DeductionTrace(puzzle_id="p", grid_size=3)
    trace.record(build_step(
        step_index=1, character_id="A1", verdict="CRIMINAL", kb_version=0,
        revealed_clues=[], sat_metrics_list=[{}], evidence_clue_ids=[], support_cell_ids=[],
    ))
    data = trace.to_dict()
    assert data["steps"][0]["support_cell_ids"] == []
    assert data["steps"][0]["minimal_evidence"] is True
    assert "không cần manh mối nào" in data["steps"][0]["explanation"]