"""
semantic_eval.py - Direct Semantic Evaluator (khong qua CNF / SAT).

Kiem tra truc tiep mot trang thai ban co DAY DU (moi o da co gia tri
Guilty = True / Innocent = False) co thoa man mot manh moi hay khong.

Dung de:
  * doi chieu (oracle) voi bo ma hoa CNF: CNF + board  <=>  evaluate_clue(...)
  * debug nhanh, sinh / kiem tra cau do.

Quy uoc giao dien (GIA DINH, xem ASSUMPTIONS.md):
  * Board : list[list[bool|0|1]]  hoac  dict[(row, col)] -> bool|0|1
  * Clue  : doi tuong co .type (Enum hoac str) va .params (dict),
            hoac mot dict {"type": ..., "params": {...}} / {"type": ..., **params}
  * Cell  : tuple (row, col), chi so tu 0.

Ho tro region_type: ROW, COLUMN, NEIGHBORS, EXPLICIT, ALL (toan ban),
PROFESSION (danh sach `cells` da duoc validator doi chieu voi nghe nghiep).
"""
from __future__ import annotations

import operator
from src.core.regions import SPATIAL_REGIONS, in_spatial_region
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

Cell = Tuple[int, int]
Board = Any  # Sequence[Sequence[bool|int]] | Mapping[Cell, bool|int]

__all__ = [
    "COMPARE_OPS", "normalize_op", "normalize_cells", "normalize_status", "to_board",
    "count_guilty",
    "check_fact", "check_same", "check_different", "check_exactly",
    "check_parity", "check_count_compare", "check_implies",
    "clue_type_name", "clue_params",
    "register_evaluator", "evaluate_clue", "evaluate_all", "violated_clues",
]

# --------------------------------------------------------------------------- #
# Tien ich dung chung (extended_clues.py cung import tu day de dong nhat ngu nghia)
# --------------------------------------------------------------------------- #
COMPARE_OPS: Dict[str, Callable[[int, int], bool]] = {
    "<": operator.lt, "<=": operator.le, "==": operator.eq,
    "!=": operator.ne, ">=": operator.ge, ">": operator.gt,
}
_OP_ALIASES = {"=": "==", "=>": ">=", "=<": "<=", "<>": "!=", "≠": "!=", "≥": ">=", "≤": "<="}


def normalize_op(op: str) -> str:
    op = str(op).strip()
    op = _OP_ALIASES.get(op, op)
    if op not in COMPARE_OPS:
        raise ValueError(f"Toan tu so sanh khong hop le: {op!r}")
    return op


def normalize_cells(cells: Iterable[Any]) -> List[Cell]:
    """Doi sang list[(r, c)], bo trung (giu thu tu). Vung rong -> ValueError."""
    out: Dict[Cell, None] = {}
    for cell in cells:
        try:
            if isinstance(cell, str):
                from src.core.variable_map import parse_coord
                col, row = parse_coord(cell)
                r, c = row - 1, col - 1
            else:
                r, c = cell
            if type(r) is not int or type(c) is not int or r < 0 or c < 0:
                raise ValueError("Cell coordinates must be non-negative integers")
            out[(r, c)] = None
        except (TypeError, ValueError):
            raise ValueError(f"O khong hop le (can (row, col)): {cell!r}") from None
    if not out:
        raise ValueError("Danh sach o / vung khong duoc rong")
    return list(out)


def normalize_parity(parity: Any) -> bool:
    """Tra ve True neu 'odd' (le), False neu 'even' (chan)."""
    if isinstance(parity, str):
        p = parity.strip().lower()
        if p in ("even", "chan", "chẵn"):
            return False
        if p in ("odd", "le", "lẻ"):
            return True
    elif parity in (0, 1) and not isinstance(parity, bool):
        return bool(parity)
    raise ValueError(f"parity khong hop le: {parity!r} (dung 'even' hoac 'odd')")


def normalize_status(status: Any) -> bool:
    """Tra ve True neu Guilty/CRIMINAL, False neu Innocent/INNOCENT."""
    if isinstance(status, bool):
        return status
    if isinstance(status, str):
        s = status.strip().upper()
        if s in ("CRIMINAL", "GUILTY", "TRUE"):
            return True
        if s in ("INNOCENT", "NOT_GUILTY", "FALSE"):
            return False
    raise ValueError(f"status khong hop le: {status!r} (dung 'CRIMINAL' hoac 'INNOCENT')")


def _as_bool(v: Any, cell: Cell) -> bool:
    if isinstance(v, bool):
        return v
    if v in (0, 1) and v is not None and not isinstance(v, str):
        return bool(v)
    raise ValueError(f"Trang thai o {cell} chua day du / khong hop le: {v!r}")


def to_board(board: Board) -> Dict[Cell, bool]:
    """Chuan hoa board ve dict[(r, c)] -> bool. Bat buoc day du (khong co None)."""
    out: Dict[Cell, bool] = {}
    if isinstance(board, Mapping):
        for (r, c), v in board.items():
            out[(int(r), int(c))] = _as_bool(v, (r, c))
    else:
        for r, row in enumerate(board):
            for c, v in enumerate(row):
                out[(r, c)] = _as_bool(v, (r, c))
    if not out:
        raise ValueError("Board rong")
    return out


def _get(b: Dict[Cell, bool], cell: Cell) -> bool:
    try:
        return b[cell]
    except KeyError:
        raise ValueError(f"O {cell} nam ngoai ban co") from None


def count_guilty(board: Board, cells: Iterable[Any]) -> int:
    """So o Guilty trong `cells` (da bo trung)."""
    b = to_board(board)
    return sum(_get(b, c) for c in normalize_cells(cells))


# --------------------------------------------------------------------------- #
# Cac ham kiem tra thuan (pure) cho tung loai manh moi
# --------------------------------------------------------------------------- #
def check_fact(board: Board, cell: Cell, value: bool = True) -> bool:
    """FACT: o `cell` co dung gia tri `value` (True = Guilty)."""
    return _get(to_board(board), (int(cell[0]), int(cell[1]))) == bool(value)


def check_same(board: Board, cells: Iterable[Cell]) -> bool:
    """SAME: tat ca cac o cung tinh chat (cung Guilty hoac cung Innocent)."""
    b = to_board(board)
    vals = {_get(b, c) for c in normalize_cells(cells)}
    return len(vals) == 1


def check_different(board: Board, cells: Iterable[Cell]) -> bool:
    """DIFFERENT: hai o co tinh chat khac nhau (chi nhan dung 2 o)."""
    cs = normalize_cells(cells)
    if len(cs) != 2:
        raise ValueError("DIFFERENT can dung 2 o khac nhau")
    b = to_board(board)
    return _get(b, cs[0]) != _get(b, cs[1])


def check_exactly(board: Board, cells: Iterable[Cell], k: int) -> bool:
    """EXACTLY: dung k o Guilty trong `cells`."""
    return count_guilty(board, cells) == int(k)


def check_parity(board: Board, cells: Iterable[Cell], parity: Any) -> bool:
    """PARITY: so o Guilty trong `cells` la chan ('even') hoac le ('odd')."""
    want_odd = normalize_parity(parity)
    return (count_guilty(board, cells) % 2 == 1) == want_odd


def check_count_compare(board: Board, region_a: Iterable[Cell],
                        region_b: Iterable[Cell], op: str) -> bool:
    """COUNT_COMPARE: (#Guilty trong A) <op> (#Guilty trong B)."""
    b = to_board(board)
    ca = sum(_get(b, c) for c in normalize_cells(region_a))
    cb = sum(_get(b, c) for c in normalize_cells(region_b))
    return COMPARE_OPS[normalize_op(op)](ca, cb)


def _literal_spec(spec: Any) -> Tuple[Cell, bool]:
    """{'target': <o>, 'status': ...} -> ((r, c), gia_tri_mong_doi)."""
    if not isinstance(spec, Mapping):
        raise ValueError(f"IMPLIES can doi tuong {{target, status}}, nhan {spec!r}")
    target = spec.get("target", spec.get("cell"))
    status = spec.get("status", spec.get("value"))
    if target is None or status is None:
        raise ValueError(f"IMPLIES thieu 'target' hoac 'status': {spec!r}")
    return normalize_cells([target])[0], normalize_status(status)


def check_implies(board: Board, antecedent: Mapping[str, Any],
                  consequent: Mapping[str, Any]) -> bool:
    """IMPLIES: neu ve trai dung thi ve phai phai dung (ve trai sai => thoa man)."""
    b = to_board(board)
    (ca, va), (cc, vc) = _literal_spec(antecedent), _literal_spec(consequent)
    if ca == cc:
        raise ValueError("IMPLIES can hai o khac nhau")
    return (_get(b, ca) != va) or (_get(b, cc) == vc)


# --------------------------------------------------------------------------- #
# Doc Clue + dispatch theo loai
# --------------------------------------------------------------------------- #
def clue_type_name(clue: Any) -> str:
    t = clue.get("type") if isinstance(clue, Mapping) else getattr(clue, "clue_type", getattr(clue, "type", None))
    if t is None:
        raise ValueError(f"Manh moi khong co truong 'type': {clue!r}")
    return str(getattr(t, "name", t)).upper()


def clue_params(clue: Any) -> Mapping[str, Any]:
    if isinstance(clue, Mapping):
        return clue.get("parameters", clue.get("params", {k: v for k, v in clue.items() if k != "type"}))
    params = getattr(clue, "parameters", getattr(clue, "params", None))
    if params is None:
        raise ValueError(f"Manh moi khong co truong 'params': {clue!r}")
    return params


_EVALUATORS: Dict[str, Callable[[Board, Mapping[str, Any]], bool]] = {}


def register_evaluator(type_name: str):
    """Decorator dang ky bo danh gia cho loai manh moi moi (de mo rong)."""
    def deco(fn):
        _EVALUATORS[type_name.upper()] = fn
        return fn
    return deco


@register_evaluator("FACT")
def _ev_fact(board, p):
    return check_fact(board, p["cell"], p.get("value", True))


@register_evaluator("SAME")
def _ev_same(board, p):
    return check_same(board, p["cells"])


@register_evaluator("DIFFERENT")
def _ev_different(board, p):
    return check_different(board, p["cells"])


@register_evaluator("EXACTLY")
def _ev_exactly(board, p):
    return check_exactly(board, p["cells"], p["k"])


@register_evaluator("AT_LEAST")
def _ev_at_least(board, p):
    return count_guilty(board, p["cells"]) >= p["k"]


@register_evaluator("AT_MOST")
def _ev_at_most(board, p):
    return count_guilty(board, p["cells"]) <= p["k"]


@register_evaluator("PARITY")
def _ev_parity(board, p):
    return check_parity(board, p["cells"], p["parity"])


@register_evaluator("COUNT_COMPARE")
def _ev_count_compare(board, p):
    return check_count_compare(board, p["region_a"], p["region_b"], p["op"])


@register_evaluator("IMPLIES")
def _ev_implies(board, p):
    return check_implies(board, p["antecedent"], p["consequent"])


def evaluate_clue(clue: Any, board: Board) -> bool:
    """True neu `board` (day du) thoa man `clue`."""
    name = clue_type_name(clue)
    try:
        fn = _EVALUATORS[name]
    except KeyError:
        raise ValueError(f"Chua co bo danh gia cho loai manh moi {name!r}") from None
    p = dict(clue_params(clue))
    if name == "FACT" and "target" in p:
        p = {"cell": normalize_cells([p["target"]])[0],
             "value": p["status"] == "CRIMINAL"}
    elif name in {"SAME", "DIFFERENT"} and "target1" in p:
        p = {"cells": normalize_cells([p["target1"], p["target2"]])}
    elif "region_type" in p:
        b = to_board(board)
        kind = p["region_type"]
        if kind == "ROW":
            cells = [cell for cell in b if cell[0] == p["index"]]
        elif kind == "COLUMN":
            cells = [cell for cell in b if cell[1] == p["index"]]
        elif kind == "NEIGHBORS":
            r, c = normalize_cells([p["center"]])[0]
            cells = [cell for cell in b if cell != (r, c)
                     and abs(cell[0]-r) <= 1 and abs(cell[1]-c) <= 1]
        elif kind in {"EXPLICIT", "PROFESSION"}:
            cells = p["cells"]
        elif kind == "ALL":
            cells = list(b)
        elif kind in SPATIAL_REGIONS:
            size = max(max(r, c) for r, c in b) + 1
            cells = [cell for cell in b if in_spatial_region(kind, *cell, size)]
        else:
            raise ValueError(f"Unknown region type: {kind}")
        if not cells:
            if name == "EXACTLY":
                return p["k"] == 0
            if name == "AT_LEAST":
                return 0 >= p["k"]
            if name == "AT_MOST":
                return 0 <= p["k"]
        p = {"cells": cells, "k": p["k"]}
    return fn(board, p)


def evaluate_all(clues: Iterable[Any], board: Board) -> bool:
    """True neu board thoa man TAT CA manh moi."""
    return not violated_clues(clues, board)


def violated_clues(clues: Iterable[Any], board: Board) -> List[Any]:
    """Danh sach manh moi bi vi pham (huu ich khi debug / kiem tra nghiem)."""
    b = to_board(board)  # chuan hoa mot lan
    return [c for c in clues if not evaluate_clue(c, b)]
