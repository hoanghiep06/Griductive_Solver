"""Validate all maps with reference certificates and the production pipeline."""
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.entailment import EntailmentChecker, Verdict
from src.core.game_engine import GameEngine, VerdictResponse
from src.core.puzzle_loader import PuzzleLoader
from src.encoder import CNFEncoder
from src.solvers.dpll import DPLLSolver
from tools.validate_puzzles import ROOT, validate_dataset


def main():
    reports = validate_dataset(ROOT / "puzzles")
    results = []
    for report in reports:
        pid = report["puzzle_id"]
        path = ROOT / "puzzles" / f"{pid}.json"
        engine = GameEngine(path)
        encoder = CNFEncoder(engine.var_map)
        solver = DPLLSolver()
        checker = EntailmentChecker(solver, variable_map=engine.var_map)
        metrics = dict.fromkeys(("decisions", "propagations", "backtracks", "runtime"), 0)
        reveals = 0
        while not engine.is_solved():
            snapshot = engine.get_public_snapshot()
            cnf = encoder.encode_public_kb(snapshot).clauses
            batch = checker.classify_all(cnf, {
                cid: engine.var_map.get_var(cid) for cid in engine.get_unsolved_characters()
            })
            for key, value in batch.metrics.items():
                metrics[key] += value
            forced = next(((cid, result) for cid, result in batch.results.items()
                           if result.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT)), None)
            if forced is None:
                raise ValueError(f"{pid}: production pipeline stuck or inconsistent")
            cid, result = forced
            response, _ = engine.submit_verdict(
                cid, result.verdict is Verdict.CRIMINAL,
                result.to_engine_result(cid, snapshot.version))
            if response is not VerdictResponse.ACCEPTED:
                raise ValueError(f"{pid}: rejected deduction: {response}")
            reveals += 1
        puzzle = PuzzleLoader().load(path)
        cnf = encoder.encode_kb(list(puzzle.clues), reset_aux=True).clauses
        key = [engine.var_map.to_literal(cid, value) for cid, value in puzzle.hidden_solution.items()]
        if not solver.solve(cnf + [[lit] for lit in key]) or solver.solve(cnf + [[-lit for lit in key]]):
            raise ValueError(f"{pid}: production uniqueness check failed")
        results.append({"puzzle_id": pid, "reveals": reveals, "metrics": metrics,
                        "reference_validation": True, "production_unique": True})
        print(f"{pid}: PASSED (reference + CNFEncoder/DPLL, {reveals} public reveals, unique)", flush=True)
    destination = ROOT / "docs/stage1_validation.json"
    destination.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
