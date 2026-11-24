"""Exercise the actual production encoder/DPLL on an authored puzzle."""

from src.agent.entailment import EntailmentChecker, Verdict
from src.agent.uniqueness import check_uniqueness_from_var_map
from src.core.variable_map import VariableMap
from src.encoder.cnf_encoder import CNFEncoder
from src.solvers.dpll import DPLLSolver
from copy import deepcopy
from functools import lru_cache
import json


def certify_runtime(puzzle):
    # Repeated reports/tests may certify the same bytes many times. The cache
    # key covers every clue, public identity, initial reveal AND private key;
    # changing any puzzle content requires a fresh production replay.
    payload = json.dumps({
        "schema_version": puzzle.schema_version, "puzzle_id": puzzle.puzzle_id, "grid_size": puzzle.grid_size,
        "characters": [c.to_dict() for c in puzzle.characters], "hidden_solution": dict(puzzle.hidden_solution),
        "initial_revealed": list(puzzle.initial_revealed), "clues": [c.to_dict() for c in puzzle.clues],
    }, sort_keys=True)
    return deepcopy(_certify_payload(payload))


@lru_cache(maxsize=64)
def _certify_payload(payload):
    from src.core.puzzle_validator import PuzzleValidator
    puzzle = PuzzleValidator().validate(json.loads(payload))
    vm = VariableMap()
    vm.register_characters(puzzle.characters)
    vm.freeze_primary_variables()
    encoder = CNFEncoder(vm)
    solver = DPLLSolver()
    full = encoder.encode_kb(puzzle.clues, reset_aux=True).clauses
    unique = check_uniqueness_from_var_map(full, vm, solver)
    if not unique.is_unique:
        raise ValueError("Production DPLL: full puzzle must have exactly one primary solution")
    known = {cid: puzzle.hidden_solution[cid] for cid in puzzle.initial_revealed}
    ordered = [c.id for c in sorted(puzzle.characters, key=lambda c: (c.row, c.col))]
    trace = []
    checker = EntailmentChecker(solver, variable_map=vm)
    while len(known) < len(ordered):
        active = [puzzle.clues_by_owner[cid] for cid in known]
        cnf = encoder.encode_kb(active, known, reset_aux=True).clauses
        forced = checker.first_forced(cnf, {cid: vm.get_var(cid) for cid in ordered if cid not in known})
        if forced is None:
            raise ValueError("Production DPLL: STUCK before all cards are proved")
        cid, result = forced
        status = result.verdict is Verdict.CRIMINAL
        if status is not puzzle.hidden_solution[cid]:
            raise ValueError("Production proof differs from authored solution")
        known[cid] = status
        trace.append({"character_id": cid, "status": status})
    return {"status": "PASSED", "unique": True, "public_no_guess": True, "reveal_order": trace}
