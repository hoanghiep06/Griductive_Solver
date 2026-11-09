"""V2 fixed-seed, constraint-guided generation; all candidates SAT-certified.

Pair, overlapping-count, bridge and triangle stages share multiple unresolved
variables. Providers reveal a batch of constraints rather than a one-clue chain.
Reference SAT is authoring-only; production DPLL/encoder stay untouched.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
import os
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.character import Character
from src.core.clue import Clue
from tools.validate_puzzles import ROOT, PUZZLE_IDS, clue_scope, validate_puzzle

DEFAULT_SEED = 20261110
GENERATOR_VERSION = "2.0"
NAMES = ("Abel", "Bea", "Clara", "Derek", "Eliza", "Franz", "Grant", "Hannah", "Ivy",
         "Jonah", "Kira", "Leo", "Maya", "Nora", "Owen", "Petra", "Quinn", "Rosa",
         "Seth", "Tara", "Uma", "Vera", "Will", "Xena", "Yuri")
PROFESSIONS = ("Analyst", "Baker", "Carpenter", "Doctor", "Engineer", "Florist", "Guard",
               "Historian", "Illustrator", "Journalist", "Librarian", "Musician")
TARGET_LABELS = {
    3: ("Tutorial", "Easy", "Easy-Medium", "Medium", "Medium+"),
    4: ("Medium", "Medium", "Medium-Hard", "Hard", "Hard"),
    5: ("Medium-Hard", "Hard", "Hard", "Very Hard", "Very Hard"),
}


def quality_target(size, case):
    return 0 if size == 3 and case <= 2 else 1 if size == 3 else 3 if size == 4 else 6


def _layout(size, case, rng):
    coords = [(r, c) for r in range(size) for c in range(size)]
    if case == 1:
        coords = [(r, c) for r in range(size) for c in (range(size) if r % 2 == 0 else reversed(range(size)))]
    elif case == 2:
        coords = [(r, c) for c in range(size) for r in (range(size) if c % 2 == 0 else reversed(range(size)))]
    elif case == 4:
        coords.sort(key=lambda rc: (min(rc[0], rc[1], size-rc[0]-1, size-rc[1]-1), rc))
    else:
        rng.shuffle(coords)
    return [f"{chr(65+c)}{r+1}" for r, c in coords]


def build_puzzle(size, case, seed=DEFAULT_SEED, attempt=0):
    if size not in (3, 4, 5) or case not in range(1, 6):
        raise ValueError("Require size 3/4/5 and case 1..5")
    # Intentional tutorial/easy references; only these two keep baseline design.
    if size == 3 and case <= 2:
        return json.loads((ROOT / "puzzles_baseline" / f"3x3_{case:02d}.json").read_text())
    rng = random.Random(seed + size*10000 + case*100 + attempt)
    ids = [f"{chr(65+c)}{r+1}" for r in range(size) for c in range(size)]
    path = _layout(size, case, rng)
    if size == 3:
        stages = ["pair", "count"] if case in (3, 4) else ["bridge"]
    elif size == 4:
        stages = {1: ["pair"]*4, 2: ["count"]*4, 3: ["pair", "bridge", "bridge"],
                  4: ["bridge"]*3, 5: ["triangle", "bridge", "bridge"]}[case]
    else:
        stages = {1: ["pair"]*7, 2: ["count", "pair", "count", "count", "pair", "count", "pair"],
                  3: ["bridge"]*4 + ["count"]*2,
                  4: ["bridge"]*5, 5: ["bridge", "triangle", "bridge", "bridge", "bridge"]}[case]
    initial_count = 3 if any(s in {"bridge", "triangle"} for s in stages) else 2
    initial = path[:initial_count]
    remaining = path[initial_count:]
    solution = {cid: bool(rng.getrandbits(1)) for cid in ids}
    characters = [{"id": cid, "name": NAMES[i], "profession": rng.choice(PROFESSIONS),
                   "row": i//size, "col": i%size} for i, cid in enumerate(ids)]
    chars = {c["id"]: Character.from_dict(c) for c in characters}
    providers = list(initial)
    prefix = set(initial)
    by_owner = {}
    region_use = Counter()

    def assign(owner, kind, parameters):
        if owner in by_owner:
            raise RuntimeError("Two clues assigned to one owner")
        by_owner[owner] = {"clue_id": f"CLUE_{owner}", "owner_id": owner,
                           "type": kind, "parameters": parameters}

    def count_clue(unknown, k, known, kind="EXACTLY"):
        # A natural region is usable if precisely these stage variables remain
        # unresolved. Known filler counts are included in the actual threshold.
        specs = [{"region_type": "ROW", "index": i} for i in range(size)]
        specs += [{"region_type": "COLUMN", "index": i} for i in range(size)]
        specs += [{"region_type": "NEIGHBORS", "center": cid} for cid in ids]
        options = []
        for spec in specs:
            scope = clue_scope(Clue("scope", initial[0], "EXACTLY", {"k": 0, **spec}), chars, size)
            if set(scope) - set(known) == set(unknown):
                options.append((spec, scope))
        if options:
            options.sort(key=lambda pair: (region_use[pair[0]["region_type"]], len(pair[1])))
            spec, scope = options[0]
        else:
            fillers = sorted(known, key=ids.index)
            if fillers and case >= 3:
                fillers = rng.sample(fillers, min(len(fillers), (case + len(unknown)) % 3))
            else:
                fillers = []
            scope = sorted(set(unknown) | set(fillers), key=ids.index)
            spec = {"region_type": "EXPLICIT", "cells": scope}
        region_use[spec["region_type"]] += 1
        offset = sum(solution[cid] for cid in scope if cid not in unknown)
        return kind, {"k": k + offset, **spec}

    for stage_index, stage in enumerate(stages):
        width = 3 if stage in {"pair", "count"} else 4
        group, remaining = remaining[:width], remaining[width:]
        if len(group) != width:
            raise RuntimeError("Stage plan exceeds board")
        a, b, c = group[:3]
        x = bool(rng.getrandbits(1))
        solution[a], solution[b] = x, not x
        constraints = []
        closure_owner = None
        if stage in {"pair", "count"}:
            solution[c] = bool(rng.getrandbits(1))
            if stage == "count" or (stage_index % 3 == 1 and case >= 3):
                constraints.append(count_clue([a, b], 1, prefix))
            else:
                constraints.append(("DIFFERENT", {"target1": a, "target2": b}))
            kind = ("EXACTLY", "AT_MOST", "AT_LEAST")[(stage_index+case) % 3]
            if kind == "AT_MOST":
                solution[c] = False
            elif kind == "AT_LEAST":
                solution[c] = True
            constraints.append(count_clue([a, b, c], 1 + solution[c], prefix, kind))
            relation = "SAME" if solution[a] == solution[c] else "DIFFERENT"
            assign(c, relation, {"target1": a, "target2": c})
            closure_owner = c
        elif stage == "bridge":
            d = group[3]
            solution[a] = solution[b] = x
            solution[c], solution[d] = not x, bool(rng.getrandbits(1))
            constraints += [("SAME", {"target1": a, "target2": b})]
            if stage_index % 2:
                constraints.append(count_clue([b, c], 1, prefix))
            else:
                constraints.append(("DIFFERENT", {"target1": b, "target2": c}))
            constraints.append(count_clue([a, c, d], 1 + solution[d], prefix))
            closure_kind = "EXACTLY" if case % 2 else "AT_LEAST" if x else "AT_MOST"
            kind, parameters = count_clue([a, b, c], 1 + x, prefix | {d}, closure_kind)
            assign(d, kind, parameters)
            closure_owner = d
        else:
            d = group[3]
            solution[a] = solution[c] = x
            solution[b] = solution[d] = not x
            constraints += [count_clue([a, b], 1, prefix), count_clue([b, c], 1, prefix),
                            count_clue([a, c, d], 1 + x, prefix)]
        for kind, parameters in constraints:
            owner = providers.pop(0)
            assign(owner, kind, parameters)
        providers.extend(cid for cid in group if cid != closure_owner)
        prefix.update(group)
    # Remaining cards are resolved by late public counting clues. Last free
    # owners anchor initially public statuses, proving full-clue uniqueness.
    for target in remaining:
        owner = providers.pop(0)
        kind, parameters = count_clue([target], int(solution[target]), prefix)
        assign(owner, kind, parameters)
        providers.append(target)
        prefix.add(target)
    for target in initial:
        owner = providers.pop(0)
        assign(owner, "FACT", {"target": target, "status": "CRIMINAL" if solution[target] else "INNOCENT"})
    for owner in providers:
        # Triangle stages have one extra slot; add an overlapping natural count
        # as an alternative clue, then measure any resulting shortcuts honestly.
        spec = {"region_type": "NEIGHBORS", "center": owner, "k": 0}
        scope = clue_scope(Clue("scope", owner, "EXACTLY", spec), chars, size)
        spec["k"] = sum(solution[cid] for cid in scope)
        assign(owner, "EXACTLY", spec)
    return {"schema_version": "1.0", "puzzle_id": f"{size}x{size}_{case:02d}", "grid_size": size,
            "characters": characters, "hidden_solution": solution, "initial_revealed": initial,
            "clues": [by_owner[cid] for cid in ids]}


def generate_dataset(directory, seed=DEFAULT_SEED, max_attempts=40):
    if type(seed) is not int:
        raise TypeError("seed must be integer")
    generated, entries, fingerprints = [], [], set()
    for size in (3, 4, 5):
        for case in range(1, 6):
            target = quality_target(size, case)
            for attempt in range(max_attempts):
                raw = build_puzzle(size, case, seed, attempt)
                report = validate_puzzle(raw)
                fingerprint = report["structural_features"]["wl_fingerprint"]
                if report["difficulty"]["multi_clue_steps"] >= target and fingerprint not in fingerprints:
                    break
            else:
                raise ValueError(f"No certified candidate for {size}x{size}_{case:02d}; existing dataset unchanged")
            fingerprints.add(fingerprint)
            generated.append(raw)
            entries.append({**{key: report[key] for key in (
                "puzzle_id", "size", "criminal_count", "innocent_count", "clue_count", "initial_revealed_count",
                "clue_types", "region_types", "validation_status", "checks", "proof_method")},
                "file": raw["puzzle_id"] + ".json", "generation_seed": seed,
                "generation_attempt": attempt, "generator_version": GENERATOR_VERSION,
                "target_difficulty": TARGET_LABELS[size][case-1], "difficulty_label": report["difficulty"]["label"],
                "difficulty_measured": True, "difficulty_is_subjective_heuristic": True,
                "difficulty": report["difficulty"], "structural_features": report["structural_features"],
                "minimum_multi_clue_target": target, "multi_clue_target_met": True,
                "deduction_steps": len(report["reveal_proof"])})
            print(raw["puzzle_id"], 'multi=', report['difficulty']['multi_clue_steps'],
                  'triple=', report['difficulty']['three_plus_clue_steps'], 'attempt=', attempt, flush=True)
    types = set().union(*(set(e["clue_types"]) for e in entries))
    regions = set().union(*(set(e["region_types"]) for e in entries))
    if types != {"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST"} or regions != {"ROW", "COLUMN", "NEIGHBORS", "EXPLICIT"}:
        raise ValueError("Batch coverage failed; existing dataset unchanged")
    # Nothing is written until ALL candidates pass. Stage bytes in a sibling
    # directory and use atomic per-file replacement; errors restore old bytes.
    directory = Path(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    payload = {raw['puzzle_id']+'.json': json.dumps(raw, indent=2, ensure_ascii=False)+'\n' for raw in generated}
    payload['manifest.json'] = json.dumps({"schema_version": "1.0", "generator_version": GENERATOR_VERSION,
        "generator_seed": seed, "max_attempts": max_attempts, "puzzles": entries}, indent=2, ensure_ascii=False)+'\n'
    old = {name: (directory/name).read_bytes() if (directory/name).exists() else None for name in payload}
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory.parent, prefix='.puzzle-candidates-') as temp:
        staging = Path(temp)
        for name, data in payload.items():
            (staging/name).write_text(data, encoding='utf-8')
        try:
            for name in payload:
                os.replace(staging/name, directory/name)
        except BaseException:
            for name, data in old.items():
                if data is None:
                    (directory/name).unlink(missing_ok=True)
                else:
                    (directory/name).write_bytes(data)
            raise
    return entries


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'puzzles')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--max-attempts', type=int, default=40)
    args=parser.parse_args()
    generate_dataset(args.output_dir,args.seed,args.max_attempts)
    print('15 SAT-certified puzzles published. Team DPLL/CNF benchmark remains BLOCKED.')

if __name__=='__main__':
    main()
