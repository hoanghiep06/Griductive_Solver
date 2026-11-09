"""Authoring-only proofs using local clue semantics, NOT a SAT replacement.

Each inference enumerates only the unknown cells in ONE core clue (at most 8),
then intersects its models. Completion from no initial facts proves uniqueness
of the full clue set. This sufficient procedure may fail on valid harder maps.
No result here is presented as measured DPLL evidence.
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
    """Resolve the official four regions without accessing private Core APIs."""
    p = clue.parameters
    if clue.clue_type == "FACT":
        cells = [p["target"]]
    elif clue.clue_type in {"SAME", "DIFFERENT"}:
        cells = [p["target1"], p["target2"]]
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
        raise PuzzleProofError(f"Unsupported region in {clue.clue_id}")
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
        if clue.clue_type not in evaluator.CORE_CLUE_TYPES:
            raise PuzzleProofError("Only agreed core clues are supported")
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


def prove_uniqueness(puzzle: Puzzle) -> list[dict]:
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


def prove_progressive(puzzle: Puzzle) -> list[dict]:
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


def validate_puzzle(raw: dict) -> dict:
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
                   "constructive_uniqueness": "PASSED", "public_no_guess": "PASSED",
                   "dpll_cnf_integration": "SKIPPED"},
        "proof_method": "local semantic enumeration (<=8 unknowns per clue); no CNF or SAT",
        "uniqueness_proof": full_proof,
        "reveal_proof": reveal_proof,
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
    if types != PuzzleValidator.CORE_CLUE_TYPES or regions != PuzzleValidator.SUPPORTED_REGION_TYPES:
        raise PuzzleProofError("Dataset does not cover all six core clues and four regions")
    if len(solutions) != 15:
        raise PuzzleProofError("Repeated hidden board in dataset")
    return reports


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
        print(f"{r['puzzle_id']}: PASSED (constructive uniqueness + public no-guess, "
              f"{len(r['reveal_proof'])} reveals); DPLL/CNF integration SKIPPED")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
