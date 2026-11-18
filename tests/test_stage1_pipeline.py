"""Cross-check production bindings against independent direct semantics."""
import importlib
import itertools
import json
from pathlib import Path

import pytest

from src.agent.entailment import EntailmentChecker, Verdict
from src.core.clue import Clue
from src.core.game_engine import GameEngine
from src.core.puzzle_validator import PuzzleValidator, PuzzleValidationError
from src.core.variable_map import VariableMap
from src.encoder import CNFEncoder, VariableMap as EncoderVariableMap
from src.encoder.semantic_eval import evaluate_clue
from src.solvers.dpll import DPLLSolver

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("kind,params", [
    ("FACT", {"target": "A1", "status": "INNOCENT"}),
    ("SAME", {"target1": "A1", "target2": "B1"}),
    ("DIFFERENT", {"target1": "A1", "target2": "B1"}),
    ("EXACTLY", {"region_type": "ROW", "index": 0, "k": 1}),
    ("AT_LEAST", {"region_type": "COLUMN", "index": 1, "k": 2}),
    ("AT_MOST", {"region_type": "NEIGHBORS", "center": "B2", "k": 3}),
    *[(kind, {"region_type": "EXPLICIT", "cells": [], "k": 0})
      for kind in ("EXACTLY", "AT_LEAST", "AT_MOST")],
    ("PARITY", {"cells": ["A1", "B1", "C1"], "parity": "odd"}),
    *[("COUNT_COMPARE", {"region_a": ["A1", "B1"],
                         "region_b": ["B1", "C1", "C2"], "op": op})
      for op in ("<", "<=", "==", "!=", ">=", ">")],
])
def test_canonical_clues_match_direct_semantics_for_all_boards(kind, params):
    assert EncoderVariableMap is VariableMap
    vm = VariableMap.from_puzzle({"size": 3})
    clue = Clue("CHECK", "A1", kind, params)
    cnf = CNFEncoder(vm).encode_clue(clue)
    solver = DPLLSolver()
    for bits in itertools.product((False, True), repeat=9):
        board = [bits[i:i+3] for i in (0, 3, 6)]
        fixed = [[v if value else -v] for v, value in zip(vm.primary_ids, bits)]
        assert solver.solve(cnf + fixed) == evaluate_clue(clue, board)


def test_public_snapshot_and_query_metrics_are_preserved():
    engine = GameEngine(ROOT / "puzzles/sample_3x3.json")
    snapshot = engine.get_public_snapshot()
    cnf = CNFEncoder(engine.var_map).encode_public_kb(snapshot).clauses
    solver = DPLLSolver()
    checker = EntailmentChecker(solver, variable_map=engine.var_map)
    batch = checker.classify_all(cnf, {
        cid: engine.var_map.get_var(cid) for cid in engine.get_unsolved_characters()
    })
    assert Verdict.UNKNOWN in batch.verdicts.values()
    assert any(v in (Verdict.CRIMINAL, Verdict.INNOCENT) for v in batch.verdicts.values())
    for key in ("decisions", "propagations", "backtracks", "runtime"):
        assert batch.metrics[key] == sum(q.metrics[key] for q in batch.queries)
        assert all(q.metrics[key] >= 0 for q in batch.queries)
    saved = dict(batch.queries[0].metrics)
    solver.solve([[1]])
    assert dict(batch.queries[0].metrics) == saved
    with pytest.raises(TypeError):
        batch.queries[0].metrics["decisions"] = 999


@pytest.mark.parametrize("kind", ["PARITY", "COUNT_COMPARE"])
def test_extensions_load_from_json_and_encode_public_snapshot(kind, tmp_path):
    raw = json.loads((ROOT / "puzzles/sample_3x3.json").read_text(encoding="utf-8"))
    owner = raw["initial_revealed"][0]
    value = raw["hidden_solution"][owner]
    params = ({"cells": [owner], "parity": "odd" if value else "even"}
              if kind == "PARITY" else
              {"region_a": [owner], "region_b": [owner], "op": "=="})
    clue = next(c for c in raw["clues"] if c["owner_id"] == owner)
    clue.update(type=kind, parameters=params)
    path = tmp_path / "extended.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    engine = GameEngine(path)
    snapshot = engine.get_public_snapshot()
    assert any(c.clue_type == kind for c in snapshot.revealed_clues)
    assert DPLLSolver().solve(CNFEncoder(engine.var_map).encode_public_kb(snapshot).clauses)
    field = "cells" if kind == "PARITY" else "region_a"
    clue["parameters"][field] = [[99, 99]]
    with pytest.raises(PuzzleValidationError):
        PuzzleValidator().validate(raw)


def test_stage2_placeholders_remain_importable():
    for name in ("src.agent.logic_agent", "src.agent.deduction_trace",
                 "src.agent.uniqueness", "src.gui.app_window", "src.gui.grid_view",
                 "src.gui.clue_highlighter", "main", "benchmark"):
        importlib.import_module(name)


def test_auxiliary_reset_keeps_core_primary_ids_frozen():
    vm = VariableMap.from_puzzle({"size": 3})
    before = dict(vm.primary_mapping)
    aux = vm.allocate_aux("counter")
    assert aux == 10 and vm.get_char_id(aux) is None
    vm.reset_auxiliary()
    assert dict(vm.primary_mapping) == before
    assert vm.is_frozen and vm.total_variables == 9
    with pytest.raises(RuntimeError):
        vm.register_character("D1")
    assert vm.allocate_auxiliary_variable({"tag": "next"}) == 10
