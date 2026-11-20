"""Kiểm tra tính duy nhất nghiệm toàn bàn cờ (TV5).

Nguyên lý (Blocking clause):
  1. Tìm nghiệm đầu tiên M₁ bằng DPLLSolver.solve_with_model().
  2. Xây dựng mệnh đề phủ định M₁ (blocking clause):
       ¬M₁ = (¬x₁ ∨ ¬x₂ ∨ … ∨ ¬xₙ)
     trong đó mỗi xᵢ là literal của biến *primary* theo giá trị trong M₁
     (nếu M₁[var]=True thì đưa vào -var, ngược lại +var).
  3. Giải lại CNF ∧ ¬M₁:
       - UNSAT  →  nghiệm duy nhất (UNIQUE).
       - SAT    →  tồn tại ít nhất nghiệm thứ hai (NON_UNIQUE), trả về cả M₂.
  4. Trả về ``UniquenessResult`` bất biến với chi tiết đầy đủ.

Giới hạn rõ ràng:
  - Chỉ hoạt động trên *biến primary* (Character verdicts). Biến auxiliary
    (Tseitin) bị loại khỏi blocking clause vì chúng không thuộc về nghiệm
    của puzzle.
  - Nếu CNF rỗng (không có ràng buộc nào), mọi phép gán đều là nghiệm → NON_UNIQUE.
  - Caller cần đảm bảo CNF đã được mã hóa đầy đủ trước khi gọi hàm này.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


# ---------------------------------------------------------------------------
# Protocol để chấp nhận bất kỳ SAT solver nào (duck-typing)
# ---------------------------------------------------------------------------

class SolverWithModel(Protocol):
    """Solver trả về (bool, model | None) từ solve_with_model()."""

    def solve_with_model(
        self, cnf: Sequence[Sequence[int]]
    ) -> tuple[bool, dict[int, bool] | None]: ...

    def get_stats(self) -> dict[str, float]: ...


# ---------------------------------------------------------------------------
# Kết quả kiểm tra tính duy nhất
# ---------------------------------------------------------------------------

class UniquenessStatus(str, Enum):
    UNIQUE = "UNIQUE"           # Đúng một nghiệm
    NON_UNIQUE = "NON_UNIQUE"   # Có ít nhất 2 nghiệm
    UNSAT = "UNSAT"             # Không có nghiệm nào (KB mâu thuẫn)


@dataclass(frozen=True, slots=True)
class UniquenessResult:
    """Kết quả kiểm tra nghiệm duy nhất.

    Attributes:
        status:         Kết quả tổng thể (UNIQUE / NON_UNIQUE / UNSAT).
        first_model:    Nghiệm đầu tiên M₁ (primary vars), hoặc None nếu UNSAT.
        second_model:   Nghiệm thứ hai M₂ (primary vars), chỉ có khi NON_UNIQUE.
        sat_calls:      Tổng số lần gọi DPLL.
        metrics_m1:     Chỉ số DPLL của lần giải đầu tiên.
        metrics_m2:     Chỉ số DPLL của lần giải thứ hai (None nếu chỉ gọi 1 lần).
    """
    status: UniquenessStatus
    first_model: dict[str, str] | None          # {char_id: 'CRIMINAL'/'INNOCENT'}
    second_model: dict[str, str] | None         # None nếu UNIQUE hoặc UNSAT
    sat_calls: int
    metrics_m1: dict[str, float]
    metrics_m2: dict[str, float] | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, UniquenessStatus):
            raise TypeError("status phải là UniquenessStatus")
        if self.status is UniquenessStatus.UNIQUE:
            if self.first_model is None:
                raise ValueError("UNIQUE yêu cầu first_model không None")
            if self.second_model is not None:
                raise ValueError("UNIQUE không có second_model")
        elif self.status is UniquenessStatus.NON_UNIQUE:
            if self.first_model is None or self.second_model is None:
                raise ValueError("NON_UNIQUE yêu cầu cả first_model và second_model")
        elif self.status is UniquenessStatus.UNSAT:
            if self.first_model is not None or self.second_model is not None:
                raise ValueError("UNSAT không có model")

    @property
    def is_unique(self) -> bool:
        return self.status is UniquenessStatus.UNIQUE

    @property
    def is_unsat(self) -> bool:
        return self.status is UniquenessStatus.UNSAT

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "is_unique": self.is_unique,
            "first_model": self.first_model,
            "second_model": self.second_model,
            "sat_calls": self.sat_calls,
            "metrics_m1": self.metrics_m1,
            "metrics_m2": self.metrics_m2,
        }

    def format_summary(self) -> str:
        lines = [f"Kết quả kiểm tra nghiệm: {self.status.value}"]
        if self.first_model:
            criminals = [cid for cid, v in self.first_model.items() if v == "CRIMINAL"]
            lines.append(f"  Nghiệm M₁ — Phạm nhân: {', '.join(sorted(criminals)) or '(không ai)'}")
        if self.second_model:
            criminals2 = [cid for cid, v in self.second_model.items() if v == "CRIMINAL"]
            lines.append(f"  Nghiệm M₂ — Phạm nhân: {', '.join(sorted(criminals2)) or '(không ai)'}")
        lines.append(
            f"  SAT calls={self.sat_calls} | "
            f"M₁ decisions={int(self.metrics_m1.get('decisions', 0))} | "
            + (f"M₂ decisions={int(self.metrics_m2.get('decisions', 0))}"
               if self.metrics_m2 else "M₂ không cần giải")
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hàm kiểm tra chính
# ---------------------------------------------------------------------------

def check_uniqueness(
    cnf: Sequence[Sequence[int]],
    primary_var_ids: Sequence[int],
    var_id_to_char_id: Mapping[int, str],
    solver: SolverWithModel,
) -> UniquenessResult:
    """Kiểm tra tính duy nhất của nghiệm toàn bàn cờ.

    Args:
        cnf:                Danh sách mệnh đề CNF (list of list of int).
        primary_var_ids:    Danh sách các biến primary (ID dương), không bao gồm aux.
        var_id_to_char_id:  Ánh xạ var_id → char_id để decode model.
        solver:             SAT solver hỗ trợ solve_with_model() và get_stats().

    Returns:
        UniquenessResult với đầy đủ thông tin.

    Raises:
        TypeError:  Nếu tham số sai kiểu.
        ValueError: Nếu primary_var_ids hoặc var_id_to_char_id không hợp lệ.
    """
    # --- Validate đầu vào ---
    if not isinstance(primary_var_ids, (list, tuple)) or len(primary_var_ids) == 0:
        raise ValueError("primary_var_ids phải là danh sách không rỗng")
    for v in primary_var_ids:
        if type(v) is not int or v <= 0:
            raise ValueError(f"Mọi primary_var_id phải là số nguyên dương, nhận được {v!r}")
        if v not in var_id_to_char_id:
            raise ValueError(f"Biến primary {v} không có mục trong var_id_to_char_id")

    # Chuẩn hoá CNF sang list[list[int]] để tránh side-effect
    cnf_copy: list[list[int]] = [list(clause) for clause in cnf]
    primary_set = frozenset(primary_var_ids)

    # ------------------------------------------------------------------
    # Lần 1: Tìm nghiệm M₁
    # ------------------------------------------------------------------
    sat1, model1 = solver.solve_with_model(cnf_copy)
    stats1: dict[str, float] = dict(solver.get_stats())

    if not sat1 or model1 is None:
        # KB mâu thuẫn — không có nghiệm
        return UniquenessResult(
            status=UniquenessStatus.UNSAT,
            first_model=None,
            second_model=None,
            sat_calls=1,
            metrics_m1=stats1,
            metrics_m2=None,
        )

    # Decode model sang {char_id: verdict}
    decoded_m1 = _decode_model(model1, primary_set, var_id_to_char_id)

    # ------------------------------------------------------------------
    # Lần 2: Thêm blocking clause ¬M₁ và giải lại
    # ------------------------------------------------------------------
    blocking_clause = _build_blocking_clause(model1, primary_set)
    cnf_blocked: list[list[int]] = cnf_copy + [blocking_clause]

    sat2, model2 = solver.solve_with_model(cnf_blocked)
    stats2: dict[str, float] = dict(solver.get_stats())

    if not sat2 or model2 is None:
        # Chỉ có đúng một nghiệm
        return UniquenessResult(
            status=UniquenessStatus.UNIQUE,
            first_model=decoded_m1,
            second_model=None,
            sat_calls=2,
            metrics_m1=stats1,
            metrics_m2=stats2,
        )
    else:
        # Tồn tại nghiệm thứ hai
        decoded_m2 = _decode_model(model2, primary_set, var_id_to_char_id)
        return UniquenessResult(
            status=UniquenessStatus.NON_UNIQUE,
            first_model=decoded_m1,
            second_model=decoded_m2,
            sat_calls=2,
            metrics_m1=stats1,
            metrics_m2=stats2,
        )


def check_uniqueness_from_var_map(
    cnf: Sequence[Sequence[int]],
    var_map: Any,
    solver: SolverWithModel,
) -> UniquenessResult:
    """Phiên bản tiện lợi nhận VariableMap thay vì danh sách biến thủ công.

    Args:
        cnf:        Danh sách mệnh đề CNF.
        var_map:    Đối tượng VariableMap (đã được freeze).
        solver:     SAT solver hỗ trợ solve_with_model() và get_stats().

    Returns:
        UniquenessResult.
    """
    # Trích xuất primary_var_ids và mapping từ VariableMap
    primary_mapping: Mapping[str, int] = var_map.primary_mapping  # {char_id: var_id}
    primary_var_ids: list[int] = list(primary_mapping.values())
    var_id_to_char_id: dict[int, str] = {v: k for k, v in primary_mapping.items()}
    return check_uniqueness(
        cnf=cnf,
        primary_var_ids=primary_var_ids,
        var_id_to_char_id=var_id_to_char_id,
        solver=solver,
    )


# ---------------------------------------------------------------------------
# Hàm hỗ trợ nội bộ
# ---------------------------------------------------------------------------

def _build_blocking_clause(
    model: dict[int, bool], primary_set: frozenset[int]
) -> list[int]:
    """Xây dựng blocking clause ¬M (chỉ dùng biến primary).

    Nếu M[var]=True  → literal phủ định = -var (để clause = False khi var=True).
    Nếu M[var]=False → literal dương    = +var (để clause = False khi var=False).
    Kết quả: (lit₁ ∨ lit₂ ∨ … ∨ litₙ) sẽ là False khi và chỉ khi mô hình
    gán giống hệt M₁ trên các biến primary.
    """
    clause: list[int] = []
    for var, value in model.items():
        if var not in primary_set:
            continue
        # Phủ định: nếu M[var]=True → đưa -var vào clause
        clause.append(-var if value else var)
    return clause


def _decode_model(
    model: dict[int, bool],
    primary_set: frozenset[int],
    var_id_to_char_id: Mapping[int, str],
) -> dict[str, str]:
    """Chuyển model DPLL sang {char_id: 'CRIMINAL'/'INNOCENT'}."""
    result: dict[str, str] = {}
    for var, value in model.items():
        if var not in primary_set:
            continue
        char_id = var_id_to_char_id.get(var)
        if char_id is None:
            continue
        result[char_id] = "CRIMINAL" if value else "INNOCENT"
    return result
