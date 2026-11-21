"""Test analyze_public_kb (đường suy luận dùng chung) bằng encoder/checker giả."""

from itertools import product
from types import SimpleNamespace

from src.agent.entailment import Verdict
from src.agent.forced_move import analyze_public_kb


def _sat(cnf):
    variables = sorted({abs(lit) for clause in cnf for lit in clause})
    for values in product([False, True], repeat=len(variables)):
        model = dict(zip(variables, values))
        if all(any(model[abs(l)] == (l > 0) for l in clause) for clause in cnf):
            return True
    return False


class FakeSolver:
    def solve(self, cnf):
        return _sat(cnf)

    def get_stats(self):
        return {"decisions": 1}


class FakeVarMap:
    VARS = {"A1": 1, "A2": 2, "A3": 3}

    def get_var(self, cid):
        return self.VARS[cid]


class FakeEncoder:
    def __init__(self):
        self.var_map = FakeVarMap()

    def encode_clue(self, clue):
        return clue.clauses

    def encode_verdict(self, cid, value):
        var = self.var_map.get_var(cid)
        return [var if value else -var]


class FakeChecker:
    def classify(self, clauses, var):
        if not _sat(clauses):
            verdict = Verdict.INCONSISTENT
        elif not _sat(clauses + [[-var]]):
            verdict = Verdict.CRIMINAL
        elif not _sat(clauses + [[var]]):
            verdict = Verdict.INNOCENT
        else:
            verdict = Verdict.UNKNOWN
        return SimpleNamespace(verdict=verdict, queries=[], sat_calls=2)


def clue(cid, *clauses):
    return SimpleNamespace(clue_id=cid, clauses=[list(c) for c in clauses])


def snapshot(clues, proved=None, version=7):
    return SimpleNamespace(version=version, revealed_clues=clues, proved_verdicts=proved or {})


def run(snap, unsolved, target=None, solver=None):
    return analyze_public_kb(
        snap, unsolved, FakeEncoder(), FakeChecker(),
        solver=solver if solver is not None else FakeSolver(), target=target,
    )


def test_first_forced_in_row_major_order_with_minimal_evidence():
    # c1: x1 ∨ x2 ; c2: ¬x2 ; c3 (x3 = False khi x2 = False): -3 ∨ 2 ; c4 không liên quan
    snap = snapshot([clue("c1", [1, 2]), clue("c2", [-2]), clue("c3", [-3, 2]), clue("c4", [4, 5])])
    result = run(snap, ["A1", "A2", "A3"])
    assert result.is_forced and result.is_criminal
    assert result.cell_id == "A1"          # ô đầu tiên theo thứ tự truyền vào
    assert result.version == 7
    assert result.clue_ids == ("c1", "c2")  # c3, c4 không cần
    assert result.minimal_evidence is True
    assert len(result.extra_metrics) >= 1


def test_skips_unknown_cells_and_keeps_proved_cell_when_needed():
    # A1 đã là CRIMINAL; c1: ¬x1 ∨ ¬x2 → A2 INNOCENT chỉ nhờ ô A1 và c1
    snap = snapshot([clue("c1", [-1, -2]), clue("c9", [4, 5])], proved={"A1": True})
    result = run(snap, ["A2", "A3"])
    assert result.cell_id == "A2"
    assert result.is_forced and not result.is_criminal
    assert result.clue_ids == ("c1",)
    assert result.support_cell_ids == ("A1",)


def test_no_forced_cell():
    snap = snapshot([clue("c4", [4, 5])])
    result = run(snap, ["A1", "A2", "A3"])
    assert result.cell_id is None and result.classification is None
    assert not result.is_forced and not result.inconsistent


def test_target_mode_unknown_returns_that_cell_without_evidence():
    snap = snapshot([clue("c4", [4, 5])])
    result = run(snap, ["A1", "A2", "A3"], target="A2")
    assert result.cell_id == "A2"
    assert result.classification.verdict is Verdict.UNKNOWN
    assert not result.is_forced and result.clue_ids == ()


def test_target_mode_forced():
    snap = snapshot([clue("c1", [1])])
    result = run(snap, ["A1", "A2", "A3"], target="A1")
    assert result.is_forced and result.is_criminal and result.clue_ids == ("c1",)


def test_inconsistent_kb():
    snap = snapshot([clue("c1", [1]), clue("c2", [-1])])
    result = run(snap, ["A1", "A2", "A3"])
    assert result.inconsistent and not result.is_forced
    assert result.cell_id == "A1"


def test_without_solver_falls_back_to_whole_kb():
    snap = snapshot([clue("c1", [1, 2]), clue("c2", [-2]), clue("c4", [4, 5])])
    result = analyze_public_kb(snap, ["A1"], FakeEncoder(), FakeChecker(), solver=None)
    assert result.is_forced
    assert result.minimal_evidence is False
    assert result.clue_ids == ("c1", "c2", "c4")
    assert result.extra_metrics == ()


def test_solver_failure_falls_back_instead_of_breaking_reasoning():
    class BrokenSolver:
        def solve(self, cnf):
            raise RuntimeError("boom")

    snap = snapshot([clue("c1", [1])])
    result = analyze_public_kb(snap, ["A1"], FakeEncoder(), FakeChecker(), solver=BrokenSolver())
    assert result.is_forced and result.minimal_evidence is False
    assert result.clue_ids == ("c1",)