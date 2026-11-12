"""Standalone unit tests for VariableMap and CNFEncoder using Dict inputs."""

from __future__ import annotations

import itertools
from pathlib import Path
import sys

import pytest

# Ensure repository root is importable when running pytest directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.encoder import CNFEncoder, EncodedKB, VariableMap, normalize_coord, parse_coord


def _count_aux_models(
    clauses: list[list[int]],
    assignment: dict[int, bool],
    aux_vars: list[int],
) -> int:
    """Count satisfying extensions over aux_vars via unit propagation + backtracking."""
    assign = dict(assignment)
    changed = True
    while changed:
        changed = False
        for clause in clauses:
            sat = False
            unassigned_lits: list[int] = []
            for lit in clause:
                var = abs(lit)
                if var in assign:
                    if (lit > 0) == assign[var]:
                        sat = True
                        break
                else:
                    unassigned_lits.append(lit)
            if sat:
                continue
            if not unassigned_lits:
                return 0
            if len(unassigned_lits) == 1:
                u = unassigned_lits[0]
                assign[abs(u)] = u > 0
                changed = True

    remaining = [v for v in aux_vars if v not in assign]
    if not remaining:
        return 1

    branch_var = remaining[0]
    total = 0
    for val in (False, True):
        nxt = dict(assign)
        nxt[branch_var] = val
        total += _count_aux_models(clauses, nxt, remaining)
    return total


def _satisfying_primary_projections(
    clauses: list[list[int]],
    primary_vars: list[int],
    aux_vars: list[int],
) -> tuple[set[tuple[bool, ...]], dict[tuple[bool, ...], int]]:
    """Verify all 2^P primary assignments and count valid aux extensions for each."""
    valid_primaries: set[tuple[bool, ...]] = set()
    multiplicity: dict[tuple[bool, ...], int] = {}

    for p_vals in itertools.product((False, True), repeat=len(primary_vars)):
        p_assign = dict(zip(primary_vars, p_vals))
        count = _count_aux_models(clauses, p_assign, aux_vars)
        if count > 0:
            valid_primaries.add(p_vals)
            multiplicity[p_vals] = count

    return valid_primaries, multiplicity


# ---------------------------------------------------------------------------
# VariableMap tests
# ---------------------------------------------------------------------------


def test_coord_helpers() -> None:
    assert parse_coord("c2") == (3, 2)
    assert parse_coord(" A1 ") == (1, 1)
    assert normalize_coord("b3") == "B3"
    with pytest.raises(ValueError):
        parse_coord("2C")
    with pytest.raises(ValueError):
        parse_coord("A0")


def test_variable_map_deterministic_alphabetical_order() -> None:
    chars_order_1 = [
        {"name": "Clara", "coord": "C1", "profession": "Guard"},
        {"name": "Abel", "coord": "A1", "profession": "Cook"},
        {"name": "Bea", "coord": "B1", "profession": "Clerk"},
    ]
    chars_order_2 = [chars_order_1[2], chars_order_1[0], chars_order_1[1]]

    vm1 = VariableMap.from_puzzle({"size": 3, "characters": chars_order_1})
    vm2 = VariableMap.from_puzzle({"size": 3, "characters": chars_order_2})

    assert vm1.primary_map == {"Abel": 1, "Bea": 2, "Clara": 3}
    assert vm2.primary_map == vm1.primary_map
    assert vm1.get_primary("abel") == 1
    assert vm1.get_primary("A1") == 1
    assert vm1.get_primary("c1") == 3
    assert vm1.num_primary == 3
    assert vm1.num_auxiliary == 0


def test_variable_map_pure_coords_row_major() -> None:
    vm = VariableMap.from_puzzle({"size": 2})
    assert vm.primary_map == {"A1": 1, "B1": 2, "A2": 3, "B2": 4}


def test_variable_map_primary_aux_separation() -> None:
    vm = VariableMap.from_characters(["Abel", "Bea", "Clara"])
    aux1 = vm.allocate_aux("seq_0_1")
    aux2 = vm.allocate_aux("seq_1_1")

    assert aux1 == 4
    assert aux2 == 5
    assert vm.primary_ids == [1, 2, 3]
    assert vm.auxiliary_ids == [4, 5]
    assert set(vm.primary_ids).isdisjoint(set(vm.auxiliary_ids))

    assert vm.is_primary(1) and not vm.is_auxiliary(1)
    assert vm.is_primary(-2) and not vm.is_auxiliary(-2)
    assert vm.is_auxiliary(4) and not vm.is_primary(4)
    assert vm.is_auxiliary(-5) and not vm.is_primary(-5)

    assert vm.label_of(1) == "C[Abel]"
    assert vm.label_of(-1) == "~C[Abel]"
    assert vm.label_of(4).startswith("AUX[4:")

    # Adding primary variables after auxiliary allocation is forbidden
    with pytest.raises(RuntimeError):
        vm.register_characters(["Derek"])

    # Decode model ignores auxiliary variables and extracts primary verdicts only
    model = {1: True, 2: False, 3: True, 4: True, 5: False}
    assert vm.decode_model(model) == {
        "Abel": "CRIMINAL",
        "Bea": "INNOCENT",
        "Clara": "CRIMINAL",
    }

    vm.reset_auxiliary()
    assert vm.num_auxiliary == 0
    assert vm.num_primary == 3
    assert vm.allocate_aux("fresh") == 4


def test_variable_map_grid_regions_3x3() -> None:
    puzzle = {
        "size": 3,
        "characters": {
            "A1": "Abel",
            "B1": "Bea",
            "C1": "Clara",
            "A2": "Derek",
            "B2": "Eliza",
            "C2": "Franz",
            "A3": "Grant",
            "B3": "Hannah",
            "C3": "Ivy",
        },
    }
    vm = VariableMap.from_puzzle(puzzle)

    assert vm.cells_in_row(2) == ["Derek", "Eliza", "Franz"]
    assert vm.cells_in_col("B") == ["Bea", "Eliza", "Hannah"]
    # Corner cell A1 has 3 neighbors (excluding self)
    assert vm.neighbors_of("A1") == ["Bea", "Derek", "Eliza"]
    # Edge cell B1 has 5 neighbors
    assert vm.neighbors_of("B1") == ["Abel", "Clara", "Derek", "Eliza", "Franz"]
    # Interior cell B2 (Eliza) has 8 neighbors (excluding Eliza)
    neighbors_b2 = vm.neighbors_of("Eliza")
    assert len(neighbors_b2) == 8
    assert "Eliza" not in neighbors_b2


def test_variable_map_validation_errors() -> None:
    with pytest.raises(ValueError):
        VariableMap.from_characters([])
    with pytest.raises(ValueError):
        VariableMap.from_characters(["Abel", "abel"])
    with pytest.raises(ValueError):
        VariableMap.from_puzzle(
            {
                "size": 2,
                "characters": [
                    {"name": "Abel", "coord": "A1"},
                    {"name": "Bea", "coord": "A1"},
                ],
            }
        )
    with pytest.raises(ValueError):
        VariableMap.from_puzzle(
            {"size": 2, "characters": [{"name": "Abel", "coord": "C1"}]}
        )
    vm = VariableMap.from_puzzle({"size": 2})
    with pytest.raises(KeyError):
        vm.get_primary("Z9")


# ---------------------------------------------------------------------------
# Core CNF Encoder tests with Dict inputs -> Assert standard CNF clauses
# ---------------------------------------------------------------------------


def test_encode_fact_same_different_dict_inputs() -> None:
    vm = VariableMap.from_characters(["Abel", "Bea", "Clara"])
    encoder = CNFEncoder(vm)
    a = vm.get_primary("Abel")  # 1
    b = vm.get_primary("Bea")  # 2
    c = vm.get_primary("Clara")  # 3

    # FACT (Criminal & Innocent)
    assert encoder.encode_clue({"type": "FACT", "target": "Abel", "status": "CRIMINAL"}) == [[a]]
    assert encoder.encode_clue(
        {"type": "FACT", "params": {"target": "Bea", "status": "INNOCENT"}}
    ) == [[-b]]

    # SAME: (A <-> B) === (-A v B) & (A v -B)
    same_clauses = encoder.encode_clue({"type": "SAME", "targets": ["Abel", "Bea"]})
    assert same_clauses == [[-a, b], [a, -b]]

    # DIFFERENT: (B xor C) === (-B v -C) & (B v C)
    diff_clauses = encoder.encode_clue(
        {"type": "DIFFERENT", "target1": "Bea", "target2": "Clara"}
    )
    assert diff_clauses == [[-b, -c], [b, c]]
    assert vm.num_auxiliary == 0


def test_encode_cardinality_boundary_cases() -> None:
    vm = VariableMap.from_characters(["A1", "B1", "C1"])
    encoder = CNFEncoder(vm)
    v1, v2, v3 = 1, 2, 3
    region = ["A1", "B1", "C1"]

    # k = 0 and k = n produce direct unit clauses or empty (tautology) with 0 aux vars
    assert encoder.encode_clue({"type": "EXACTLY", "k": 0, "region": region}) == [[-v1], [-v2], [-v3]]
    assert encoder.encode_clue({"type": "NO", "region": region}) == [[-v1], [-v2], [-v3]]
    assert encoder.encode_clue({"type": "EXACTLY", "k": 3, "region": region}) == [[v1], [v2], [v3]]
    assert encoder.encode_clue({"type": "AT_MOST", "k": 0, "region": region}) == [[-v1], [-v2], [-v3]]
    assert encoder.encode_clue({"type": "AT_MOST", "k": 3, "region": region}) == []
    assert encoder.encode_clue({"type": "AT_LEAST", "k": 0, "region": region}) == []
    assert encoder.encode_clue({"type": "AT_LEAST", "k": 3, "region": region}) == [[v1], [v2], [v3]]
    assert vm.num_auxiliary == 0


@pytest.mark.parametrize("encoding", ["sequential", "binomial"])
@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8])
def test_cardinality_truth_tables_exhaustive(encoding: str, n: int) -> None:
    """Exhaustively verify EXACTLY, AT_LEAST, and AT_MOST against all 2^n assignments."""
    names = [f"P{i}" for i in range(1, n + 1)]
    for k in range(0, n + 1):
        for clue_type, predicate in (
            ("EXACTLY", lambda s, target=k: s == target),
            ("AT_LEAST", lambda s, target=k: s >= target),
            ("AT_MOST", lambda s, target=k: s <= target),
        ):
            vm = VariableMap.from_characters(names)
            encoder = CNFEncoder(vm, cardinality_encoding=encoding)
            clauses = encoder.encode_clue(
                {"type": clue_type, "k": k, "region": names}
            )

            expected = {
                vals
                for vals in itertools.product((False, True), repeat=n)
                if predicate(sum(1 for v in vals if v))
            }
            actual, multiplicity = _satisfying_primary_projections(
                clauses, vm.primary_ids, vm.auxiliary_ids
            )
            assert actual == expected, f"Mismatch for {encoding} {clue_type}({k}, n={n})"
            # Verify sequential counter maintains 1-to-1 aux assignment per valid primary model
            if encoding == "sequential":
                assert all(count == 1 for count in multiplicity.values())


def test_encode_grid_regions_in_clues() -> None:
    puzzle = {
        "size": 3,
        "characters": {
            "A1": "Abel",
            "B1": "Bea",
            "C1": "Clara",
            "A2": "Derek",
            "B2": "Eliza",
            "C2": "Franz",
            "A3": "Grant",
            "B3": "Hannah",
            "C3": "Ivy",
        },
    }
    vm = VariableMap.from_puzzle(puzzle)
    encoder = CNFEncoder(vm, cardinality_encoding="binomial")

    # Row 1: Abel(1), Bea(2), Clara(3) -> AT_MOST 1
    row_clauses = encoder.encode_clue(
        {"type": "AT_MOST", "k": 1, "region": {"kind": "row", "row": 1}}
    )
    assert row_clauses == [[-1, -2], [-1, -3], [-2, -3]]

    # Column B: Bea(2), Eliza(5), Hannah(8) -> AT_LEAST 2
    col_clauses = encoder.encode_clue(
        {"type": "AT_LEAST", "k": 2, "region": {"kind": "column", "column": "B"}}
    )
    assert col_clauses == [[2, 5], [2, 8], [5, 8]]

    # Neighbors of A1: Bea(2), Derek(4), Eliza(5) -> EXACTLY 3
    nbr_clauses = encoder.encode_clue(
        {"type": "EXACTLY", "k": 3, "region": {"kind": "neighbors", "cell": "A1"}}
    )
    assert nbr_clauses == [[2], [4], [5]]

    # String region shorthand
    shorthand_clauses = encoder.encode_clue(
        {"type": "EXACTLY", "k": 0, "region": "row:3"}
    )
    g = vm.get_primary("Grant")
    h = vm.get_primary("Hannah")
    i = vm.get_primary("Ivy")
    assert shorthand_clauses == [[-g], [-h], [-i]]


def test_clue_validation_errors() -> None:
    vm = VariableMap.from_puzzle({"size": 3})
    encoder = CNFEncoder(vm)

    invalid_clues = [
        {"type": "UNKNOWN", "target": "A1"},
        {"type": "FACT", "target": "A1", "status": "MAYBE"},
        {"type": "FACT", "target": "Z9", "status": "CRIMINAL"},
        {"type": "SAME", "targets": ["A1"]},
        {"type": "SAME", "targets": ["A1", "A1"]},
        {"type": "DIFFERENT", "target1": "B1", "target2": "B1"},
        {"type": "EXACTLY", "k": -1, "region": {"kind": "row", "row": 1}},
        {"type": "EXACTLY", "k": 4, "region": {"kind": "row", "row": 1}},
        {"type": "AT_LEAST", "k": True, "region": ["A1", "B1"]},
        {"type": "AT_MOST", "k": 1, "region": []},
        {"type": "AT_MOST", "k": 1, "region": ["A1", "a1"]},
        {"type": "AT_MOST", "k": 1, "region": {"kind": "row", "row": 9}},
        {"type": "AT_MOST", "k": 1, "region": {"kind": "column", "column": "Z"}},
        {"type": "AT_MOST", "k": 1, "region": {"kind": "neighbors", "cell": "Z9"}},
        {"type": "FACT", "target": "A1", "status": "CRIMINAL", "revealed": False},
    ]

    for clue in invalid_clues:
        with pytest.raises(ValueError):
            encoder.encode_clue(clue)


def test_encode_kb_and_public_kb_reporting() -> None:
    vm = VariableMap.from_puzzle(
        {
            "size": 3,
            "characters": {
                "A1": "Abel",
                "B1": "Bea",
                "C1": "Clara",
                "A2": "Derek",
                "B2": "Eliza",
                "C2": "Franz",
                "A3": "Grant",
                "B3": "Hannah",
                "C3": "Ivy",
            },
        }
    )
    encoder = CNFEncoder(vm, cardinality_encoding="sequential")

    public_kb = {
        "revealed_clues": [
            {"type": "EXACTLY", "k": 2, "region": {"kind": "row", "row": 1}, "revealed": True},
            {"type": "SAME", "targets": ["Abel", "Derek"], "revealed": True},
            # Unrevealed clue must never leak into KB_t
            {"type": "FACT", "target": "Ivy", "status": "CRIMINAL", "revealed": False},
        ],
        "proved_verdicts": {
            "Abel": "INNOCENT",
            "Clara": "CRIMINAL",
        },
        # Extra hidden fields must be completely ignored
        "hidden_solution": {"Ivy": "CRIMINAL"},
    }

    encoded: EncodedKB = encoder.encode_public_kb(public_kb, reset_aux=True)
    stats = encoded.stats()
    assert stats["primary_vars"] == 9
    assert stats["auxiliary_vars"] > 0
    assert stats["total_vars"] == stats["primary_vars"] + stats["auxiliary_vars"]
    assert stats["clues"] == 2
    assert stats["verdicts"] == 2
    assert stats["clauses"] == len(encoded.clauses)

    # Check unit clauses for proved verdicts exist
    assert [-vm.get_primary("Abel")] in encoded.clauses
    assert [vm.get_primary("Clara")] in encoded.clauses
    # Unrevealed clue for Ivy must NOT be present
    assert [vm.get_primary("Ivy")] not in encoded.clauses

    dimacs = encoded.to_dimacs()
    assert dimacs.startswith(f"p cnf {encoded.num_total_vars} {encoded.num_clauses}\n")


def test_conflicting_verdicts_rejected() -> None:
    vm = VariableMap.from_puzzle(
        {"size": 2, "characters": {"A1": "Abel", "B1": "Bea", "A2": "Clara", "B2": "Derek"}}
    )
    encoder = CNFEncoder(vm)
    with pytest.raises(ValueError):
        encoder.encode_verdicts({"Abel": "CRIMINAL", "A1": "INNOCENT"})


def test_end_to_end_mini_puzzle_unique_model() -> None:
    """Encode a complete solvable 2x2 puzzle via Dicts and verify unique CNF model."""
    # Ground truth: A1(Abel)=Innocent, B1(Bea)=Criminal, A2(Clara)=Criminal, B2(Derek)=Innocent
    puzzle = {
        "size": 2,
        "characters": [
            {"name": "Abel", "coord": "A1"},
            {"name": "Bea", "coord": "B1"},
            {"name": "Clara", "coord": "A2"},
            {"name": "Derek", "coord": "B2"},
        ],
    }
    clues = [
        {"type": "FACT", "target": "Abel", "status": "INNOCENT"},
        {"type": "EXACTLY", "k": 1, "region": {"kind": "row", "row": 1}},
        {"type": "SAME", "targets": ["Bea", "Clara"]},
        {"type": "DIFFERENT", "targets": ["Clara", "Derek"]},
    ]

    vm = VariableMap.from_puzzle(puzzle)
    encoder = CNFEncoder(vm, cardinality_encoding="sequential")
    kb = encoder.encode_kb(clues, proved_verdicts={"Abel": "INNOCENT"})

    valid_primaries, _ = _satisfying_primary_projections(
        kb.clauses, vm.primary_ids, vm.auxiliary_ids
    )
    # Primary order: Abel(1), Bea(2), Clara(3), Derek(4)
    assert valid_primaries == {(False, True, True, False)}
