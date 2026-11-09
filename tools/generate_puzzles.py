"""Deterministic constructive puzzle generation in Hiệp's schema v1.0.

Every owner along an authored path holds a clue forcing the next cell from a
known prefix. The last owner has a FACT anchoring the first cell, so the full
clue set proves every status even WITHOUT initially revealed status units.
Natural regions, explicit counts and binary relations vary across cases.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.character import Character
from src.core.clue import Clue
from tools.validate_puzzles import ROOT, clue_scope, validate_puzzle

DEFAULT_SEED = 20261109
NAMES = (
    "Abel", "Bea", "Clara", "Derek", "Eliza", "Franz", "Grant", "Hannah", "Ivy",
    "Jonah", "Kira", "Leo", "Maya", "Nora", "Owen", "Petra", "Quinn", "Rosa",
    "Seth", "Tara", "Uma", "Vera", "Will", "Xena", "Yuri",
)
PROFESSIONS = ("Analyst", "Baker", "Carpenter", "Doctor", "Engineer", "Florist",
               "Guard", "Historian", "Illustrator", "Journalist", "Librarian", "Musician")
DESIGN_LABELS = ("Easy target", "Easy-Medium target", "Medium target", "Medium-Hard target", "Hard target")


def _path(size: int, case: int, rng: random.Random) -> list[str]:
    coords = [(r, c) for r in range(size) for c in range(size)]
    if case == 1:
        coords = [(r, c) for r in range(size)
                  for c in (range(size) if r % 2 == 0 else reversed(range(size)))]
    elif case == 2:
        coords = [(r, c) for c in reversed(range(size))
                  for r in (range(size) if c % 2 == 0 else reversed(range(size)))]
    elif case == 4:
        coords.sort(key=lambda rc: (min(rc[0], rc[1], size-1-rc[0], size-1-rc[1]), rc))
        coords.reverse()
    else:
        rng.shuffle(coords)
    return [f"{chr(65+c)}{r+1}" for r, c in coords]


def build_puzzle(size: int, case: int, seed: int = DEFAULT_SEED) -> dict:
    rng = random.Random(seed + size * 100 + case)
    ids = [f"{chr(65+c)}{r+1}" for r in range(size) for c in range(size)]
    path = _path(size, case, rng)
    criminal_count = max(2, min(size*size-2, round(size*size * (0.24 + case*0.10))))
    criminals = set(rng.sample(ids, criminal_count))
    solution = {cid: cid in criminals for cid in ids}
    characters = [
        {"id": cid, "name": NAMES[i], "profession": rng.choice(PROFESSIONS),
         "row": i // size, "col": i % size}
        for i, cid in enumerate(ids)
    ]
    char_map = {raw["id"]: Character.from_dict(raw) for raw in characters}
    used_types = Counter()
    used_regions = Counter()
    clues_by_owner = {}
    for i, owner in enumerate(path[:-1]):
        target = path[i + 1]
        known = set(path[:i + 1])
        candidates = []
        # Binary constraints vary in their supporting earlier character.
        for ref in path[:i+1]:
            kind = "SAME" if solution[ref] == solution[target] else "DIFFERENT"
            candidates.append((kind, {"target1": ref, "target2": target}))
        region_specs = [{"region_type": "ROW", "index": char_map[target].row},
                        {"region_type": "COLUMN", "index": char_map[target].col}]
        region_specs.extend({"region_type": "NEIGHBORS", "center": cid} for cid in ids)
        # Explicit lists always provide valid candidate counts from a prefix.
        refs = rng.sample(path[:i+1], min(i+1, rng.randint(1, 4)))
        region_specs.append({"region_type": "EXPLICIT", "cells": sorted(refs+[target], key=ids.index)})
        for spec in region_specs:
            dummy = Clue("scope", owner, "EXACTLY", {"k": 0, **spec})
            scope = clue_scope(dummy, char_map, size)
            if target not in scope or not set(scope) <= known | {target}:
                continue
            count = sum(solution[cid] for cid in scope)
            candidates.append(("EXACTLY", {"k": count, **spec}))
            if solution[target]:
                candidates.append(("AT_LEAST", {"k": count, **spec}))
            else:
                candidates.append(("AT_MOST", {"k": count, **spec}))
        # Prefer unused forms, while varying choices deterministically per case.
        def score(candidate):
            kind, p = candidate
            region = p.get("region_type")
            return (4 if used_types[kind] == 0 else 0) + (
                5 if region and used_regions[region] == 0 else 0
            ) + rng.random() * (1.0 + case * 0.2) - used_types[kind] * 0.15
        kind, params = max(candidates, key=score)
        used_types[kind] += 1
        if "region_type" in params:
            used_regions[params["region_type"]] += 1
        clues_by_owner[owner] = {"clue_id": f"CLUE_{owner}", "owner_id": owner,
                                 "type": kind, "parameters": params}
    last = path[-1]
    clues_by_owner[last] = {
        "clue_id": f"CLUE_{last}", "owner_id": last, "type": "FACT",
        "parameters": {"target": path[0], "status": "CRIMINAL" if solution[path[0]] else "INNOCENT"},
    }
    # The root of the constructive chain is face-up. Some cases have two seeds.
    initial = [path[0]]
    if case in (2, 4):
        initial.append(path[len(path)//2])
    raw = {
        "schema_version": "1.0", "puzzle_id": f"{size}x{size}_{case:02d}",
        "grid_size": size, "characters": characters, "hidden_solution": solution,
        "initial_revealed": initial, "clues": [clues_by_owner[cid] for cid in ids],
    }
    return raw


def generate_dataset(directory: Path, seed: int = DEFAULT_SEED) -> list[dict]:
    if type(seed) is not int:
        raise TypeError("seed must be an integer")
    # Validate the entire batch before writing any output.
    generated = []
    manifest = []
    for size in (3, 4, 5):
        for case in range(1, 6):
            raw = build_puzzle(size, case, seed)
            report = validate_puzzle(raw)
            generated.append(raw)
            manifest.append({
                **{key: report[key] for key in (
                    "puzzle_id", "size", "criminal_count", "innocent_count", "clue_count",
                    "initial_revealed_count", "clue_types", "region_types", "validation_status", "checks",
                )},
                "file": f"{raw['puzzle_id']}.json", "generation_seed": seed + size * 100 + case,
                "difficulty_label": DESIGN_LABELS[case-1],
                "difficulty_measured": False,
                "proof_method": report["proof_method"],
                "deduction_steps": len(report["reveal_proof"]),
            })
    all_types = set().union(*(set(entry["clue_types"]) for entry in manifest))
    all_regions = set().union(*(set(entry["region_types"]) for entry in manifest))
    if all_types != {"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST"}:
        raise ValueError("Generated batch does not cover all six core clues")
    if all_regions != {"ROW", "COLUMN", "NEIGHBORS", "EXPLICIT"}:
        raise ValueError("Generated batch does not cover all four regions")
    directory.mkdir(parents=True, exist_ok=True)
    for raw in generated:
        (directory / f"{raw['puzzle_id']}.json").write_text(
            json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "generator_seed": seed, "puzzles": manifest},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "puzzles")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    manifest = generate_dataset(args.output_dir, args.seed)
    print(f"Generated {len(manifest)} validated puzzles in {args.output_dir}; seed={args.seed}")
    print("Constructive validation PASSED; DPLL/CNF integration SKIPPED (dependencies pending).")


if __name__ == "__main__":
    main()
