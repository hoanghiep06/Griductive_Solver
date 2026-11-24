"""V2 authoring validation using an explicit reference SAT backend.

Local semantic inference remains available for regression/diagnostics. Final
certificates use exact SAT entailment and minimum clue support. This module
does not replace the team's production encoder or handwritten DPLL.
"""

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import product
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jsonschema import Draft202012Validator, ValidationError

from src.agent.entailment import row_major_key
from src.core.character import Character
from src.core.clue import Clue
from src.core.puzzle import Puzzle
from src.core.puzzle_validator import PuzzleValidator

ROOT = Path(__file__).resolve().parents[1]
PUZZLE_IDS = tuple(f"{n}x{n}_{case:02d}" for n in (3, 4, 5) for case in range(1, 6))
SCHEMA = json.loads((ROOT / "schemas/puzzle.schema.json").read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA)


class PuzzleProofError(ValueError):
    """The constructive proof failed; this is not a general UNSAT verdict."""


def clue_scope(clue: Clue, characters: Mapping[str, Character], size: int) -> tuple[str, ...]:
    """Resolve a clue's entire public scope, including both comparative sides."""
    p = clue.parameters
    if clue.clue_type == "FACT":
        cells = [p["target"]]
    elif clue.clue_type in {"SAME", "DIFFERENT"}:
        cells = [p["target1"], p["target2"]]
    elif clue.clue_type == "IMPLIES":
        cells = [p["antecedent"]["target"], p["consequent"]["target"]]
    elif clue.clue_type in {"PARITY", "COUNT_COMPARE"}:
        from src.encoder.semantic_eval import normalize_cells
        region = p["cells"] if clue.clue_type == "PARITY" else (*p["region_a"], *p["region_b"])
        by_coord = {(c.row, c.col): c.id for c in characters.values()}
        cells = [by_coord[coord] for coord in normalize_cells(region)]
    elif p["region_type"] == "ALL":
        cells = list(characters)
    elif p["region_type"] == "PROFESSION":
        cells = list(p["cells"])
    elif p["region_type"] == "ROW":
        cells = [c.id for c in characters.values() if c.row == p["index"]]
    elif p["region_type"] == "COLUMN":
        cells = [c.id for c in characters.values() if c.col == p["index"]]
    elif p["region_type"] == "NEIGHBORS":
        center = characters[p["center"]]
        cells = [c.id for c in characters.values() if c.id != center.id
                 and abs(c.row - center.row) <= 1 and abs(c.col - center.col) <= 1]
    elif p["region_type"] == "EXPLICIT":
        cells = list(p["cells"])
    else:
        from src.core.regions import in_spatial_region
        cells = [c.id for c in characters.values()
                 if in_spatial_region(p["region_type"], c.row, c.col, size)]
    return tuple(sorted(set(cells), key=row_major_key))


def forced_from_public(
    known: Mapping[str, bool], clues: Sequence[Clue],
    characters: Mapping[str, Character], size: int,
) -> dict[str, tuple[bool, str]]:
    """Sound single-clue inference with public arguments only.

    Source clue IDs accompany each conclusion for replayable certificates.
    This deliberately cannot receive Puzzle, GameEngine, or a hidden key.
    """
    evaluator = PuzzleValidator()
    forced: dict[str, tuple[bool, str]] = {}
    for clue in clues:
        scope = clue_scope(clue, characters, size)
        unknown = [cid for cid in scope if cid not in known]
        if len(unknown) > 8:
            raise PuzzleProofError("Refusing enumeration of more than 8 local variables")
        possibilities = {cid: set() for cid in unknown}
        model_count = 0
        for values in product((False, True), repeat=len(unknown)):
            assignment = dict(known)
            assignment.update(zip(unknown, values))
            if evaluator.evaluate_clue(clue, assignment, characters, size):
                model_count += 1
                for cid in unknown:
                    possibilities[cid].add(assignment[cid])
        if model_count == 0:
            raise PuzzleProofError(f"Public contradiction in clue {clue.clue_id}")
        for cid, options in possibilities.items():
            if len(options) == 1:
                value = next(iter(options))
                if cid in forced and forced[cid][0] is not value:
                    raise PuzzleProofError(f"Contradictory public conclusions for {cid}")
                forced.setdefault(cid, (value, clue.clue_id))
    return forced


def prove_uniqueness_local(puzzle: Puzzle) -> list[dict]:
    """Prove all primary statuses from ALL clues, with NO initial status units.

    Semantic truth supplies existence. Induction over these sound deductions
    supplies at most one assignment, independently of the author's hidden key.
    """
    known: dict[str, bool] = {}
    steps = []
    while len(known) < len(puzzle.characters):
        forced = forced_from_public(known, puzzle.clues, puzzle.characters_by_id, puzzle.grid_size)
        if not forced:
            raise PuzzleProofError("Full clues: uniqueness could not be certified by local inference")
        cid = min(forced, key=row_major_key)
        status, source = forced[cid]
        known[cid] = status
        steps.append({"character_id": cid, "status": status, "source_clue_id": source})
    if known != dict(puzzle.hidden_solution):
        raise PuzzleProofError("Unique derived assignment disagrees with authored key")
    return steps


def prove_progressive_local(puzzle: Puzzle) -> list[dict]:
    """Independent reveal simulation, NOT GameEngine/DPLL integration.

    Authoring harness owns the key; the inference function receives only the
    current public facts/clues. Reveal occurs only after proving and checking
    the verdict. No SATQuery or fake SAT evidence is fabricated here.
    """
    known = {cid: puzzle.hidden_solution[cid] for cid in puzzle.initial_revealed}
    by_owner = puzzle.clues_by_owner
    active = [by_owner[cid] for cid in puzzle.initial_revealed]
    steps = []
    while len(known) < len(puzzle.characters):
        forced = forced_from_public(known, active, puzzle.characters_by_id, puzzle.grid_size)
        if not forced:
            raise PuzzleProofError("STUCK: no public forced verdict before completion")
        cid = min(forced, key=row_major_key)
        status, source = forced[cid]
        if status is not puzzle.hidden_solution[cid]:
            raise PuzzleProofError("Proved verdict disagrees with authored key")
        steps.append({
            "step": len(steps) + 1, "character_id": cid, "status": status,
            "source_clue_id": source,
            "active_clue_ids": [c.clue_id for c in active],
            "newly_revealed_clue_id": by_owner[cid].clue_id,
        })
        known[cid] = status
        active.append(by_owner[cid])
    # Check the final reveal as well, including its clue's consistency.
    forced_from_public(known, active, puzzle.characters_by_id, puzzle.grid_size)
    return steps


def prove_uniqueness(puzzle: Puzzle) -> dict:
    from tools.reference_sat import unique_reference
    try:
        return unique_reference(puzzle)
    except ValueError as exc:
        raise PuzzleProofError(str(exc)) from exc


def prove_progressive(puzzle: Puzzle) -> list[dict]:
    from tools.reference_sat import PublicSAT
    known = {cid: puzzle.hidden_solution[cid] for cid in puzzle.initial_revealed}
    active = [puzzle.clues_by_owner[cid] for cid in puzzle.initial_revealed]
    ordered = sorted(puzzle.characters_by_id, key=row_major_key)
    steps = []
    while len(known) < len(ordered):
        unresolved = [cid for cid in ordered if cid not in known]
        # Only currently revealed Clue objects cross into the public reasoner.
        with PublicSAT(active, puzzle.characters_by_id, puzzle.grid_size) as sat:
            forced, unknown = sat.classify(known, unresolved)
            if not forced:
                raise PuzzleProofError("STUCK: no public forced verdict before completion")
            cid = min(forced, key=row_major_key)
            status = forced[cid]
            evidence = sat.minimum_support(known, cid, status)
            steps.append({
                "step": len(steps) + 1, "character_id": cid, "status": status,
                "known_verdicts": dict(known),
                "active_clue_ids": [c.clue_id for c in active],
                "newly_revealed_clue_id": puzzle.clues_by_owner[cid].clue_id,
                "forced_character_ids": list(forced), "unknown_character_ids": unknown,
                "forced_choice_count": len(forced),
                "classification_sat_calls": 1 + 2 * len(unresolved),
                "reference_sat_calls": sat.calls,
                "public_cnf_clauses": sum(len(f) for f in sat.fragments.values()) + len(known),
                "reference_solver_stats": sat.solver.accum_stats(),
                "reasoning_kind": "multi-clue" if evidence["minimum_clue_support_size"] >= 2 else "single-clue",
                **evidence,
            })
        # The authoring controller alone may use the private key for acceptance.
        if status is not puzzle.hidden_solution[cid]:
            raise PuzzleProofError("Proved verdict disagrees with authored key")
        known[cid] = status
        active.append(puzzle.clues_by_owner[cid])
    return steps


def verify_trace(puzzle: Puzzle, trace: list[dict]) -> None:
    """Recompute the certificate, rejecting forged labels, stale K or hidden clues."""
    expected = prove_progressive(puzzle)
    if trace != expected:
        raise PuzzleProofError("Invalid trace: verdict, reveal order, public clues or minimum support differs")


def structural_features(puzzle: Puzzle, steps: list[dict]) -> dict:
    """Cell-name-independent WL graph + histograms and overlap measurements."""
    import hashlib
    nodes = {}
    edges = {}
    for cid in puzzle.characters_by_id:
        node = "cell:" + cid
        nodes[node] = "initial" if cid in puzzle.initial_revealed else "hidden"
        edges[node] = []
    scopes = []
    normalized = []
    for clue in puzzle.clues:
        node = "clue:" + clue.clue_id
        scope = clue_scope(clue, puzzle.characters_by_id, puzzle.grid_size)
        scopes.append(set(scope))
        p = clue.parameters
        detail = p.get("k", p.get("status", p.get("parity", p.get("op"))))
        if clue.clue_type == "IMPLIES":
            detail = (p["antecedent"]["status"], p["consequent"]["status"])
        label = (clue.clue_type, p.get("region_type", "BINARY"), len(scope), detail)
        nodes[node] = repr(label)
        edges[node] = [("owner", "cell:" + clue.owner_id)] + [("scope", "cell:" + cid) for cid in scope]
        edges["cell:" + clue.owner_id].append(("owns", node))
        for cid in scope:
            edges["cell:" + cid].append(("in", node))
        normalized.append((label, tuple(scope)))
    colors = nodes
    for _ in range(4):
        colors = {node: hashlib.sha256(repr((colors[node], sorted((role, colors[n]) for role, n in edges[node]))).encode()).hexdigest()
                  for node in nodes}
    fingerprint = hashlib.sha256(repr(sorted(colors.values())).encode()).hexdigest()
    overlaps = [len(a & b) / len(a | b) for i, a in enumerate(scopes) for b in scopes[i+1:] if a | b]
    support_hist = Counter(s["minimum_clue_support_size"] for s in steps)
    return {"wl_fingerprint": fingerprint,
            "clue_histogram": dict(sorted(Counter(c.clue_type for c in puzzle.clues).items())),
            "scope_size_histogram": dict(sorted(Counter(len(s) for s in scopes).items())),
            "support_histogram": dict(sorted(support_hist.items())),
            "mean_region_jaccard": round(sum(overlaps) / len(overlaps), 6),
            "mean_forced_choices": round(sum(s["forced_choice_count"] for s in steps) / max(len(steps), 1), 4),
            "logical_duplicate_clues": len(normalized) - len(set(normalized))}


def difficulty_metrics(steps, features):
    count = len(steps)
    multi = sum(s["minimum_clue_support_size"] >= 2 for s in steps)
    triple = sum(s["minimum_clue_support_size"] >= 3 for s in steps)
    maximum = max(s["minimum_clue_support_size"] for s in steps)
    clue_depth, depths = {}, []
    for step in steps:
        depth = 1 + max((clue_depth.get(cid, 0) for cid in step["minimal_supporting_clue_ids"]), default=0)
        clue_depth[step["newly_revealed_clue_id"]] = depth
        depths.append(depth)
    # Subjective heuristic using actual proof support and reveal dependency
    # depth. Neither grid area nor solver runtime inflates the difficulty.
    peak = min(max(maximum-1, 0)/2, 1)
    score = round(40 * multi/count + 25 * triple/count + 20 * peak
                  + 10 * min(max(depths, default=0) / 10, 1) + 5 * features["mean_region_jaccard"], 2)
    label = "Tutorial" if multi == 0 else "Easy" if score < 24 else "Medium" if score < 38 else "Hard" if score < 49 else "Very Hard"
    uses = Counter(cid for step in steps for cid in step["minimal_supporting_clue_ids"])
    return {"score": score, "label": label, "multi_clue_steps": multi,
            "maximum_reveal_depth": max(depths, default=0),
            "mean_reveal_depth": round(sum(depths) / max(count, 1), 3),
            "intermediate_chain_steps": sum(d > 1 for d in depths),
            "three_plus_clue_steps": triple, "single_clue_steps": count-multi,
            "multi_clue_ratio": round(multi/count, 6),
            "maximum_minimum_support": maximum,
            "steps_with_multiple_forced_choices": sum(s["forced_choice_count"] > 1 for s in steps),
            "unknown_to_forced_transitions": sum(
                s["character_id"] in steps[i-1]["unknown_character_ids"] for i, s in enumerate(steps) if i),
            "selected_minimum_support_uses": dict(sorted(uses.items())),
            "reference_sat_calls": sum(s["reference_sat_calls"] for s in steps),
            "classification_sat_calls": sum(s["classification_sat_calls"] for s in steps)}


def global_finale_witness(puzzle, steps):
    """Certify a last-criminal deduction which genuinely needs a global clue."""
    from tools.reference_sat import PublicSAT
    if not steps:
        return None
    last = steps[-1]
    known = last["known_verdicts"]
    globals_ = [c for c in puzzle.clues if c.clue_id in last["active_clue_ids"]
                and c.clue_type == "EXACTLY" and c.parameters.get("region_type") == "ALL"]
    for clue in globals_:
        total = clue.parameters["k"]
        if last["status"] is not True or sum(known.values()) != total - 1:
            continue
        other = [c for c in puzzle.clues if c.clue_id in last["active_clue_ids"]
                 and c not in globals_]
        with PublicSAT(other, puzzle.characters_by_id, puzzle.grid_size) as sat:
            if sat.query(known, assumption=-sat.variable_map.get_var(last["character_id"])):
                return {"step": last["step"], "character_id": last["character_id"],
                        "global_clue_id": clue.clue_id, "known_criminals_before": total - 1,
                        "required_total": total, "without_global_opposite_satisfiable": True}
    return None


def validate_puzzle(raw: dict, *, check_runtime: bool = True) -> dict:
    SCHEMA_VALIDATOR.validate(raw)
    puzzle = PuzzleValidator().validate(raw)
    ordered = sorted(puzzle.characters, key=lambda c: (c.row, c.col))
    for c in ordered:
        if c.id != f"{chr(65 + c.col)}{c.row + 1}":
            raise PuzzleProofError("Cell ID does not match its coordinate")
    names = [c.name.casefold() for c in ordered]
    if names != sorted(names) or len(set(names)) != len(names):
        raise PuzzleProofError("Display names must be distinct and alphabetical across rows")
    if not 0 < len(puzzle.initial_revealed) < len(puzzle.characters):
        raise PuzzleProofError("Require at least one initial and at least one unresolved card")
    full_proof = prove_uniqueness(puzzle)
    reveal_proof = prove_progressive(puzzle)
    features = structural_features(puzzle, reveal_proof)
    difficulty = difficulty_metrics(reveal_proof, features)
    runtime = None
    if check_runtime:
        from tools.certify_runtime import certify_runtime
        runtime = certify_runtime(puzzle)
    criminal_count = sum(puzzle.hidden_solution.values())
    return {
        "puzzle_id": puzzle.puzzle_id, "size": puzzle.grid_size,
        "criminal_count": criminal_count,
        "innocent_count": len(puzzle.characters) - criminal_count,
        "clue_count": len(puzzle.clues),
        "initial_revealed_count": len(puzzle.initial_revealed),
        "clue_types": sorted({c.clue_type for c in puzzle.clues}),
        "region_types": sorted({c.parameters["region_type"] for c in puzzle.clues
                                if "region_type" in c.parameters}),
        "validation_status": "PASSED",
        "checks": {"schema": "PASSED", "semantic_truth": "PASSED",
                   "reference_sat_uniqueness": "PASSED", "public_no_guess": "PASSED",
                   "exact_minimum_support": "PASSED",
                   "dpll_cnf_integration": "PASSED" if check_runtime else "SKIPPED"},
        "proof_method": "independent reference SAT + exact support subsets; production encoder/DPLL replay",
        "runtime_proof": runtime,
        "global_finale": global_finale_witness(puzzle, reveal_proof),
        "uniqueness_proof": full_proof,
        "reveal_proof": reveal_proof,
        "structural_features": features,
        "difficulty": difficulty,
        "clues_absent_from_selected_minimum_supports": sorted(
            {c.clue_id for c in puzzle.clues} - set(difficulty["selected_minimum_support_uses"])),
    }


def validate_dataset(directory: Path) -> list[dict]:
    expected = {f"{pid}.json" for pid in PUZZLE_IDS}
    # Preserve Hiệp's sample; select Phước's dataset explicitly by naming rule.
    actual = {p.name for p in directory.glob("[345]x[345]_*.json")}
    if actual != expected:
        raise PuzzleProofError(f"Dataset files mismatch: missing={expected-actual}, extra={actual-expected}")
    reports = []
    fingerprints = set()
    types, regions = set(), set()
    solutions = set()
    for pid in PUZZLE_IDS:
        raw = json.loads((directory / f"{pid}.json").read_text(encoding="utf-8"))
        if raw["puzzle_id"] != pid:
            raise PuzzleProofError(f"Puzzle ID differs from filename: {pid}")
        fingerprint = json.dumps({"solution": raw["hidden_solution"], "initial": raw["initial_revealed"],
                                  "clues": raw["clues"]}, sort_keys=True)
        if fingerprint in fingerprints:
            raise PuzzleProofError("Duplicate logical puzzle")
        fingerprints.add(fingerprint)
        solutions.add(tuple(raw["hidden_solution"].items()))
        report = validate_puzzle(raw)
        types.update(report["clue_types"])
        regions.update(report["region_types"])
        reports.append(report)
    if Counter(r["size"] for r in reports) != {3: 5, 4: 5, 5: 5}:
        raise PuzzleProofError("Dataset requires five puzzles of each size")
    required_types = PuzzleValidator.CORE_CLUE_TYPES
    required_regions = {"ROW", "COLUMN", "NEIGHBORS", "EXPLICIT"}
    manifest_path = directory / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")).get("generator_version", "").startswith("3."):
        required_types = required_types | {"PARITY", "COUNT_COMPARE", "IMPLIES"}
        required_regions |= {"ALL", "PROFESSION", "CORNERS", "CENTER"}
    if not required_types <= types or not required_regions <= regions:
        raise PuzzleProofError("Dataset does not cover the required clue families and regions")
    if len(solutions) != 15:
        raise PuzzleProofError("Repeated hidden board in dataset")
    if len({r["structural_features"]["wl_fingerprint"] for r in reports}) != 15:
        raise PuzzleProofError("Indistinguishable constraint/ownership WL graphs in dataset")
    return reports


def structural_comparisons(reports):
    """Weighted histogram similarity flags near matches; not a JSON hash.

    50% clue family, 25% scope sizes, 25% measured support histogram. WL
    fingerprints separately detect name-independent ownership/scope graphs.
    A high histogram score is a review flag, not proof of graph isomorphism.
    """
    result = []
    for i, a in enumerate(reports):
        for b in reports[i+1:]:
            if a["size"] != b["size"]:
                continue
            scores = []
            for name, weight in [("clue_histogram", .5), ("scope_size_histogram", .25), ("support_histogram", .25)]:
                ha, hb = a["structural_features"][name], b["structural_features"][name]
                keys = set(ha) | set(hb)
                total_a, total_b = sum(ha.values()), sum(hb.values())
                distance = sum(abs(ha.get(k, 0)/total_a - hb.get(k, 0)/total_b) for k in keys)
                scores.append(weight * (1-distance/2))
            similarity = round(sum(scores), 6)
            result.append({"a": a["puzzle_id"], "b": b["puzzle_id"], "similarity": similarity,
                           "near_duplicate_review_flag": similarity >= .96,
                           "wl_equal": a["structural_features"]["wl_fingerprint"] == b["structural_features"]["wl_fingerprint"]})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "puzzles")
    parser.add_argument("--report", type=Path, help="Optional JSON report including replayable proofs")
    args = parser.parse_args()
    try:
        reports = validate_dataset(args.directory)
    except (ValueError, KeyError, TypeError, OSError, ValidationError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    for r in reports:
        print(f"{r['puzzle_id']}: PASSED (reference SAT uniqueness + public no-guess, "
              f"{r['difficulty']['multi_clue_steps']} multi-clue / {len(r['reveal_proof'])} reveals); production DPLL/CNF PASSED")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
