# Griductive Solver — Nền Tảng Cốt Lõi Engine (TV1 Core Foundation)

Dự án phát triển **Hệ thống tự động giải đố trò chơi Griductive (No-Guess Griductive Solver)** sử dụng **Logic Mệnh đề (Propositional Logic)**, **Mã hóa CNF (CNF Encoding)** và giải thuật **DPLL SAT Solver**.

## 1. Yêu cầu Hệ thống & Cài đặt (Requirements & Setup)

* **Phiên bản Python:** Python 3.10 trở lên.
* **Thư viện phụ thuộc:** Phần Core Engine của TV1 **sử dụng thuần thư viện tiêu chuẩn Python (Standard Library)**. 
* Package `jsonschema` là tùy chọn (chỉ dùng nếu muốn validate trực tiếp qua lệnh CLI schema validation), hệ thống chạy thực thi và Unit Test hoàn toàn không phụ thuộc vào thư viện ngoài.

### Chạy giao diện Desktop (PySide6 GUI)
Cài đặt thư viện giao diện (nếu chưa cài) và khởi chạy ứng dụng:

```bash
pip install PySide6
python -m src.gui.app
```

### Kiểm thử hệ thống (Run Unit Tests)
Chạy lệnh sau tại thư mục gốc dự án để kiểm tra toàn bộ bộ test tự động (Core + GUI):

```bash
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen PYTEST_QT_API=pyside6 pytest -q
python -m compileall -q src tests
```

---

## 2. Cấu trúc Dự án (Project Layout)

```text
Lab02/
├── puzzles/                  # Thư mục chứa các màn chơi (.json)
│   └── sample_3x3.json       # File puzzle mẫu 3x3 giải được tuần tự 100%
├── schemas/                  # JSON Schema v1.0 cho puzzle
│   └── puzzle.schema.json
├── docs/                     # Tài liệu bàn giao & Hợp đồng kỹ thuật (TV1)
│   ├── TV1_HANDOFF.md        # Hợp đồng tích hợp API dành cho cả nhóm
│   └── TV1_PUSH_NOTES.md     # Ghi chú phát hành & các điểm cập nhật mới
├── src/
│   ├── core/                 # [TV1 - Đã hoàn thành] Nền tảng cốt lõi
│   │   ├── character.py      # Data model Nhân vật (Immutable)
│   │   ├── clue.py           # Data model Manh mối (Immutable)
│   │   ├── cnf_types.py      # Định nghĩa chuẩn Type Aliases: Literal, Clause, CNFFormula
│   │   ├── variable_map.py   # Ánh xạ 1-1 giữa Nhân vật và Biến SAT C_i
│   │   ├── entailment_result.py # Hợp đồng kết quả Entailment cho SAT Solver
│   │   ├── public_kb.py      # Tập tri thức công khai (Public KB & Snapshot)
│   │   ├── game_engine.py    # Game Engine quản lý ẩn/hiện và quy trình lật thẻ
│   │   ├── puzzle.py         # Data model tập hợp Puzzle
│   │   ├── puzzle_validator.py # Validator kiểm tra Schema, ngữ nghĩa & giải được tuần tự
│   │   ├── puzzle_loader.py  # Nạp file JSON an toàn (Atomic Loading)
│   │   └── sequential_solvability.py # Thuật toán phân tích giải được tuần tự không đoán
│   ├── encoder/              # [TV3 & TV4] Chuyển đổi Manh mối sang CNF
│   │   └── variable_map.py   # Re-export chính thức từ src.core.variable_map
│   ├── solvers/              # [TV2] DPLL SAT Solver
│   │   └── cnf_formula.py    # Re-export chính thức từ src.core.cnf_types
│   ├── agent/                # [TV5 & TV1] Logic Agent & Deduction Loop
│   └── gui/                  # [TV2 & TV3] Giao diện người dùng
├── tests/                    # Bộ Unit Tests tự động kiểm thử toàn diện
│   └── fixtures/             # File puzzle thử nghiệm các trường hợp biên
├── requirements.txt
└── README.md
```

---

## 3. Giao ước Kỹ thuật dùng chung (Shared Logic Contracts)

Các thành viên phát triển module riêng tuân thủ các giao ước sau:

### A. Quản lý Biến Mệnh đề (`VariableMap`)
* **Thứ tự Biến chính (Primary Variables):** Tự động gán chỉ số cố định $1, 2, \dots, N^2$ dựa trên thứ tự tên hiển thị `(display_name.casefold(), character_id)`. Với file mẫu 3x3 theo thứ tự Hàng (Row-Major): `A1` Abel (1), `B1` Bea (2), `C1` Clara (3), `A2` Derek (4), `B2` Eliza (5), `C2` Franz (6), `A3` Grant (7), `B3` Hannah (8), `C3` Ivy (9).
* **Đóng băng miền biến:** `GameEngine` tự động gọi `freeze_primary_variables()` trước khi truyền `VariableMap` cho Encoder. Các biến phụ (Auxiliary Variables) được cấp phát sau miền biến chính và không bao giờ được phép gán làm biến nhân vật.
* **Quy ước Literal:**
  * `+i`: Nhân vật $i$ là Tội phạm (**Criminal**, $C_i = \text{True}$).
  * `-i`: Nhân vật $i$ là Vô tội (**Innocent**, $C_i = \text{False}$).
  * `0`: Giá trị không hợp lệ.

### B. Định dạng CNF chuẩn (`src/core/cnf_types.py`)
Import trực tiếp các Type Aliases từ đường dẫn đại diện `src.solvers.cnf_formula` hoặc `src.core.cnf_types`:
* `Literal = int`
* `Clause = list[Literal]`
* `CNFFormula = list[Clause]`
* Tập CNF rỗng `[]` tương đương $\text{TRUE}$; CNF chứa mệnh đề rỗng `[[]]` tương đương $\text{FALSE}$.

### C. Tri thức Công khai (`PublicKB` & `PublicKBSnapshot`)
* `PublicKB` chỉ lưu giữ: (1) Manh mối đã lật ngửa, (2) Trạng thái nhân vật đã được chứng minh.
* Gọi `engine.get_public_snapshot()` để lấy đối tượng `PublicKBSnapshot` bất biến (read-only).
* Lấy danh sách mệnh đề đơn đại diện cho trạng thái đã biết qua `snapshot.get_unit_clauses_for_verdicts()`.
* **Giao dịch Nguyên tử (Atomic Reveal):** Mỗi lần lật ngửa 1 lá bài (bao gồm cả phán quyết và manh mối) chỉ làm tăng `version` của KB đúng **1 lần**. Version giữ tính tăng đơn điệu (monotonic) ngay cả khi `restart()` hoặc `load_puzzle()`.

---

## 4. Tương tác với `GameEngine` & Kiểm tra Kéo theo (`EntailmentResult`)

Agent hoặc GUI **bắt buộc** phải gửi phán quyết kèm đối tượng `EntailmentResult` được tính toán từ 3 câu truy vấn SAT:

1. $\text{SAT}(KB)$ — Kiểm tra tính nhất quán của tập tri thức cơ sở.
2. $\text{SAT}(KB \wedge C_i)$ — Giả định nhân vật $i$ là Criminal.
3. $\text{SAT}(KB \wedge \neg C_i)$ — Giả định nhân vật $i$ là Innocent.

```python
from src.core.entailment_result import EntailmentResult
from src.core.game_engine import GameEngine, VerdictResponse

engine = GameEngine("puzzles/sample_3x3.json")
snapshot = engine.get_public_snapshot()

# Tạo EntailmentResult cho nhân vật B1 tại version hiện tại:
result = EntailmentResult.from_sat_results(
    character_id="B1",
    kb_version=snapshot.version,
    kb_satisfiable=True,
    criminal_assumption_satisfiable=True,   # SAT(KB AND C_B1)
    innocent_assumption_satisfiable=False,  # UNSAT(KB AND NOT C_B1) => Bố trí B1 = CRIMINAL
)

response, newly_revealed_clue = engine.submit_verdict(
    char_id="B1", 
    claimed_status=True, # True = CRIMINAL 
    entailment=result
)
```

### Các phản hồi từ GameEngine (`VerdictResponse`)
* `ACCEPTED`: Phán quyết đúng logic kéo theo; lá bài được lật ngửa và trả về manh mối mới.
* `NOT_PROVABLE`: Cả 2 giả định đều SAT (tri thức chưa đủ để khẳng định).
* `CONTRADICTED`: Phán quyết ngược lại mới đúng với logic kéo theo.
* `INCONSISTENT`: Tập tri thức công khai bị mâu thuẫn (UNSAT).
* `STALE_PROOF`: Bằng chứng được tính toán trên `kb_version` cũ (đã quá hạn sau khi có bài mới).
* `ALREADY_SOLVED`: Nhân vật đã được lật ngửa từ trước.

> **Chốt An toàn Nội bộ (`GameEngineIntegrityError`):** Nếu một phán quyết được logic chứng minh là đúng (`ACCEPTED`) nhưng lại ngược với đáp án ẩn `hidden_solution`, `GameEngine` sẽ raise lỗi `GameEngineIntegrityError`. Đây là cơ chế phát hiện bug mã hóa CNF/DPLL của hệ thống, không làm lộ đáp án ra giao diện người chơi.

---

## 5. Chuẩn Định dạng Puzzle Schema v1.0 & Phân tích Giải được Tuần tự

Các file puzzle trong `puzzles/` tuân thủ JSON Schema v1.0:
* `grid_size`: Kích thước bàn cờ ($3$, $4$, hoặc $5$).
* `characters`: Danh sách $N^2$ nhân vật gồm `id`, `name`, `profession`, `row`, `col` (tọa độ zero-based $0 \dots N-1$).
* `hidden_solution`: Trạng thái ẩn (`true` = Criminal, `false` = Innocent).
* `initial_revealed`: Danh sách ID các nhân vật lật ngửa ban đầu.
* `clues`: Mới mỗi nhân vật sở hữu đúng 1 manh mối với 6 mẫu chuẩn (`FACT`, `SAME`, `DIFFERENT`, `EXACTLY`, `AT_LEAST`, `AT_MOST`).

### Tính Giải được Tuần tự (Sequential Solvability) vs. Tính Duy nhất Nghiệm (Uniqueness)
* **Tính Duy nhất Nghiệm (Uniqueness):** File `sample_3x3.json` chỉ có **đúng 1 model thỏa mãn** trên toàn bộ $2^9 = 512$ khả năng gán biến.
* **Tính Giải được Tuần tự (Sequential Solvability):** Trò chơi Griductive đòi hỏi người chơi/Agent phải giải được từng bước mà không cần đoán. File `sample_3x3.json` đảm bảo chuỗi suy luận 8 bước liên tục từ lá bài `A1` ban đầu:
  $$\text{A1} \to \text{B1} \to \text{C1} \to \text{A2} \to \text{B2} \to \text{C2} \to \text{A3} \to \text{B3} \to \text{C3}$$

Hàm `PuzzleValidator.analyze_sequential_solvability()` được tích hợp để tự động kiểm thử tính giải được tuần tự khi thiết kế màn chơi mới.

