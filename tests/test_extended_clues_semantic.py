"""
Doi chieu CNF (extended_clues) voi Direct Evaluator (semantic_eval) tren MOI
trang thai ban co 3x3 (512 trang thai). Chay:  python -m tests.test_extended_clues_semantic
Voi moi (clue, board): so nghiem day du cua CNF khi co dinh cac bien o phai
bang 1 neu board thoa man, 0 neu khong (=> bien phu duoc xac dinh duy nhat).
"""
import itertools
from src.encoder.extended_clues import encode_extended
from src.encoder.semantic_eval import evaluate_clue, violated_clues

N = 3


class MockVM:
    """Mo phong VariableMap theo ASSUMPTIONS.md."""
    def __init__(self, n):
        self.n, self._next = n, n * n + 1
    def cell_var(self, r, c):
        return r * self.n + c + 1
    def new_aux(self):
        v, self._next = self._next, self._next + 1
        return v
    @property
    def num_vars(self):
        return self._next - 1


def count_models(clauses, num_vars, fixed):
    """Dem so phep gan day du thoa man (DPLL dem, du nho cho test)."""
    def simplify(cls, lit):
        out = []
        for c in cls:
            if lit in c:
                continue
            nc = [l for l in c if l != -lit]
            if not nc:
                return None
            out.append(nc)
        return out

    cls = [list(c) for c in clauses]
    if any(len(c) == 0 for c in cls):
        return 0
    for lit in fixed:
        cls = simplify(cls, lit)
        if cls is None:
            return 0
    assigned = {abs(l) for l in fixed}

    def rec(cls, free):
        unit = next((c[0] for c in cls if len(c) == 1), None)
        if unit is not None:
            nxt = simplify(cls, unit)
            return 0 if nxt is None else rec(nxt, free - {abs(unit)})
        if not cls:
            return 2 ** len(free)
        v = abs(cls[0][0])
        total = 0
        for lit in (v, -v):
            nxt = simplify(cls, lit)
            if nxt is not None:
                total += rec(nxt, free - {v})
        return total

    return rec(cls, set(range(1, num_vars + 1)) - assigned)


def cells(*rc):
    return list(rc)


ROW0 = [(0, 0), (0, 1), (0, 2)]
ROW1 = [(1, 0), (1, 1), (1, 2)]
COL0 = [(0, 0), (1, 0), (2, 0)]
ALL = [(r, c) for r in range(N) for c in range(N)]
CORNERS = [(0, 0), (0, 2), (2, 0), (2, 2)]

CLUES = (
    [{"type": "PARITY", "params": {"cells": cs, "parity": par}}
     for cs in (ROW0, COL0, ALL, CORNERS, [(1, 1)], [(0, 0), (2, 2)])
     for par in ("even", "odd")]
    + [{"type": "COUNT_COMPARE", "params": {"region_a": a, "region_b": b, "op": op}}
       for a, b in ((ROW0, ROW1), (ROW0, COL0), (CORNERS, [(1, 1)]),
                    ([(0, 0)], ALL), (ROW0, [(0, 0), (1, 1)]))
       for op in ("<", "<=", "==", "!=", ">=", ">")]
)


def main():
    boards = [[[bool(bits[r * N + c]) for c in range(N)] for r in range(N)]
              for bits in itertools.product((0, 1), repeat=N * N)]
    for clue in CLUES:
        vm = MockVM(N)
        cnf = encode_extended(clue, vm)
        for board in boards:
            fixed = [vm.cell_var(r, c) if board[r][c] else -vm.cell_var(r, c)
                     for r in range(N) for c in range(N)]
            expect = 1 if evaluate_clue(clue, board) else 0
            got = count_models(cnf, vm.num_vars, fixed)
            assert got == expect, (clue, board, got, expect)
    print(f"OK: {len(CLUES)} manh moi x {len(boards)} ban co - CNF khop Direct Evaluator.")

    # Kiem tra them vai ham tien ich
    b = [[1, 0, 1], [0, 0, 0], [0, 0, 0]]
    assert violated_clues(CLUES[:2], b) == [CLUES[1]] or violated_clues(CLUES[:2], b) == [CLUES[0]]
    print("OK: violated_clues.")


if __name__ == "__main__":
    main()