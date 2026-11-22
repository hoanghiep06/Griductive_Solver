"""Tìm tập chứng cứ tối tiểu cho một bước suy luận .

Một bước suy luận "KB ⊨ C" được chứng minh bằng cách chỉ ra KB ∧ ¬C là UNSAT.
Thông thường KB chứa nhiều manh mối không liên quan đến kết luận. Module này
dùng thuật toán *xóa dần* (deletion-based minimization) để thu nhỏ KB về một
tập con tối tiểu (subset-minimal): bỏ bất kỳ manh mối / ô đã chứng minh nào
khỏi tập này thì ¬C không còn dẫn tới mâu thuẫn.

Module này không import GameEngine / Encoder / DPLL để có thể test độc lập;
solver chỉ cần có phương thức ``solve(cnf) -> bool``.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

# (loại nhóm: "clue" | "cell", định danh, danh sách mệnh đề CNF của nhóm)
EvidenceGroup = tuple[str, str, list[list[int]]]


def minimize_support(
    groups: Sequence[EvidenceGroup],
    opposite_literal: int,
    solver: Any,
    on_solve: Callable[[], None] | None = None,
) -> list[EvidenceGroup]:
    """Thu nhỏ ``groups`` về tập con tối tiểu vẫn khiến ¬C mâu thuẫn.

    Args:
        groups:            Các nhóm mệnh đề (mỗi manh mối / mỗi ô đã chứng minh một nhóm).
        opposite_literal:  Literal của giả thiết ngược (¬C), ví dụ -v nếu kết luận là
                           CRIMINAL, +v nếu là INNOCENT.
        solver:            Đối tượng có ``solve(cnf) -> bool`` (True = SAT).
        on_solve:          Callback tuỳ chọn gọi sau mỗi lần giải (để thu metrics).

    Returns:
        Danh sách nhóm còn lại, giữ nguyên thứ tự ban đầu.

    Precondition:
        Toàn bộ ``groups`` ∧ ¬C phải là UNSAT (caller nên kiểm tra trước).
    """
    n = len(groups)
    active = [True] * n
    group_clauses = [[list(c) for c in cs] for _, _, cs in groups]
    for idx in range(n):
        active[idx] = False
        clauses = [list(c) for i in range(n) if active[i] for c in group_clauses[i]]
        clauses.append([opposite_literal])
        satisfiable = solver.solve(clauses)
        if on_solve is not None:
            on_solve()
        if satisfiable:
            # Bỏ nhóm này làm mất tính mâu thuẫn → nhóm này bắt buộc phải giữ lại.
            active[idx] = True
    return [groups[i] for i in range(n) if active[i]]