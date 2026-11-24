"""Constructive, seeded campaign motifs with public reveal dependencies.

Every stage has a guaranteed entry deduction from two/three clues, followed
by a new clue which resolves the stage's initially ambiguous pair. Final
publication additionally certifies the *actual* deduction path and difficulty.
"""

from collections import Counter
import random

from src.core.character import Character
from src.core.clue import Clue
from src.core.regions import SPATIAL_REGIONS
from tools.validate_puzzles import clue_scope

ARCHETYPES = {
    1: ("local_counts", "Đếm lân cận"),
    2: ("global_finale", "Tổng toàn bàn · Chốt hạ"),
    3: ("category_groups", "Nghề nghiệp & vị trí"),
    4: ("compare_parity", "So sánh & chẵn/lẻ"),
    5: ("conditional_links", "Điều kiện liên kết chéo"),
}


def build_archetype(size, case, characters, seed, attempt):
    rng = random.Random(seed + size * 10000 + case * 100 + attempt)
    ids = [c["id"] for c in characters]
    chars = {c["id"]: Character.from_dict(c) for c in characters}
    path = rng.sample(ids, len(ids))
    finale = ids[-1] if case == 2 else None
    if finale:
        path.remove(finale)
    group_spec = None
    pair = []
    if case == 3:
        group_spec = {"region_type": "CORNERS" if size == 3 else "CENTER"}
        if size == 5:
            groups = Counter(c["profession"] for c in characters)
            profession = next((p for p, n in sorted(groups.items()) if 2 <= n <= 4), None)
            if profession:
                group_spec = {"region_type": "PROFESSION", "profession": profession,
                              "cells": [c["id"] for c in characters if c["profession"] == profession]}
            else:
                group_spec = {"region_type": "CORNERS"}
        scope = list(clue_scope(Clue("scope", ids[0], "EXACTLY", {"k": 0, **group_spec}), chars, size))
        rng.shuffle(scope)
        pair, initial = scope[:2], scope[2:]
        for cid in path:
            if len(initial) >= 3:
                break
            if cid not in initial and cid not in pair:
                initial.append(cid)
        remaining = [cid for cid in path if cid not in initial and cid not in pair]
        # Put outer cells late so the border becomes a useful remaining-count
        # region after the interior group has already been resolved.
        remaining.sort(key=lambda cid: chars[cid].row in (0, size - 1) or chars[cid].col in (0, size - 1))
        remaining = pair + remaining
    else:
        count = 4 if finale and size >= 4 else 3
        initial, remaining = path[:count], path[count:]
    solution = {cid: bool(rng.getrandbits(1)) for cid in ids}
    # Reference groups for comparison clues have at least two true literals
    # and one false literal, without tying character metadata to an answer.
    for cid, value in zip(initial, (True, True, False)):
        solution[cid] = value
    if finale:
        solution[finale] = True
    global_owner = initial[0] if finale else None
    providers = [cid for cid in initial if cid != global_owner]
    prefix = set(initial)
    by_owner = {}
    used_regions = Counter()

    def assign(owner, kind, parameters):
        if owner in by_owner:
            raise RuntimeError("Clue owner was already assigned")
        by_owner[owner] = {"clue_id": f"CLUE_{owner}", "owner_id": owner,
                           "type": kind, "parameters": parameters}

    def count_clue(unknown, k, known, kind="EXACTLY", forced_spec=None):
        if case == 4:
            truths = [cid for cid in ids if cid in known and solution[cid]]
            falsehoods = [cid for cid in ids if cid in known and not solution[cid]]
            if k <= len(truths):
                reference = truths[:k] + falsehoods[:1]
                if reference:
                    op = {"EXACTLY": "==", "AT_MOST": "<=", "AT_LEAST": ">="}[kind]
                    return "COUNT_COMPARE", {"region_a": list(unknown), "region_b": reference, "op": op}
        specs = [{"region_type": "ROW", "index": i} for i in range(size)]
        specs += [{"region_type": "COLUMN", "index": i} for i in range(size)]
        specs += [{"region_type": "NEIGHBORS", "center": cid} for cid in ids]
        specs += [{"region_type": region} for region in sorted(SPATIAL_REGIONS)]
        if not finale:
            specs += [{"region_type": "ALL"}]
        professions = sorted({c["profession"] for c in characters})
        specs += [{"region_type": "PROFESSION", "profession": p,
                   "cells": [c["id"] for c in characters if c["profession"] == p]} for p in professions]
        if forced_spec:
            specs = [forced_spec]
        options = []
        for spec in specs:
            scope = clue_scope(Clue("scope", ids[0], "EXACTLY", {"k": 0, **spec}), chars, size)
            if len(scope) >= 2 and set(scope) - set(known) == set(unknown):
                themed = spec["region_type"] in SPATIAL_REGIONS | {"PROFESSION"}
                options.append(((0 if case == 3 and spec["region_type"] == "BORDER" else 1 if case == 3 and themed else 2,
                                 used_regions[spec["region_type"]], len(scope)), spec, scope))
        if options:
            _, spec, scope = min(options, key=lambda item: item[0])
        else:
            fillers = [cid for cid in ids if cid in known][:1]
            scope = list(dict.fromkeys([*unknown, *fillers]))
            spec = {"region_type": "EXPLICIT", "cells": scope}
        used_regions[spec["region_type"]] += 1
        offset = sum(solution[cid] for cid in scope if cid not in unknown)
        return kind, {"k": int(k + offset), **spec}

    def relation(owner, source, target):
        if case == 5:
            assign(owner, "IMPLIES", {
                "antecedent": {"target": source, "status": "CRIMINAL" if solution[source] else "INNOCENT"},
                "consequent": {"target": target, "status": "CRIMINAL" if solution[target] else "INNOCENT"},
            })
        else:
            assign(owner, "SAME" if solution[source] == solution[target] else "DIFFERENT",
                   {"target1": source, "target2": target})

    stage = 0
    while len(remaining) >= 3:
        bridge = len(remaining) >= 4 and len(providers) >= 3 and size >= 4 and not (case == 3 and stage == 0)
        width = 4 if bridge else 3
        group, remaining = remaining[:width], remaining[width:]
        a, b, c = group[:3]
        x = bool(rng.getrandbits(1))
        constraints = []
        if bridge:
            d = group[3]
            solution[a] = solution[b] = x
            solution[c], solution[d] = not x, bool(rng.getrandbits(1))
            constraints.append(("SAME", {"target1": a, "target2": b}))
            constraints.append(("DIFFERENT", {"target1": b, "target2": c}))
            if case in {4, 5}:
                constraints.append(("PARITY", {"cells": [a, c, d],
                                               "parity": "even" if solution[d] else "odd"}))
            else:
                constraints.append(count_clue([a, c, d], 1 + solution[d], prefix))
            if case == 5:
                relation(d, d, a)
            else:
                assign(d, *count_clue([a, b, c], 1 + x, prefix | {d}))
            closure = d
        else:
            solution[a], solution[b], solution[c] = x, not x, bool(rng.getrandbits(1))
            if case == 3 and stage == 0:
                constraints.append(count_clue([a, b], 1, prefix, forced_spec=group_spec))
            elif case == 4:
                constraints.append(("PARITY", {"cells": [a, b], "parity": "odd"}))
            else:
                constraints.append(("DIFFERENT", {"target1": a, "target2": b}))
            if case == 5:
                constraints.append(("PARITY", {"cells": [a, b, c],
                                               "parity": "even" if solution[c] else "odd"}))
            else:
                constraints.append(count_clue([a, b, c], 1 + solution[c], prefix))
            relation(c, c, a)
            closure = c
        for kind, params in constraints:
            assign(providers.pop(0), kind, params)
        providers.extend(cid for cid in group if cid != closure)
        prefix.update(group)
        stage += 1
    for target in remaining:
        assign(providers.pop(0), *count_clue([target], int(solution[target]), prefix))
        providers.append(target)
        prefix.add(target)
    if finale:
        assign(global_owner, "EXACTLY", {"region_type": "ALL", "k": sum(solution.values())})
        providers.append(finale)
    for target in initial:
        assign(providers.pop(0), "FACT", {"target": target,
                                         "status": "CRIMINAL" if solution[target] else "INNOCENT"})
    if providers:
        raise RuntimeError("Stage plan did not consume all clue owners")
    return {"schema_version": "1.0", "puzzle_id": f"{size}x{size}_{case:02d}", "grid_size": size,
            "characters": characters, "hidden_solution": solution, "initial_revealed": initial,
            "clues": [by_owner[cid] for cid in ids]}
