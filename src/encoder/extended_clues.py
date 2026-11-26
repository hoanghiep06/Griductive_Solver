"""
extended_clues.py - Ma hoa cac loai manh moi mo rong sang CNF.

  * PARITY        : so o Guilty trong mot tap o la chan / le.
  * COUNT_COMPARE : so sanh so o Guilty cua hai vung (<, <=, ==, !=, >=, >).
  * IMPLIES       : dieu kien keo theo  (o A co trang thai X)  =>  (o B co trang thai Y).

Giao dien (GIA DINH, xem ASSUMPTIONS.md):
  vm.cell_var(r, c) -> int   # bien DIMACS (>0) cua IsGuilty(r, c)
  vm.new_aux()      -> int   # bien phu moi (>0), dung cho Tseitin
Ket qua: list[list[int]] - cac clause theo quy uoc DIMACS.

Dac diem ma hoa: moi bien phu duoc dinh nghia DAY DU (<=>) theo cac bien o,
nen voi mot ban co day du, gia tri bien phu bi xac dinh duy nhat. Dieu nay
giu nguyen so nghiem khi UniquenessChecker chi can chan cac bien o.
IMPLIES khong dung bien phu: chi la mot clause [-A, B].
"""
from __future__ import annotations

from typing import Any, List, Mapping, Sequence, Union

from .semantic_eval import (
    clue_params, clue_type_name, normalize_cells, normalize_op, normalize_parity,
    normalize_status,
)

Clause = List[int]
__all__ = [
    "EXTENDED_TYPES", "is_extended", "encode_extended",
    "encode_parity", "encode_count_compare", "encode_implies", "build_counter",
]

EXTENDED_TYPES = frozenset({"PARITY", "COUNT_COMPARE", "IMPLIES"})


class _Const:
    """Hang Boolean (khong dung True/False cua Python de khong lan voi literal 1)."""
    def __init__(self, v: bool): self.v = v
    def __repr__(self): return "TRUE" if self.v else "FALSE"


_T, _F = _Const(True), _Const(False)
Lit = Union[int, _Const]


def _neg(l: Lit) -> Lit:
    if l is _T: return _F
    if l is _F: return _T
    return -l  # type: ignore[operator]


def _emit(clauses: List[Clause], lits: Sequence[Lit]) -> None:
    """Them clause, rut gon hang so; bo qua clause hang dung / tautology."""
    out: List[int] = []
    for l in lits:
        if l is _T:
            return
        if l is _F:
            continue
        out.append(l)  # type: ignore[arg-type]
    s = set(out)
    if any(-l in s for l in s):
        return
    clauses.append(out)  # out rong = clause rong = UNSAT (dung ngu nghia)


def _cell_lits(vm, cells) -> List[int]:
    cells = list(cells)
    if not cells:
        raise ValueError("Extended clue regions must not be empty")
    if hasattr(vm, "get_primary"):
        literals = []
        for cell in cells:
            literal = (vm.get_primary(cell) if isinstance(cell, str)
                       else vm.cell_var(*normalize_cells([cell])[0]))
            if literal not in literals:
                literals.append(literal)
        return literals
    return [vm.cell_var(r, c) for r, c in normalize_cells(cells)]


# --------------------------------------------------------------------------- #
# PARITY: chuoi XOR (Tseitin)
# --------------------------------------------------------------------------- #
def encode_parity(vm, cells, parity) -> List[Clause]:
    """So o Guilty trong `cells` la chan ('even') hoac le ('odd')."""
    want_odd = normalize_parity(parity)
    clauses: List[Clause] = []
    p: Lit = _F  # p = XOR cac bien da xet (True <=> so luong le)
    for x in _cell_lits(vm, cells):
        if p is _F:
            p = x
            continue
        q = vm.new_aux()  # q <=> p XOR x
        _emit(clauses, [-q, p, x])
        _emit(clauses, [-q, _neg(p), -x])
        _emit(clauses, [q, _neg(p), x])
        _emit(clauses, [q, p, -x])
        p = q
    _emit(clauses, [p if want_odd else _neg(p)])
    return clauses


# --------------------------------------------------------------------------- #
# Bo dem don phan (unary counter) day du: ge[j] <=> (so bien dung >= j)
# --------------------------------------------------------------------------- #
def build_counter(vm, lits: Sequence[int], clauses: List[Clause]) -> List[Lit]:
    """
    Tra ve `ge` co do dai n+1: ge[0] = TRUE, ge[j] (1<=j<=n) la bien phu
    thoa ge[j] <=> (co it nhat j literal trong `lits` dung).
    Truy hoi: ge_i[j] <=> ge_{i-1}[j]  OR  (x_i AND ge_{i-1}[j-1]).
    """
    prev: List[Lit] = [_T]
    for x in lits:
        cur: List[Lit] = [_T]
        for j in range(1, len(prev) + 1):
            b: Lit = prev[j] if j < len(prev) else _F
            c: Lit = prev[j - 1]
            a = vm.new_aux()
            _emit(clauses, [_neg(b), a])            # b        -> a
            _emit(clauses, [-x, _neg(c), a])        # x & c    -> a
            _emit(clauses, [-a, b, x])              # a        -> b | x
            _emit(clauses, [-a, b, c])              # a        -> b | c
            cur.append(a)
        prev = cur
    return prev


def _ge(arr: Sequence[Lit], j: int) -> Lit:
    """'dem >= j' voi bien ngoai khoang: j<=0 -> TRUE, j>n -> FALSE."""
    if j <= 0: return _T
    if j >= len(arr): return _F
    return arr[j]


def _imply_gt(clauses, A, B, guard: Sequence[Lit] = ()) -> None:
    """guard -> (dem A > dem B):  moi k=0..|B|: (B>=k) -> (A>=k+1)."""
    for k in range(0, len(B)):
        _emit(clauses, [*guard, _neg(_ge(B, k)), _ge(A, k + 1)])


def _imply_ge(clauses, A, B, guard: Sequence[Lit] = ()) -> None:
    """guard -> (dem A >= dem B):  moi k=1..|B|-1: (B>=k) -> (A>=k)."""
    for k in range(1, len(B)):
        _emit(clauses, [*guard, _neg(_ge(B, k)), _ge(A, k)])


# --------------------------------------------------------------------------- #
# COUNT_COMPARE
# --------------------------------------------------------------------------- #
def encode_count_compare(vm, region_a, region_b, op: str) -> List[Clause]:
    """(#Guilty trong A) <op> (#Guilty trong B), op in {<,<=,==,!=,>=,>}."""
    op = normalize_op(op)
    clauses: List[Clause] = []
    A = build_counter(vm, _cell_lits(vm, region_a), clauses)
    B = build_counter(vm, _cell_lits(vm, region_b), clauses)
    if op == ">":
        _imply_gt(clauses, A, B)
    elif op == "<":
        _imply_gt(clauses, B, A)
    elif op == ">=":
        _imply_ge(clauses, A, B)
    elif op == "<=":
        _imply_ge(clauses, B, A)
    elif op == "==":
        _imply_ge(clauses, A, B)
        _imply_ge(clauses, B, A)
    else:  # "!=" : g -> A>B, l -> A<B, g | l
        g, l = vm.new_aux(), vm.new_aux()
        _imply_gt(clauses, A, B, guard=[-g])
        _imply_gt(clauses, B, A, guard=[-l])
        _emit(clauses, [g, l])
    return clauses


# --------------------------------------------------------------------------- #
# IMPLIES: (A co trang thai sa) => (B co trang thai sb)   ==   clause [-LA, LB]
# --------------------------------------------------------------------------- #
def _literal_from_spec(vm, spec: Any) -> int:
    """{'target': <o>, 'status': 'CRIMINAL'|'INNOCENT'} -> literal DIMACS."""
    if not isinstance(spec, Mapping):
        raise ValueError(f"IMPLIES operand must be an object with target/status, got {spec!r}")
    target = spec.get("target", spec.get("cell"))
    status = spec.get("status", spec.get("value"))
    if target is None or status is None:
        raise ValueError(f"IMPLIES operand requires 'target' and 'status': {spec!r}")
    var = _cell_lits(vm, [target])[0]
    return var if normalize_status(status) else -var


def encode_implies(vm, antecedent, consequent) -> List[Clause]:
    """NEU antecedent THI consequent. Hai ve phai la hai o khac nhau."""
    a = _literal_from_spec(vm, antecedent)
    b = _literal_from_spec(vm, consequent)
    if abs(a) == abs(b):
        raise ValueError("IMPLIES requires two distinct cells")
    clauses: List[Clause] = []
    _emit(clauses, [-a, b])
    return clauses


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def is_extended(clue: Any) -> bool:
    return clue_type_name(clue) in EXTENDED_TYPES


def encode_extended(clue: Any, vm) -> List[Clause]:
    """Ma hoa mot manh moi mo rong (PARITY / COUNT_COMPARE / IMPLIES) sang CNF."""
    name, p = clue_type_name(clue), clue_params(clue)
    if name == "PARITY":
        return encode_parity(vm, p["cells"], p["parity"])
    if name == "COUNT_COMPARE":
        return encode_count_compare(vm, p["region_a"], p["region_b"], p["op"])
    if name == "IMPLIES":
        return encode_implies(vm, p["antecedent"], p["consequent"])
    raise ValueError(f"{name!r} khong phai manh moi mo rong")