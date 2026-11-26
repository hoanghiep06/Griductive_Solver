"""Independent rule truth tables and campaign authoring guarantees."""

from itertools import product
import json
import random

import pytest
from pysat.solvers import Solver

from src.core.clue import Clue
from src.core.puzzle_loader import PuzzleLoader
from src.core.puzzle_validator import PuzzleValidationError, PuzzleValidator
from src.core.variable_map import VariableMap
from src.encoder.cnf_encoder import CNFEncoder
from src.solvers.dpll import DPLLSolver
from tools.generate_puzzles import build_puzzle, official_characters
from tools.reference_sat import PublicSAT
from tools.validate_puzzles import ROOT, PUZZLE_IDS, clue_scope, validate_puzzle


@pytest.mark.parametrize("region,expected", [
    ("CORNERS", {"A1", "C1", "A3", "C3"}),
    ("BORDER", {"A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3"}),
    ("CENTER", {"B2"}),
    ("TOP_HALF", {"A1", "B1", "C1"}), ("BOTTOM_HALF", {"A3", "B3", "C3"}),
    ("LEFT_HALF", {"A1", "A2", "A3"}), ("RIGHT_HALF", {"C1", "C2", "C3"}),
])
def test_named_regions_have_exact_membership_and_sound_encoding(region, expected):
    puzzle = PuzzleLoader().load(ROOT / "puzzles/3x3_01.json")
    vm = VariableMap.from_characters(puzzle.characters)
    vm.freeze_primary_variables()
    encoder = CNFEncoder(vm)
    assert set(encoder.resolve_region(region)) == expected
    clue = Clue("group", "A1", "EXACTLY", {"region_type": region, "k": len(expected) // 2})
    assert set(clue_scope(clue, puzzle.characters_by_id, 3)) == expected
    cnf = encoder.encode_clue(clue)
    with Solver(name="m22", bootstrap_with=cnf) as sat:
        for values in product((False, True), repeat=9):
            assignment = dict(zip([c.id for c in puzzle.characters], values))
            expected_truth = sum(assignment[cid] for cid in expected) == len(expected) // 2
            assumptions = [vm.to_literal(cid, value) for cid, value in assignment.items()]
            assert sat.solve(assumptions=assumptions) == expected_truth
            assert PuzzleValidator().evaluate_clue(clue, assignment, puzzle.characters_by_id, 3) == expected_truth


@pytest.mark.parametrize("a_status,b_status", tuple(product(("CRIMINAL", "INNOCENT"), repeat=2)))
def test_implies_truth_table_including_contrapositive_and_false_antecedent(a_status, b_status):
    puzzle = PuzzleLoader().load(ROOT / "puzzles/3x3_01.json")
    clue = Clue("if", "A1", "IMPLIES", {
        "antecedent": {"target": "A1", "status": a_status},
        "consequent": {"target": "C3", "status": b_status},
    })
    vm = VariableMap.from_characters(puzzle.characters)
    vm.freeze_primary_variables()
    cnf = CNFEncoder(vm).encode_clue(clue)
    with PublicSAT([clue], puzzle.characters_by_id, 3) as reference:
        for a, b in product((False, True), repeat=2):
            known = {"A1": a, "C3": b}
            truth = a != (a_status == "CRIMINAL") or b == (b_status == "CRIMINAL")
            assert DPLLSolver().solve(cnf + [[vm.to_literal(cid, v)] for cid, v in known.items()]) == truth
            assert reference.query(known) == truth
            assert PuzzleValidator().evaluate_clue(clue, known, puzzle.characters_by_id, 3) == truth


@pytest.mark.parametrize("op", ["<", "<=", "==", "!=", ">=", ">"])
def test_comparison_overlapping_groups_preserves_the_shared_cell(op):
    puzzle = PuzzleLoader().load(ROOT / "puzzles/3x3_01.json")
    clue = Clue("compare", "A1", "COUNT_COMPARE", {
        "region_a": ["A1", "B1", "C1"], "region_b": ["C1", "C2", "C3"], "op": op,
    })
    vm = VariableMap.from_characters(puzzle.characters)
    vm.freeze_primary_variables()
    cnf = CNFEncoder(vm).encode_clue(clue)
    cells = ("A1", "B1", "C1", "C2", "C3")
    import operator
    compare = {"<": operator.lt, "<=": operator.le, "==": operator.eq,
               "!=": operator.ne, ">=": operator.ge, ">": operator.gt}[op]
    with PublicSAT([clue], puzzle.characters_by_id, 3) as reference:
        for values in product((False, True), repeat=len(cells)):
            known = dict(zip(cells, values))
            truth = compare(sum(known[c] for c in ("A1", "B1", "C1")), sum(known[c] for c in ("C1", "C2", "C3")))
            assert DPLLSolver().solve(cnf + [[vm.to_literal(cid, v)] for cid, v in known.items()]) == truth
            assert reference.query(known) == truth


@pytest.mark.parametrize("kind", ["EXACTLY", "PARITY", "COUNT_COMPARE"])
def test_large_global_reference_auxiliaries_do_not_collide_with_selectors(kind):
    raw = build_puzzle(5, 2)
    puzzle = PuzzleValidator().validate(raw)
    ids = [c.id for c in puzzle.characters]
    params = {
        "EXACTLY": {"region_type": "ALL", "k": 12},
        "PARITY": {"cells": ids, "parity": "even"},
        "COUNT_COMPARE": {"region_a": ids[:15], "region_b": ids[10:], "op": "!="},
    }[kind]
    clue = Clue("large", ids[0], kind, params)
    vm = VariableMap.from_characters(puzzle.characters)
    vm.freeze_primary_variables()
    cnf = CNFEncoder(vm).encode_clue(clue)
    rng = random.Random(42)
    assignments = [{cid: flag for cid in ids} for flag in (False, True)]
    assignments += [{cid: bool(rng.getrandbits(1)) for cid in ids} for _ in range(40)]
    with PublicSAT([clue], puzzle.characters_by_id, 5) as reference:
        selectors = set(reference.selectors.values())
        encoded_ids = {abs(lit) for fragment in reference.fragments.values() for clause in fragment for lit in clause}
        assert not selectors & encoded_ids
        for known in assignments:
            truth = PuzzleValidator().evaluate_clue(clue, known, puzzle.characters_by_id, 5)
            assert reference.query(known) == truth
            assert DPLLSolver().solve(cnf + [[vm.to_literal(cid, v)] for cid, v in known.items()]) == truth


def test_profession_group_must_match_exact_public_membership():
    raw = build_puzzle(5, 3)
    clue = next(c for c in raw["clues"] if c["parameters"].get("region_type") == "PROFESSION")
    clue["parameters"]["cells"] = clue["parameters"]["cells"][:1]
    with pytest.raises(PuzzleValidationError, match="exactly the characters"):
        PuzzleValidator().validate(raw)


@pytest.mark.parametrize("size", [3, 4, 5])
def test_last_criminal_really_requires_global_total(size):
    raw = json.loads((ROOT / f"puzzles/{size}x{size}_02.json").read_text(encoding="utf-8"))
    report = validate_puzzle(raw, check_runtime=False)
    witness = report["global_finale"]
    assert witness and witness["step"] == len(report["reveal_proof"])
    assert witness["known_criminals_before"] == witness["required_total"] - 1
    assert witness["without_global_opposite_satisfiable"]
    initial_clues = {c["clue_id"] for c in raw["clues"] if c["owner_id"] in raw["initial_revealed"]}
    assert witness["global_clue_id"] in initial_clues


def test_campaign_progression_changes_motifs_without_decreasing_difficulty_band():
    manifest = json.loads((ROOT / "puzzles/manifest.json").read_text(encoding="utf-8"))
    entries = manifest["puzzles"]
    ranks = {name: i for i, name in enumerate(("Tutorial", "Easy", "Medium", "Hard", "Very Hard"))}
    assert [ranks[e["difficulty_label"]] for e in entries] == sorted(ranks[e["difficulty_label"]] for e in entries)
    assert [e["progression_rank"] for e in entries] == list(range(1, 16))
    assert all(a["archetype"] != b["archetype"] for a, b in zip(entries, entries[1:]))
    for size in (3, 4, 5):
        assert len({e["archetype"] for e in entries if e["size"] == size}) == 5
    assert all(e["checks"]["dpll_cnf_integration"] == "PASSED" for e in entries)
    assert {e["difficulty_label"] for e in entries} == set(ranks)


def test_generator_keeps_every_public_identity_aligned_with_existing_portraits():
    for pid in PUZZLE_IDS:
        raw = json.loads((ROOT / f"puzzles/{pid}.json").read_text(encoding="utf-8"))
        assert raw["characters"] == official_characters(int(pid[0]), int(pid[-2:]))
