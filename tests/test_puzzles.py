import copy
from collections import Counter
from itertools import product
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from src.core.clue import Clue
from src.core.puzzle_loader import PuzzleLoader
from src.core.puzzle_validator import PuzzleValidationError, PuzzleValidator
from tools.generate_puzzles import DEFAULT_SEED, build_puzzle, generate_dataset
from tools.validate_puzzles import (
    PUZZLE_IDS, ROOT, PuzzleProofError, clue_scope, forced_from_public,
    prove_progressive, validate_dataset, validate_puzzle,
)


@pytest.fixture(scope="module")
def reports():
    return validate_dataset(ROOT / "puzzles")


def load_raw(pid):
    return json.loads((ROOT / "puzzles" / f"{pid}.json").read_text(encoding="utf-8"))


def test_exactly_fifteen_dataset_files_and_five_per_size(reports):
    assert len(reports) == 15
    assert Counter(r["size"] for r in reports) == {3: 5, 4: 5, 5: 5}
    assert {r["puzzle_id"] for r in reports} == set(PUZZLE_IDS)
    # Hiệp's original sample is intentionally retained outside this dataset.
    assert (ROOT / "puzzles/sample_3x3.json").exists()


@pytest.mark.parametrize("pid", PUZZLE_IDS)
def test_schema_semantics_unique_solution_and_progressive_proof(pid):
    report = validate_puzzle(load_raw(pid))
    assert report["validation_status"] == "PASSED"
    assert report["checks"] == {
        "schema": "PASSED", "semantic_truth": "PASSED", "reference_sat_uniqueness": "PASSED",
        "exact_minimum_support": "PASSED",
        "public_no_guess": "PASSED", "dpll_cnf_integration": "SKIPPED",
    }
    assert len(report["uniqueness_proof"]["primary_model"]) == report["size"] ** 2
    assert report["uniqueness_proof"]["second_sat"] is False
    assert len(report["reveal_proof"]) == report["size"] ** 2 - report["initial_revealed_count"]


def test_all_six_templates_four_regions_and_varied_boards(reports):
    assert set.union(*(set(r["clue_types"]) for r in reports)) == PuzzleValidator.CORE_CLUE_TYPES
    assert set.union(*(set(r["region_types"]) for r in reports)) == PuzzleValidator.SUPPORTED_REGION_TYPES
    for size in (3, 4, 5):
        raws = [load_raw(pid) for pid in PUZZLE_IDS if pid.startswith(str(size))]
        assert len({json.dumps(r["clues"], sort_keys=True) for r in raws}) == 5
        assert len({tuple(r["hidden_solution"].values()) for r in raws}) == 5
        assert len({tuple(r["initial_revealed"]) for r in raws}) >= 4
        # V2 no longer imposes the old monotone criminal-ratio template.
        assert len({sum(r["hidden_solution"].values()) for r in raws}) >= 3
        assert all(sum(c["type"] == "FACT" for c in r["clues"]) <= 3 for r in raws)


def test_generator_is_byte_for_byte_reproducible(tmp_path):
    manifest = generate_dataset(tmp_path)
    assert len(manifest) == 15
    assert len(list(tmp_path.glob("*.json"))) == 16  # 15 puzzles + manifest.
    before = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    for name, contents in before.items():
        assert contents == (ROOT / "puzzles" / name).read_bytes()
    generate_dataset(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    assert len(validate_dataset(tmp_path)) == 15


def test_fixed_seed_is_local_and_alternate_seed_is_valid():
    import random
    random.seed(123)
    state = random.getstate()
    first = build_puzzle(5, 3, DEFAULT_SEED)
    assert random.getstate() == state
    second = build_puzzle(5, 3, DEFAULT_SEED + 1)
    assert first != second
    assert validate_puzzle(second)["validation_status"] == "PASSED"


@pytest.mark.parametrize("pid", PUZZLE_IDS[:5])
def test_3x3_exhaustive_cross_check_independent_of_constructive_proof(pid):
    """Check all 512 full states and exact public models using TV1's code."""
    puzzle = PuzzleLoader().load(ROOT / "puzzles" / f"{pid}.json")
    validator = PuzzleValidator()
    ids = [c.id for c in puzzle.characters]
    models = []
    for values in product((False, True), repeat=9):
        assignment = dict(zip(ids, values))
        if all(validator.evaluate_clue(c, assignment, puzzle.characters_by_id, 3) for c in puzzle.clues):
            models.append(assignment)
    assert models == [dict(puzzle.hidden_solution)]
    exact = validator.analyze_sequential_solvability(puzzle)
    assert exact.status.value == "SOLVED"
    proof = prove_progressive(puzzle)
    # Local inference may prove fewer characters per state, but every verdict
    # is globally forced and both procedures finish with the same assignment.
    assert len(exact.steps) == len(proof)
    assert {s.character_id: s.status == "CRIMINAL" for s in exact.steps} == {
        s["character_id"]: s["status"] for s in proof}


def test_neighbors_eight_directions_center_excluded():
    puzzle = PuzzleLoader().load(ROOT / "puzzles/3x3_01.json")
    for center, expected in [("A1", 3), ("B1", 5), ("B2", 8)]:
        clue = Clue("test", "A1", "EXACTLY", {"k": 0, "region_type": "NEIGHBORS", "center": center})
        scope = clue_scope(clue, puzzle.characters_by_id, 3)
        assert center not in scope and len(scope) == expected


def test_public_inference_soundness_and_contradiction():
    puzzle = PuzzleLoader().load(ROOT / "puzzles/3x3_01.json")
    chars = puzzle.characters_by_id
    different = Clue("d", "A1", "DIFFERENT", {"target1": "A1", "target2": "B1"})
    assert forced_from_public({}, [different], chars, 3) == {}
    assert forced_from_public({"A1": True}, [different], chars, 3) == {"B1": (False, "d")}
    exact = Clue("e", "A1", "EXACTLY", {"k": 1, "region_type": "EXPLICIT", "cells": ["A1", "B1"]})
    assert forced_from_public({}, [exact], chars, 3) == {}
    assert forced_from_public({"A1": False}, [exact], chars, 3) == {"B1": (True, "e")}
    with pytest.raises(PuzzleProofError, match="contradiction"):
        forced_from_public({"A1": True, "B1": True}, [exact], chars, 3)
    fact = Clue("f", "A1", "FACT", {"target": "B1", "status": "CRIMINAL"})
    with pytest.raises(PuzzleProofError, match="Contradictory"):
        forced_from_public({"A1": True}, [different, fact], chars, 3)


def test_progressive_reasoner_receives_only_revealed_clues(monkeypatch):
    import tools.validate_puzzles as validation
    puzzle = PuzzleLoader().load(ROOT / "puzzles/5x5_03.json")
    seen = []
    from tools.reference_sat import PublicSAT
    original = PublicSAT.classify
    def spy(self, known, unresolved):
        assert all(c.owner_id in known for c in self.clues)
        assert set(c.owner_id for c in self.clues) == set(known)
        seen.append((dict(known), tuple(c.clue_id for c in self.clues)))
        return original(self, known, unresolved)
    monkeypatch.setattr(PublicSAT, "classify", spy)
    steps = validation.prove_progressive(puzzle)
    assert len(seen) == len(steps)
    assert len(seen[0][0]) == len(puzzle.initial_revealed)
    for index, step in enumerate(steps):
        assert step["character_id"] not in seen[index][0]
        assert step["newly_revealed_clue_id"] not in seen[index][1]
        assert set(step["minimal_supporting_clue_ids"]) <= set(seen[index][1])


def test_unique_does_not_imply_no_guess():
    raw = load_raw("3x3_01")
    raw["initial_revealed"] = [raw["clues"][-1]["owner_id"]]
    # Force a definitely stuck start: self-fact on its already exposed owner;
    # all other cards keep independent facts, so the full clue set is unique.
    for clue in raw["clues"]:
        cid = clue["owner_id"]
        clue["type"] = "FACT"
        clue["parameters"] = {"target": cid, "status": "CRIMINAL" if raw["hidden_solution"][cid] else "INNOCENT"}
    with pytest.raises(PuzzleProofError, match="STUCK"):
        validate_puzzle(raw)


def test_ambiguous_full_clues_are_not_marked_unique():
    raw = load_raw("3x3_01")
    for clue in raw["clues"]:
        clue["type"] = "SAME"
        clue["parameters"] = {"target1": "A1", "target2": "A1"}
    with pytest.raises(PuzzleProofError, match="AMBIGUOUS"):
        validate_puzzle(raw)


@pytest.mark.parametrize("defect", ["duplicate_region", "invalid_cell", "false_clue", "bad_name", "coordinate", "count"])
def test_corrupt_dataset_is_rejected(defect):
    raw = copy.deepcopy(load_raw("3x3_01"))
    if defect in {"duplicate_region", "invalid_cell", "count"}:
        raw["clues"][0]["type"] = "EXACTLY"
        raw["clues"][0]["parameters"] = {"region_type": "EXPLICIT", "k": 0,
            "cells": ["A1", "A1"] if defect == "duplicate_region" else ["Z9"] if defect == "invalid_cell" else ["A1"]}
        if defect == "count":
            raw["clues"][0]["parameters"]["k"] = 2
    elif defect == "false_clue":
        raw["clues"][0]["type"] = "FACT"
        raw["clues"][0]["parameters"] = {"target": "A1", "status": "INNOCENT" if raw["hidden_solution"]["A1"] else "CRIMINAL"}
    elif defect == "bad_name":
        raw["characters"][0]["name"] = "ZZZ"
    else:
        raw["characters"][0]["id"] = "Z9"
    with pytest.raises((PuzzleValidationError, PuzzleProofError, ValidationError)):
        validate_puzzle(raw)


def test_manifest_matches_recomputed_reports(reports):
    manifest = json.loads((ROOT / "puzzles/manifest.json").read_text(encoding="utf-8"))
    assert manifest["generator_seed"] == DEFAULT_SEED
    for entry, report in zip(manifest["puzzles"], reports):
        for field in ("puzzle_id", "size", "criminal_count", "innocent_count", "clue_count",
                      "initial_revealed_count", "checks", "clue_types", "region_types"):
            assert entry[field] == report[field]
        assert entry["difficulty_measured"] is True
        assert entry["difficulty_is_subjective_heuristic"] is True


def test_validator_cli_reports_failed_schema_without_traceback(tmp_path, capsys, monkeypatch):
    from tools.validate_puzzles import main
    (tmp_path / "3x3_01.json").write_text('{"puzzle_id": "3x3_01"}', encoding="utf-8")
    # Ensure directory membership passes so schema failure is the tested path.
    for pid in PUZZLE_IDS[1:]:
        (tmp_path / f"{pid}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validate_puzzles", "--directory", str(tmp_path)])
    # Required schema fields are absent, despite having the right puzzle ID.
    assert main() == 1
    assert "FAILED:" in capsys.readouterr().err


def test_local_enumeration_limit_prevents_board_wide_search():
    puzzle = PuzzleLoader().load(ROOT / "puzzles/3x3_01.json")
    clue = Clue("large", "A1", "EXACTLY", {
        "k": 4, "region_type": "EXPLICIT", "cells": list(puzzle.characters_by_id),
    })
    with pytest.raises(PuzzleProofError, match="more than 8"):
        forced_from_public({}, [clue], puzzle.characters_by_id, 3)
