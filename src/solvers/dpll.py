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

        # 1. UNIT PROPAGATION
        while True:
            # Kiểm tra trạng thái các mệnh đề dưới phép gán hiện tại
            unit_literals: List[int] = []
            has_conflict = False

            for clause in clauses:
                unassigned_lits = []
                clause_satisfied = False

                for lit in clause:
                    var = abs(lit)
                    if var in current_assignment:
                        # Kiểm tra literal có đúng theo assignment không
                        lit_val = current_assignment[var] if lit > 0 else not current_assignment[var]
                        if lit_val:
                            clause_satisfied = True
                            break
                    else:
                        unassigned_lits.append(lit)

                if clause_satisfied:
                    continue

                # Conflict detection: Tất cả literals trong clause đều False -> Clause rỗng -> Mâu thuẫn
                if len(unassigned_lits) == 0:
                    has_conflict = True
                    break

                # Unit clause detection: Chỉ còn đúng 1 literal chưa gán và clause chưa thỏa mãn
                if len(unassigned_lits) == 1:
                    unit_literals.append(unassigned_lits[0])

            if has_conflict:
                return False, current_assignment

            if not unit_literals:
                # Không còn unit clause nào để lan truyền
                break

            # Thực hiện lan truyền đơn vị cho unit literal tìm được đầu tiên
            unit_lit = unit_literals[0]
            var = abs(unit_lit)
            forced_val = unit_lit > 0

            if var in current_assignment:
                if current_assignment[var] != forced_val:
                    # Xảy ra mâu thuẫn giữa 2 unit clauses
                    return False, current_assignment
            else:
                self.propagations += 1
                current_assignment[var] = forced_val

        # 2. KIỂM TRA ĐIỀU KIỆN DỪNG (Toàn bộ clauses đã thỏa mãn chưa?)
        all_satisfied = True
        for clause in clauses:
            clause_sat = False
            for lit in clause:
                var = abs(lit)
                if var in current_assignment:
                    lit_val = current_assignment[var] if lit > 0 else not current_assignment[var]
                    if lit_val:
                        clause_sat = True
                        break
            if not clause_sat:
                all_satisfied = False
                break

        if all_satisfied:
            return True, current_assignment

        # 3. DETERMINISTIC VARIABLE SELECTION (Chọn biến rẽ nhánh tất định)
        # Chọn biến chưa gán có chỉ số số nguyên nhỏ nhất
        unassigned_vars = sorted([v for v in all_vars if v not in current_assignment])
        if not unassigned_vars:
            # Tất cả các biến đã gán nhưng vẫn có clause chưa thỏa mãn
            return False, current_assignment

        chosen_var = unassigned_vars[0]

        # 4. RECURSIVE BRANCHING & BACKTRACKING
        # Nhánh 1: Thử chosen_var = True (Quyết định rẽ nhánh)
        self.decisions += 1
        branch1_assignment = dict(current_assignment)
        branch1_assignment[chosen_var] = True
        sat1, model1 = self._dpll(clauses, branch1_assignment, all_vars)
        if sat1:
            return True, model1

        # Nhánh 2: Backtrack, thử chosen_var = False
        self.backtracks += 1
        branch2_assignment = dict(current_assignment)
        branch2_assignment[chosen_var] = False
        sat2, model2 = self._dpll(clauses, branch2_assignment, all_vars)
        if sat2:
            return True, model2

        # Cả 2 nhánh đều mâu thuẫn -> UNSAT
        return False, current_assignment

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

