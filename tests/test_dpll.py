"""
Bộ Unit Test độc lập cho thuật toán DPLL SAT Solver (TV2 - Huy).
Kiểm thử toàn diện:
1. Trường hợp rỗng và đơn vị (Unit Clause, Empty Formula, Empty Clause)
2. Kiểm tra tính SAT và tính đúng đắn của Model trả về
3. Kiểm tra tính UNSAT (Mâu thuẫn logic)
4. Kiểm tra các bộ đếm đo lường (Decisions, Propagations, Backtracks, Runtime)
5. Kiểm thử độc lập bằng chuỗi/file chuẩn DIMACS (.cnf)
"""

import unittest
from src.solvers.dpll import DPLLSolver


class TestDPLLSolver(unittest.TestCase):
    def setUp(self):
        self.solver = DPLLSolver()

    def _verify_model(self, clauses, model):
        """Hàm phụ trợ: Kiểm tra xem model có thực sự thỏa mãn tất cả clauses không."""
        self.assertIsNotNone(model, "Model không được là None khi SAT")
        for clause in clauses:
            sat = False
            for lit in clause:
                var = abs(lit)
                expected_val = lit > 0
                if model.get(var) == expected_val:
                    sat = True
                    break
            self.assertTrue(sat, f"Clause {clause} không được thỏa mãn bởi model {model}")

    def test_empty_formula(self):
        """Công thức rỗng [] luôn luôn là SAT (chân lý)."""
        cnf = []
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertTrue(is_sat)
        self.assertTrue(self.solver.solve(cnf))

    def test_single_unit_clauses(self):
        """Lan truyền đơn vị với các unit clauses."""
        # x1 = True
        cnf = [[1]]
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertTrue(is_sat)
        self.assertTrue(model[1])
        self._verify_model(cnf, model)

        # x2 = False
        cnf = [[-2]]
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertTrue(is_sat)
        self.assertFalse(model[2])
        self._verify_model(cnf, model)

    def test_direct_contradiction(self):
        """Mâu thuẫn trực tiếp (x1) ^ (~x1) -> UNSAT."""
        cnf = [[1], [-1]]
        self.assertFalse(self.solver.solve(cnf))
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertFalse(is_sat)
        self.assertIsNone(model)

    def test_chain_unit_propagation(self):
        """
        Chuỗi lan truyền đơn vị:
        (x1) ^ (~x1 v x2) ^ (~x2 v x3)
        Ép buộc: x1 = True -> x2 = True -> x3 = True.
        """
        cnf = [[1], [-1, 2], [-2, 3]]
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertTrue(is_sat)
        self.assertTrue(model[1])
        self.assertTrue(model[2])
        self.assertTrue(model[3])
        self._verify_model(cnf, model)

        stats = self.solver.get_stats()
        # Phải có ít nhất 3 lần propagation
        self.assertGreaterEqual(stats["propagations"], 3)

    def test_branching_and_backtracking(self):
        """
        Công thức yêu cầu rẽ nhánh và quay lui:
        (~x1 v ~x2) ^ (x1 v x2) ^ (x1 v ~x2)
        Giải thích:
        Nếu thử x1 = False -> x2 = True (từ clause 2) -> clause 3 thành (~x2) -> mâu thuẫn -> Backtrack!
        Sau đó chọn x1 = True -> x2 = False -> thỏa mãn toàn bộ!
        """
        cnf = [[-1, -2], [1, 2], [1, -2]]
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertTrue(is_sat)
        self._verify_model(cnf, model)

        stats = self.solver.get_stats()
        self.assertGreater(stats["decisions"], 0)
        self.assertGreaterEqual(stats["runtime"], 0.0)

    def test_unsat_all_combinations(self):
        """Tất cả 4 tổ hợp của 2 biến đều bị cấm -> UNSAT."""
        cnf = [
            [1, 2],
            [1, -2],
            [-1, 2],
            [-1, -2],
        ]
        is_sat, model = self.solver.solve_with_model(cnf)
        self.assertFalse(is_sat)
        self.assertIsNone(model)
        stats = self.solver.get_stats()
        self.assertGreater(stats["backtracks"], 0)

    def test_pigeonhole_principle_2_into_1(self):
        """
        Nguyên lý chuồng bồ câu: 2 con bồ câu vào 1 chuồng (UNSAT).
        x1: bồ câu 1 ở chuồng 1.
        x2: bồ câu 2 ở chuồng 1.
        Clause 1: Bồ câu 1 phải ở chuồng 1 -> (x1)
        Clause 2: Bồ câu 2 phải ở chuồng 1 -> (x2)
        Clause 3: Không thể cả 2 cùng ở chuồng 1 -> (~x1 v ~x2)
        """
        cnf = [[1], [2], [-1, -2]]
        self.assertFalse(self.solver.solve(cnf))

    def test_dimacs_parser_and_solver(self):
        """Kiểm tra độc lập với cú pháp chuẩn DIMACS (.cnf)."""
        dimacs_cnf_text = """
        c Day la file test DIMACS mau cho DPLL
        p cnf 3 4
        1 -2 0
        2 3 0
        -1 3 0
        -3 0
        """
        clauses = DPLLSolver.parse_dimacs(dimacs_cnf_text)
        self.assertEqual(len(clauses), 4)

        # Giải bài toán DIMACS này:
        # Clause 4: -3 -> x3 = False
        # Clause 2: (2 v 3) -> vì x3=F nên x2 = True
        # Clause 1: (1 v -2) -> vì x2=T nên -2=F -> x1 = True
        # Clause 3: (-1 v 3) -> x1=T nên -1=F, x3=F -> cả 2 đều F -> Mâu thuẫn!
        # Do đó DIMACS này phải là UNSAT.
        is_sat = self.solver.solve(clauses)
        self.assertFalse(is_sat)


if __name__ == "__main__":
    unittest.main()

