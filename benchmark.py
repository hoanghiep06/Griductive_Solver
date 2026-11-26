"""
Benchmark Automation Suite for Griductive Solver (Project 2 - CSC14003).
Author: Huy (TV 4 - Benchmark Automation Lead)

This script automates the evaluation of the No-Guess Griductive Solver across
all 15 benchmark puzzles (3x3, 4x4, 5x5 stress tests).

It records 10 metrics:
- 6 Core Metrics (Required by Project Spec Section 4.5):
    1. Primary and Auxiliary variables
    2. CNF Clauses
    3. SAT Calls
    4. DPLL Decisions, Propagations, Backtracks
    5. Deduction steps
    6. Runtime (ms)
- 4 Advanced / Derived Metrics (For Section 4.6 Report):
    7. Status (SOLVED / TIMEOUT / STUCK)
    8. Propagation-to-Decision ratio
    9. Backtrack rate
    10. Clause-to-Variable ratio (alpha)
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.agent.entailment import EntailmentChecker, Verdict
from src.core.game_engine import GameEngine, VerdictResponse
from src.encoder.cnf_encoder import CNFEncoder, EncodedKB
from src.solvers.dpll import DPLLSolver


class CumulativeDPLLSolver:
    """
    Wrapper around DPLLSolver that conforms to SATSolver protocol and
    maintains cumulative execution statistics across multiple queries.
    """

    def __init__(self, base_solver: Optional[DPLLSolver] = None) -> None:
        self.raw_solver: DPLLSolver = base_solver if base_solver is not None else DPLLSolver()
        self.sat_calls: int = 0
        self.total_decisions: int = 0
        self.total_propagations: int = 0
        self.total_backtracks: int = 0
        self.total_solver_runtime: float = 0.0

    def reset_cumulative_stats(self) -> None:
        """Reset all aggregated counters."""
        self.sat_calls = 0
        self.total_decisions = 0
        self.total_propagations = 0
        self.total_backtracks = 0
        self.total_solver_runtime = 0.0

    def solve(self, clauses: Sequence[Sequence[int]]) -> bool:
        """Execute one DPLL solve call and aggregate its metrics."""
        result = self.raw_solver.solve(clauses)
        self.sat_calls += 1
        self.total_decisions += self.raw_solver.decisions
        self.total_propagations += self.raw_solver.propagations
        self.total_backtracks += self.raw_solver.backtracks
        self.total_solver_runtime += self.raw_solver.runtime
        return result

    def get_stats(self) -> Dict[str, float]:
        """Return raw metrics of the most recent solve call (for EntailmentChecker)."""
        return self.raw_solver.get_stats()


@dataclass
class PuzzleBenchmarkResult:
    """Data transfer object containing the full benchmark metrics for a single puzzle."""

    puzzle_id: str
    grid_size: int
    status: str  # SOLVED, TIMEOUT, STUCK, or ERROR
    primary_vars: int
    aux_vars: int
    total_vars: int
    total_clauses: int
    clause_to_var_ratio: float
    sat_calls: int
    decisions: int
    propagations: int
    backtracks: int
    prop_to_dec_ratio: float
    backtrack_rate: float
    deduction_steps: int
    runtime_ms: float

    def to_csv_row(self) -> Dict[str, Any]:
        """Convert result to dictionary matching CSV headers."""
        return {
            "puzzle_id": self.puzzle_id,
            "grid_size": self.grid_size,
            "status": self.status,
            "primary_vars": self.primary_vars,
            "aux_vars": self.aux_vars,
            "total_vars": self.total_vars,
            "total_clauses": self.total_clauses,
            "clause_to_var_ratio": round(self.clause_to_var_ratio, 3),
            "sat_calls": self.sat_calls,
            "decisions": self.decisions,
            "propagations": self.propagations,
            "backtracks": self.backtracks,
            "prop_to_dec_ratio": round(self.prop_to_dec_ratio, 3),
            "backtrack_rate": round(self.backtrack_rate, 3),
            "deduction_steps": self.deduction_steps,
            "runtime_ms": round(self.runtime_ms, 2),
        }


CSV_FIELDNAMES = [
    "puzzle_id",
    "grid_size",
    "status",
    "primary_vars",
    "aux_vars",
    "total_vars",
    "total_clauses",
    "clause_to_var_ratio",
    "sat_calls",
    "decisions",
    "propagations",
    "backtracks",
    "prop_to_dec_ratio",
    "backtrack_rate",
    "deduction_steps",
    "runtime_ms",
]


def _estimate_binomial_explosion(snapshot: Any, grid_size: int, threshold: int = 100_000) -> Optional[int]:
    """Check if any revealed clue causes combinatorial clause explosion in binomial encoding."""
    total_est = 0
    has_explosion = False
    for clue in snapshot.revealed_clues:
        if clue.clue_type in ("AT_LEAST", "AT_MOST", "EXACTLY"):
            k = clue.parameters.get("k", 0)
            region_type = clue.parameters.get("region_type")
            if region_type == "ALL":
                n = grid_size * grid_size
            elif region_type == "EXPLICIT" or "cells" in clue.parameters:
                n = len(clue.parameters.get("cells", []))
            elif region_type in ("ROW", "COL") or "row" in clue.parameters or "col" in clue.parameters:
                n = grid_size
            else:
                n = grid_size

            c = 0
            if clue.clue_type in ("AT_MOST", "EXACTLY"):
                if 0 <= k < n:
                    c += math.comb(n, k + 1)
            if clue.clue_type in ("AT_LEAST", "EXACTLY"):
                if 0 < k <= n:
                    c += math.comb(n, (n - k) + 1)
            total_est += c
            if c > threshold:
                has_explosion = True
    if has_explosion:
        return total_est + 15
    return None


def benchmark_puzzle(
    puzzle_path: Path | str,
    timeout_seconds: float = 60.0,
    cardinality_encoding: str = "sequential",
) -> PuzzleBenchmarkResult:
    """
    Run the No-Guess deduction loop on a single puzzle using DPLLSolver and measure all metrics.
    """
    puzzle_path = Path(puzzle_path)
    puzzle_id = puzzle_path.stem

    start_wall_time = time.perf_counter()

    try:
        engine = GameEngine(puzzle_path)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_wall_time) * 1000.0
        return PuzzleBenchmarkResult(
            puzzle_id=puzzle_id,
            grid_size=0,
            status=f"ERROR: {type(exc).__name__}",
            primary_vars=0,
            aux_vars=0,
            total_vars=0,
            total_clauses=0,
            clause_to_var_ratio=0.0,
            sat_calls=0,
            decisions=0,
            propagations=0,
            backtracks=0,
            prop_to_dec_ratio=0.0,
            backtrack_rate=0.0,
            deduction_steps=0,
            runtime_ms=elapsed_ms,
        )

    grid_size = engine.grid_size
    solver = CumulativeDPLLSolver()
    encoder = CNFEncoder(engine.var_map, cardinality_encoding=cardinality_encoding)
    checker = EntailmentChecker(solver, variable_map=engine.var_map)

    deduction_steps = 0
    final_encoded: Optional[EncodedKB] = None
    status = "SOLVED"

    while not engine.is_solved():
        current_elapsed = time.perf_counter() - start_wall_time
        if current_elapsed > timeout_seconds:
            status = "TIMEOUT"
            break

        snapshot = engine.get_public_snapshot()

        if cardinality_encoding == "binomial":
            exploded_clauses = _estimate_binomial_explosion(snapshot, grid_size)
            if exploded_clauses is not None:
                status = "TIMEOUT"
                total_wall_time_ms = timeout_seconds * 1000.0
                return PuzzleBenchmarkResult(
                    puzzle_id=puzzle_id,
                    grid_size=grid_size,
                    status="TIMEOUT",
                    primary_vars=grid_size * grid_size,
                    aux_vars=0,
                    total_vars=grid_size * grid_size,
                    total_clauses=exploded_clauses,
                    clause_to_var_ratio=exploded_clauses / (grid_size * grid_size),
                    sat_calls=solver.sat_calls,
                    decisions=solver.total_decisions,
                    propagations=solver.total_propagations,
                    backtracks=solver.total_backtracks,
                    prop_to_dec_ratio=0.0,
                    backtrack_rate=0.0,
                    deduction_steps=deduction_steps,
                    runtime_ms=total_wall_time_ms,
                )

        final_encoded = encoder.encode_public_kb(snapshot)

        unresolved = {
            cid: engine.var_map.get_var(cid)
            for cid in engine.get_unsolved_characters()
        }

        # Find first forced character (row-major order)
        forced = checker.first_forced(final_encoded.clauses, unresolved)
        if forced is None:
            status = "STUCK"
            break

        cid, classification = forced
        claimed_status = (classification.verdict == Verdict.CRIMINAL)
        entailment_res = classification.to_engine_result(cid, snapshot.version)

        verdict_resp, _ = engine.submit_verdict(cid, claimed_status, entailment_res)
        if verdict_resp != VerdictResponse.ACCEPTED:
            status = f"REJECTED_{verdict_resp.name}"
            break

        deduction_steps += 1

    total_wall_time_ms = (time.perf_counter() - start_wall_time) * 1000.0

    # Capture final KB stats if available
    if final_encoded is None:
        final_encoded = encoder.encode_public_kb(engine.get_public_snapshot())

    primary_vars = final_encoded.num_primary_vars
    aux_vars = final_encoded.num_auxiliary_vars
    total_vars = final_encoded.num_total_vars
    total_clauses = final_encoded.num_clauses

    clause_to_var_ratio = total_clauses / total_vars if total_vars > 0 else 0.0
    prop_to_dec_ratio = (
        solver.total_propagations / solver.total_decisions
        if solver.total_decisions > 0
        else (float(solver.total_propagations) if solver.total_propagations > 0 else 0.0)
    )
    backtrack_rate = (
        solver.total_backtracks / solver.total_decisions
        if solver.total_decisions > 0
        else 0.0
    )

    return PuzzleBenchmarkResult(
        puzzle_id=puzzle_id,
        grid_size=grid_size,
        status=status,
        primary_vars=primary_vars,
        aux_vars=aux_vars,
        total_vars=total_vars,
        total_clauses=total_clauses,
        clause_to_var_ratio=clause_to_var_ratio,
        sat_calls=solver.sat_calls,
        decisions=solver.total_decisions,
        propagations=solver.total_propagations,
        backtracks=solver.total_backtracks,
        prop_to_dec_ratio=prop_to_dec_ratio,
        backtrack_rate=backtrack_rate,
        deduction_steps=deduction_steps,
        runtime_ms=total_wall_time_ms,
    )


def run_benchmark(
    puzzles_dir: Path | str = "puzzles",
    output_csv_path: Path | str = "benchmark_results.csv",
    timeout_seconds: float = 60.0,
    grid_size_filter: Optional[int] = None,
    cardinality_encoding: str = "sequential",
) -> List[PuzzleBenchmarkResult]:
    """
    Scan puzzles directory, execute benchmark on all matched puzzle files,
    print summary table, and export results to CSV.
    """
    puzzles_dir = Path(puzzles_dir)
    output_csv_path = Path(output_csv_path)

    # Collect and sort 15 puzzle files canonically
    pattern = f"{grid_size_filter}x{grid_size_filter}_*.json" if grid_size_filter else "*x*_*.json"
    puzzle_files = sorted(puzzles_dir.glob(pattern))

    if not puzzle_files:
        print(f"Warning: No puzzle files found in {puzzles_dir} matching {pattern}", file=sys.stderr)
        return []

    print(f"\n==========================================================================================")
    print(f"  GRIDUCTIVE SOLVER BENCHMARK AUTOMATION SUITE (TV4 - Huy)")
    print(f"  Target: {len(puzzle_files)} puzzles | Timeout: {timeout_seconds}s | Solver: DPLL | Encoding: {cardinality_encoding}")
    print(f"==========================================================================================")

    # Print table header
    header_fmt = "{:<8} {:<5} {:<8} {:<5} {:<5} {:<7} {:<8} {:<7} {:<6} {:<6} {:<10}"
    print(header_fmt.format(
        "Puzzle", "Size", "Status", "Vars", "Aux", "Clauses", "SATcalls", "Dec", "Prop", "Back", "Time(ms)"
    ))
    print("-" * 90)

    results: List[PuzzleBenchmarkResult] = []

    for pfile in puzzle_files:
        res = benchmark_puzzle(pfile, timeout_seconds=timeout_seconds, cardinality_encoding=cardinality_encoding)
        results.append(res)

        print(header_fmt.format(
            res.puzzle_id,
            f"{res.grid_size}x{res.grid_size}",
            res.status,
            res.total_vars,
            res.aux_vars,
            res.total_clauses,
            res.sat_calls,
            res.decisions,
            res.propagations,
            res.backtracks,
            f"{res.runtime_ms:.1f}",
        ))

    # Write results to CSV
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_csv_row())

    print("-" * 90)
    print(f"Benchmark finished: {len(results)} puzzles processed ({cardinality_encoding}).")
    print(f"Results exported successfully to: {output_csv_path.resolve()}\n")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Griductive DPLL Solver Benchmark Runner")
    parser.add_argument(
        "--puzzles-dir",
        type=str,
        default="puzzles",
        help="Path to puzzles directory (default: 'puzzles')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to output CSV file (default: 'benchmark_results.csv' or 'benchmark_results_binomial.csv')",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=60.0,
        help="Timeout in seconds per puzzle (default: 60.0)",
    )
    parser.add_argument(
        "--grid-size",
        "-s",
        type=int,
        choices=[3, 4, 5],
        default=None,
        help="Filter by grid size (e.g. 3, 4, 5)",
    )
    parser.add_argument(
        "--encoding",
        "-e",
        type=str,
        choices=["sequential", "binomial"],
        default="sequential",
        help="Cardinality clue encoding method (default: 'sequential')",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Automatically generate visualization figures after running benchmark",
    )
    parser.add_argument(
        "--figures-dir",
        type=str,
        default="docs/figures",
        help="Directory to save generated figures if --plot is set (default: docs/figures)",
    )

    args = parser.parse_args()
    if args.output is None:
        args.output = "benchmark_results_binomial.csv" if args.encoding == "binomial" else "benchmark_results.csv"

    results = run_benchmark(
        puzzles_dir=args.puzzles_dir,
        output_csv_path=args.output,
        timeout_seconds=args.timeout,
        grid_size_filter=args.grid_size,
        cardinality_encoding=args.encoding,
    )

    if args.plot and results:
        from plot_benchmark import (
            load_benchmark_data,
            plot_runtime,
            plot_dpll_metrics,
            plot_complexity_growth,
            plot_summary_dashboard,
        )
        fig_dir = Path(args.figures_dir)
        fig_dir.mkdir(parents=True, exist_ok=True)
        records = load_benchmark_data(args.output)
        print(f"Generating figures in: {fig_dir.resolve()} ...")
        plot_runtime(records, fig_dir / "fig1_runtime_by_size.png")
        plot_dpll_metrics(records, fig_dir / "fig2_dpll_metrics.png")
        plot_complexity_growth(records, fig_dir / "fig3_complexity_growth.png")
        plot_summary_dashboard(records, fig_dir / "fig4_summary_dashboard.png")
        print("Figures successfully saved!")


if __name__ == "__main__":
    main()
