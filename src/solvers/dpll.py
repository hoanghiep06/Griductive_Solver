"""
Thuật toán DPLL SAT Solver thuần Python (TV2 - Huy phụ trách).

Tuân thủ đầy đủ các yêu cầu cốt lõi của đề tài (Mục 4.3):
1. Unit propagation (Lan truyền mệnh đề đơn vị)
2. Conflict detection (Phát hiện mâu thuẫn)
3. Deterministic variable selection (Chọn biến rẽ nhánh tất định)
4. Recursive branching & backtracking (Rẽ nhánh đệ quy và quay lui)
5. Trả về SAT (kèm assignment gán biến) hoặc UNSAT
6. Ghi nhận các chỉ số đo lường (decisions, propagations, backtracks, runtime)
7. Hỗ trợ đọc và kiểm thử file chuẩn DIMACS (.cnf) độc lập
"""

import time
from typing import Dict, Iterable, List, Optional, Set, Tuple


class DPLLSolver:
    """
    Bộ giải DPLL SAT Solver thuần Python độc lập.
    Đầu vào: CNF dưới dạng danh sách các mệnh đề (list of list of non-zero ints).
             Ví dụ: [[1, 2], [-1, 2]] tương đương (C1 v C2) ^ (~C1 v C2).
    """

    def __init__(self):
        # Bộ đếm metrics
        self.decisions: int = 0
        self.propagations: int = 0
        self.backtracks: int = 0
        self.runtime: float = 0.0

        # Lưu model nghiệm tìm được (nếu SAT)
        self.model: Optional[Dict[int, bool]] = None

    def reset_stats(self) -> None:
        """Đặt lại toàn bộ bộ đếm đo lường."""
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0
        self.runtime = 0.0
        self.model = None

    def get_stats(self) -> Dict[str, float]:
        """Trả về từ điển các chỉ số thực nghiệm."""
        return {
            "decisions": self.decisions,
            "propagations": self.propagations,
            "backtracks": self.backtracks,
            "runtime": self.runtime,
        }

    def solve(self, cnf: Iterable[Iterable[int]]) -> bool:
        """
        Giao diện chính phục vụ tích hợp với nhóm (EntailmentChecker, GameEngine).
        Trả về:
            True: nếu công thức SAT (thỏa được).
            False: nếu công thức UNSAT (vô nghiệm / mâu thuẫn).
        """
        is_sat, model = self.solve_with_model(cnf)
        return is_sat

    def solve_with_model(
        self, cnf: Iterable[Iterable[int]]
    ) -> Tuple[bool, Optional[Dict[int, bool]]]:
        """
        Giải công thức CNF và trả về bộ gán giá trị (model) nếu thỏa mãn.
        Trả về:
            (True, model_dict): nếu SAT.
            (False, None): nếu UNSAT.
        """
        self.reset_stats()
        start_time = time.perf_counter()

        # Chuẩn hóa clauses sang dạng list of sets và thu thập tất cả các biến
        clauses: List[Set[int]] = []
        all_vars: Set[int] = set()

        for raw_clause in cnf:
            clause = set(raw_clause)
            # Nếu clause chứa cả x và -x thì luôn True (tautology), có thể bỏ qua
            if any(-lit in clause for lit in clause):
                continue
            clauses.append(clause)
            for lit in clause:
                all_vars.add(abs(lit))

        # Khởi chạy thuật toán DPLL
        is_sat, assignment = self._dpll(clauses, {}, all_vars)

        self.runtime = time.perf_counter() - start_time
        if is_sat:
            # Đảm bảo tất cả các biến đều có giá trị (nếu có biến tự do chưa gán, gán mặc định False)
            full_model = {v: assignment.get(v, False) for v in all_vars}
            self.model = full_model
            return True, full_model
        else:
            self.model = None
            return False, None

    def _dpll(
        self,
        clauses: List[Set[int]],
        assignment: Dict[int, bool],
        all_vars: Set[int],
    ) -> Tuple[bool, Dict[int, bool]]:
        """
        Hàm đệ quy lõi DPLL với Unit Propagation và Backtracking.
        """
        current_assignment = dict(assignment)
        active = clauses
        # Simplify once per propagation wave and carry the reduced formula
        # into recursive branches. Already satisfied counter clauses no longer
        # participate in every scan of large global/group count encodings.
        while True:
            reduced = []
            units = []
            for clause in active:
                if any(current_assignment.get(abs(lit)) == (lit > 0)
                       for lit in clause if abs(lit) in current_assignment):
                    continue
                remaining = {lit for lit in clause if abs(lit) not in current_assignment}
                if not remaining:
                    return False, current_assignment
                reduced.append(remaining)
                if len(remaining) == 1:
                    units.append(next(iter(remaining)))
            active = reduced
            if not units:
                break
            for literal in units:
                variable, value = abs(literal), literal > 0
                if variable in current_assignment:
                    if current_assignment[variable] != value:
                        return False, current_assignment
                else:
                    current_assignment[variable] = value
                    self.propagations += 1
        if not active:
            return True, current_assignment

        # Stable smallest *active* unassigned variable. Variables appearing only
        # in satisfied clauses are free and need no speculative decisions.
        chosen_var = min(abs(lit) for clause in active for lit in clause)
        self.decisions += 1
        branch = dict(current_assignment)
        branch[chosen_var] = True
        sat, model = self._dpll(active, branch, all_vars)
        if sat:
            return True, model
        self.backtracks += 1
        branch[chosen_var] = False
        return self._dpll(active, branch, all_vars)

    # -------------------------------------------------------------
    # CÁC TIỆN ÍCH ĐỌC & TEST FILE .CNF CHUẨN DIMACS ĐỘC LẬP
    # -------------------------------------------------------------

    @staticmethod
    def parse_dimacs(dimacs_content: str) -> List[List[int]]:
        """Phân tích nội dung chuỗi định dạng DIMACS CNF thành danh sách các clauses."""
        clauses: List[List[int]] = []
        current_clause: List[int] = []

        for line in dimacs_content.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("c") or line.startswith("p"):
                # Bỏ qua dòng chú thích và dòng khai báo p cnf ...
                continue

            tokens = line.split()
            for token in tokens:
                try:
                    lit = int(token)
                except ValueError:
                    continue

                if lit == 0:
                    if current_clause:
                        clauses.append(current_clause)
                        current_clause = []
                else:
                    current_clause.append(lit)

        if current_clause:
            clauses.append(current_clause)

        return clauses

    @classmethod
    def from_dimacs_file(cls, filepath: str) -> List[List[int]]:
        """Đọc và chuyển đổi trực tiếp file .cnf thành cấu trúc clauses."""
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.parse_dimacs(f.read())

