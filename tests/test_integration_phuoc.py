"""Core smoke tests and production DPLL/encoder integration for all 15 maps."""

import pytest

from src.agent.entailment import EntailmentChecker, Verdict
from src.core.game_engine import GameEngine, VerdictResponse
from src.core.puzzle_loader import PuzzleLoader
from tests.test_entailment import ExhaustiveTestSolver
from tools.validate_puzzles import PUZZLE_IDS, ROOT


@pytest.mark.parametrize("pid", PUZZLE_IDS)
def test_real_core_loads_dataset_and_exposes_only_public_initial_state(pid):
    engine = GameEngine(ROOT / "puzzles" / f"{pid}.json")
    snapshot = engine.get_public_snapshot()
    state = engine.get_public_state()
    assert "hidden_solution" not in state and "clues" not in state
    assert {c.owner_id for c in snapshot.revealed_clues} == set(snapshot.proved_verdicts)
    assert len(engine.get_unsolved_characters()) == engine.grid_size**2 - len(snapshot.proved_verdicts)
    for cid in engine.get_unsolved_characters():
        assert engine.get_clue_for_character(cid) is None
    engine.restart()
    assert engine.get_public_snapshot().version > snapshot.version
    assert dict(engine.get_public_snapshot().proved_verdicts) == dict(snapshot.proved_verdicts)


def test_real_core_accepts_bridge_from_public_fact_with_test_solver():
    """Partial integration only: one FACT encoded by the test, no real DPLL."""
    engine = GameEngine(ROOT / "puzzles/sample_3x3.json")
    snapshot = engine.get_public_snapshot()
    fact = snapshot.revealed_clues[0]
    assert fact.clue_type == "FACT"
    cid = fact.parameters["target"]
    literal = engine.var_map.to_literal(cid, fact.parameters["status"] == "CRIMINAL")
    cnf = snapshot.get_unit_clauses_for_verdicts() + [[literal]]
    checker = EntailmentChecker(ExhaustiveTestSolver(), variable_map=engine.var_map)
    result = checker.classify(cnf, engine.var_map.get_var(cid))
    proof = result.to_engine_result(cid, snapshot.version)
    response, clue = engine.submit_verdict(cid, result.verdict is Verdict.CRIMINAL, proof)
    assert response is VerdictResponse.ACCEPTED
    assert clue["owner_id"] == cid
    assert engine.get_public_snapshot().version == snapshot.version + 1
    # A different still-unsolved target with old public version is rejected.
    stale = result.to_engine_result(engine.get_unsolved_characters()[0], snapshot.version)
    assert engine.submit_verdict(stale.character_id, True, stale)[0] is VerdictResponse.STALE_PROOF


def test_real_core_rejects_unproved_and_contradicted_bridge_with_test_solver():
    engine = GameEngine(ROOT / "puzzles/sample_3x3.json")
    snapshot = engine.get_public_snapshot()
    fact = snapshot.revealed_clues[0]
    forced_id = fact.parameters["target"]
    cnf = snapshot.get_unit_clauses_for_verdicts() + [[engine.var_map.to_literal(
        forced_id, fact.parameters["status"] == "CRIMINAL")]]
    checker = EntailmentChecker(ExhaustiveTestSolver(), variable_map=engine.var_map)
    unknown = checker.classify(cnf, engine.var_map.get_var("C1"))
    assert unknown.verdict is Verdict.UNKNOWN
    before = engine.get_public_state()
    for claim in (True, False):
        response, clue = engine.submit_verdict("C1", claim, unknown.to_engine_result("C1", snapshot.version))
        assert response is VerdictResponse.NOT_PROVABLE and clue is None
        assert engine.get_public_state() == before
    forced = checker.classify(cnf, engine.var_map.get_var(forced_id))
    opposite = forced.verdict is not Verdict.CRIMINAL
    response, clue = engine.submit_verdict(forced_id, opposite, forced.to_engine_result(forced_id, snapshot.version))
    assert response is VerdictResponse.CONTRADICTED and clue is None
    assert engine.get_public_state() == before


@pytest.fixture
def team_bindings():
    from src.solvers import dpll
    from src.encoder import cnf_encoder
    return dpll.DPLLSolver(), cnf_encoder.CNFEncoder


def encode_clues(encoder, clues, variable_map):
    return encoder(variable_map).encode_kb(list(clues), reset_aux=True).clauses


@pytest.mark.parametrize("pid", PUZZLE_IDS)
def test_real_dpll_encoder_progressive_and_deterministic(pid, team_bindings):
    solver, encoder = team_bindings
    engine = GameEngine(ROOT / "puzzles" / f"{pid}.json")
    checker = EntailmentChecker(solver, variable_map=engine.var_map)
    traces = []
    for run in range(2):
        if run:
            engine.restart()
        trace = []
        while not engine.is_solved():
            snapshot = engine.get_public_snapshot()
            cnf = encode_clues(encoder, snapshot.revealed_clues, engine.var_map)
            cnf += snapshot.get_unit_clauses_for_verdicts()
            unresolved = {cid: engine.var_map.get_var(cid) for cid in engine.get_unsolved_characters()}
            batch = checker.classify_all(cnf, unresolved)
            assert batch.sat_calls == 1 + 2 * len(unresolved)
            forced = [(cid, r) for cid, r in batch.results.items()
                      if r.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT)]
            assert forced, "Public deduction became stuck or inconsistent"
            cid, result = forced[0]
            assert engine.get_clue_for_character(cid) is None
            before = snapshot.version
            response, clue = engine.submit_verdict(
                cid, result.verdict is Verdict.CRIMINAL, result.to_engine_result(cid, before))
            assert response is VerdictResponse.ACCEPTED
            assert clue["owner_id"] == cid
            assert engine.get_public_snapshot().version == before + 1
            trace.append((cid, result.verdict.value, tuple(c.clue_id for c in snapshot.revealed_clues)))
        traces.append(trace)
    assert traces[0] == traces[1]


@pytest.mark.parametrize("pid", PUZZLE_IDS)
def test_real_dpll_encoder_uniqueness_blocks_only_primary_variables(pid, team_bindings):
    solver, encoder = team_bindings
    path = ROOT / "puzzles" / f"{pid}.json"
    puzzle = PuzzleLoader().load(path)  # Authoring-only full-clue check.
    engine = GameEngine(path)
    cnf = encode_clues(encoder, puzzle.clues, engine.var_map)
    key_units = [[engine.var_map.to_literal(cid, value)] for cid, value in puzzle.hidden_solution.items()]
    assert solver.solve(cnf + key_units) is True
    block = [-unit[0] for unit in key_units]
    assert len(block) == engine.var_map.primary_count
    assert all(engine.var_map.get_char_id(abs(lit)) is not None for lit in block)
    assert solver.solve(cnf + [block]) is False
