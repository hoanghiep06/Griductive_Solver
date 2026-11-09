"""Authoring/test-only CNF + MiniSat reference; never a production fallback.

The team's encoder and DPLL remain untouched. Counting uses direct combinations
with no auxiliary variables. Selector variables activate clue groups only in
this analysis harness and are excluded from puzzle-variable statistics.
"""
from itertools import combinations

from pysat.solvers import Solver

from src.core.clue import Clue
from src.core.variable_map import VariableMap


def encode_reference(clue, characters, size, variable_map):
    from tools.validate_puzzles import clue_scope
    p = clue.parameters
    if clue.clue_type == "FACT":
        return [[variable_map.to_literal(p["target"], p["status"] == "CRIMINAL")]]
    if clue.clue_type in {"SAME", "DIFFERENT"}:
        a, b = (variable_map.get_var(p[key]) for key in ("target1", "target2"))
        return [[-a, b], [a, -b]] if clue.clue_type == "SAME" else [[a, b], [-a, -b]]
    variables = [variable_map.get_var(cid) for cid in clue_scope(clue, characters, size)]
    k = p["k"]
    result = []
    if clue.clue_type in {"EXACTLY", "AT_MOST"}:
        result.extend([-v for v in group] for group in combinations(variables, k + 1))
    if clue.clue_type in {"EXACTLY", "AT_LEAST"}:
        result.extend(list(group) for group in combinations(variables, len(variables) - k + 1))
    return result


class PublicSAT:
    """Incremental analysis of ONLY the supplied public clues and facts."""

    def __init__(self, clues, characters, size):
        self.variable_map = VariableMap()
        self.variable_map.register_characters(characters.values())
        self.variable_map.freeze_primary_variables()
        self.clues = tuple(clues)
        self.ids = tuple(c.clue_id for c in clues)
        self.fragments = {
            c.clue_id: encode_reference(c, characters, size, self.variable_map) for c in clues
        }
        self.selectors = {cid: self.variable_map.primary_count + i + 1 for i, cid in enumerate(self.ids)}
        guarded = [[-self.selectors[cid], *clause] for cid in self.ids for clause in self.fragments[cid]]
        self.solver = Solver(name="m22", bootstrap_with=guarded)
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.solver.delete()

    def query(self, known, clue_ids=None, assumption=None):
        selected = self.ids if clue_ids is None else tuple(clue_ids)
        if not set(selected) <= set(self.ids):
            raise ValueError("Cannot query an unrevealed clue")
        assumptions = [self.variable_map.to_literal(cid, value) for cid, value in known.items()]
        assumptions.extend(self.selectors[cid] for cid in selected)
        if assumption is not None:
            assumptions.append(assumption)
        self.calls += 1
        return self.solver.solve(assumptions=assumptions)

    def classify(self, known, unresolved):
        if not self.query(known):
            raise ValueError("INCONSISTENT public knowledge")
        forced, unknown = {}, []
        for cid in unresolved:
            variable = self.variable_map.get_var(cid)
            innocent = self.query(known, assumption=-variable)
            criminal = self.query(known, assumption=variable)
            if not innocent and not criminal:
                raise RuntimeError("Invalid reference solver evidence")
            if innocent and criminal:
                unknown.append(cid)
            else:
                forced[cid] = not innocent
        return forced, unknown

    def minimum_support(self, known, target, status):
        """Exact cardinality minimum, preserving EVERY known verdict.

        Enumerate support subsets by increasing size, not merely an irreducible
        UNSAT core. Stored SAT results exhaust every smaller cardinality.
        """
        opposite = self.variable_map.to_literal(target, not status)
        if not self.query(known):
            raise ValueError("Support measured on an inconsistent KB")
        if self.query(known, assumption=opposite):
            raise ValueError("Requested verdict is not publicly entailed")
        # Shrink a witness first to bound exact subset enumeration.
        witness = list(self.ids)
        for cid in self.ids:
            candidate = [other for other in witness if other != cid]
            if not self.query(known, candidate, opposite):
                witness = candidate
        checks = []
        for count in range(len(witness) + 1):
            for subset in combinations(self.ids, count):
                sat = self.query(known, subset, opposite)
                checks.append({"clue_ids": list(subset), "satisfiable": sat})
                if not sat:
                    return {
                        "minimum_clue_support_size": count,
                        "minimal_supporting_clue_ids": list(subset),
                        "opposite_assumption": opposite,
                        "full_kb_satisfiable": True,
                        "full_opposite_satisfiable": False,
                        "minimality_checks": checks,
                    }
        raise RuntimeError("No support witness found")


def unique_reference(puzzle):
    """Two SAT queries; block the returned model on primary variables only."""
    with PublicSAT(puzzle.clues, puzzle.characters_by_id, puzzle.grid_size) as sat:
        if not sat.query({}):
            raise ValueError("UNSAT full clue set")
        model = {abs(lit): lit > 0 for lit in sat.solver.get_model()}
        primary = dict(sat.variable_map.primary_mapping)
        assignment = {cid: model[var] for cid, var in primary.items()}
        block = [-var if assignment[cid] else var for cid, var in primary.items()]
        # Selectors activate all clues but NEVER appear in the blocking clause.
        sat.solver.add_clause(block)
        second = sat.query({})
        if second:
            raise ValueError("AMBIGUOUS: full clue set has at least two primary solutions")
        if assignment != dict(puzzle.hidden_solution):
            raise ValueError("SAT model disagrees with authored key")
        return {"status": "PASSED", "first_sat": True, "second_sat": False,
                "primary_model": assignment, "blocking_clause": block,
                "primary_variables": sat.variable_map.primary_count,
                "auxiliary_variables": 0,
                "full_cnf_clauses": sum(len(fragment) for fragment in sat.fragments.values()),
                "selector_variables_in_analysis_only": len(sat.selectors), "sat_calls": sat.calls}
