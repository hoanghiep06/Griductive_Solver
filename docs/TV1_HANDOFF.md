# Tích Hợp Kỹ Thuật (TV1 → Cả Nhóm)

Tài liệu này là hợp đồng bàn giao phần **Core Foundation (Nền tảng cốt lõi)**. Các thành viên khác trong nhóm cần thực hiện tích hợp thông qua các API công khai được định nghĩa dưới đây, tuyệt đối không tự ý đọc hay thay đổi mã nguồn nội bộ của `GameEngine`.

## 1. Phân định Ranh giới Trách nhiệm (Ownership Boundaries)

| Module / File | Thành viên phụ trách / Trách nhiệm |
| :--- | :--- |
| `core/puzzle_loader.py`, `core/puzzle_validator.py` | **TV1**: Đọc file, kiểm tra tính hợp lệ về mặt cấu trúc, ngữ nghĩa và tính giải được tuần tự của Puzzle. |
| `core/variable_map.py` | **TV1**: Nơi duy nhất quản lý bảng ánh xạ Biến chính (Primary) và Biến phụ (Auxiliary). |
| `core/cnf_types.py` | **TV1**: Nơi duy nhất định nghĩa chuẩn các Type Aliases: `Literal`, `Clause`, `CNFFormula`. |
| `core/public_kb.py` | **TV1**: Quản lý các manh mối công khai, phán quyết đã chứng minh, snapshot và unit clauses. |
| `core/game_engine.py` | **TV1**: Quản lý trạng thái ẩn (Hidden solution), quy trình lật bài, nạp/khôi phục game (`restart`/`load`). |
| `encoder/cnf_encoder.py` | **TV3**: Đọc `Clue` và `VariableMap`; trả về kiểu dữ liệu chuẩn `CNFFormula`. |
| `solvers/dpll.py` | **TV2**: Nhận kiểu dữ liệu chuẩn `CNFFormula` để thực thi thuật toán DPLL. |
| `agent/entailment.py` | **TV5**: Truy vấn DPLL Solver và tạo đối tượng `EntailmentResult`. |
| `agent/logic_agent.py` | **TV1 (Giai đoạn sau)**: Chọn nhân vật bị ép buộc theo thứ tự Row-Major và gửi phán quyết kèm bằng chứng chứng minh. |

## 2. Các Đường dẫn Import Chuẩn (Canonical Imports)

```python
from src.core.variable_map import VariableMap
from src.core.cnf_types import Literal, Clause, CNFFormula, validate_cnf
from src.core.clue import Clue
from src.core.public_kb import PublicKBSnapshot
from src.core.entailment_result import EntailmentResult, EntailmentStatus
from src.core.game_engine import GameEngine, GameEngineIntegrityError, VerdictResponse
```

*Lưu ý:* Các đường dẫn cũ như `src.encoder.variable_map` và `src.solvers.cnf_formula` là các file re-export nhằm đảm bảo tính tương thích. Chúng không chứa bất kỳ mã nguồn trùng lặp nào.

## 3. Dành cho TV3 — Đầu vào & Đầu ra của CNF Encoder

```python
engine = GameEngine("puzzles/sample_3x3.json")
snapshot: PublicKBSnapshot = engine.get_public_snapshot()
variable_map: VariableMap = engine.var_map

revealed_clues: tuple[Clue, ...] = snapshot.revealed_clues
proved_verdicts: Mapping[str, bool] = snapshot.proved_verdicts
unit_clauses: list[list[int]] = snapshot.get_unit_clauses_for_verdicts()
```

* **Nguyên tắc cho Encoder:** Chỉ được phép mã hóa danh sách manh mối công khai `snapshot.revealed_clues`, sau đó nối thêm danh sách `unit_clauses`. Encoder **tuyệt đối không được** truy cập vào các thuộc tính private của `GameEngine` hoặc các manh mối chưa ngửa.
* **Chỉ chuyển đổi Dict khi cần:** Phương thức `snapshot.revealed_clues` và `engine.get_revealed_clues()` trả về các đối tượng `Clue` bất biến. Chỉ gọi `clue.to_dict()` khi cần truyền dữ liệu ra dạng JSON/UI.

* **Cấp phát biến phụ (Auxiliary Variables):**

```python
aux_id = variable_map.allocate_auxiliary_variable({
    "source_clue_id": "CLUE_A3",
    "purpose": "EXACTLY_ENCODING",
})
```

Tập biến chính (Primary Variables) đã được `GameEngine` đóng băng (`freeze`) trước khi Encoder nhận `VariableMap`. Các chỉ số biến phụ sẽ được cấp phát nối tiếp ngay sau miền giá trị biến chính và không bao giờ được phép đăng ký nhầm làm biến nhân vật.

## 4. Dành cho TV2 — Đầu vào & Đầu ra của DPLL Solver

Thuật toán DPLL nhận cấu trúc danh sách tiêu chuẩn của Python:

```python
Literal = int
Clause = list[Literal]
CNFFormula = list[Clause]
```

* **Quy ước:**
  * Literal dương (`+i`) $\rightarrow$ Nhân vật $i$ là **Criminal** ($C_i = \text{True}$).
  * Literal âm (`-i`) $\rightarrow$ Nhân vật $i$ là **Innocent** ($C_i = \text{False}$).
  * Giá trị `0` là không hợp lệ.
  * CNF rỗng `[]` tương đương với **TRUE**; CNF chứa clause rỗng `[[]]` tương đương với **FALSE**.
* DPLL có thể bổ sung thêm các cấu trúc dữ liệu, thuật toán nhánh cận và bộ đo đạc chỉ số (metrics) riêng, nhưng không được định nghĩa lại các alias chung này gây xung đột.

## 5. Dành cho TV5 — Khởi tạo Kết quả Entailment (`EntailmentResult`)

Đối với nhân vật $i$, tiến hành 2 câu truy vấn SAT:
* `criminal_assumption_satisfiable` $= \text{SAT}(KB \wedge C_i)$
* `innocent_assumption_satisfiable` $= \text{SAT}(KB \wedge \neg C_i)$

*Lưu ý:* Phải kiểm tra tính thỏa mãn của tập $KB$ cơ sở trước. Kết quả được phân loại tự động theo bảng sau:

```python
result = EntailmentResult.from_sat_results(
    character_id=char_id,
    kb_version=snapshot.version,
    kb_satisfiable=base_is_sat,
    criminal_assumption_satisfiable=with_criminal_is_sat,
    innocent_assumption_satisfiable=with_innocent_is_sat,
)
```

| Tập KB cơ sở | SAT($KB \wedge C_i$) | SAT($KB \wedge \neg C_i$) | Trạng thái (`EntailmentStatus`) |
| :--- | :---: | :---: | :--- |
| **UNSAT** | — | — | `INCONSISTENT` |
| **SAT** | **SAT** | **UNSAT** | `CRIMINAL` |
| **SAT** | **UNSAT** | **SAT** | `INNOCENT` |
| **SAT** | **SAT** | **SAT** | `UNKNOWN` |
| **SAT** | **UNSAT** | **UNSAT** | *(Kết quả SAT không hợp lệ - Tự động bắn lỗi)* |

## 6. API Gửi Phán Quyết cho GameEngine (TV1 Interface)

```python
response, newly_revealed_clue = engine.submit_verdict(
    char_id="B1",
    claimed_status=True,  # True=CRIMINAL, False=INNOCENT
    entailment=result,
)
```

* Đối tượng `EntailmentResult` gửi vào phải khớp đúng `char_id` và phiên bản tập tri thức `snapshot.version`.
* Sau bất kỳ giao dịch lật lá bài công khai nào, các bằng chứng tính trên `version` cũ sẽ bị từ chối với phản hồi **`STALE_PROOF`**.
* Trạng thái `UNKNOWN` luôn trả về **`NOT_PROVABLE`**, bất kể phán quyết đưa ra hay đáp án ẩn là gì.
* Phản hồi **`CONTRADICTED`** chỉ được trả về khi phán quyết đưa ra ngược với kết quả kéo theo công khai.
* Một giao dịch lật bài thành công (thêm phán quyết và manh mối) sẽ tăng `snapshot.version` lên đúng **1 đơn vị**.
* **Chốt an toàn (`GameEngineIntegrityError`):** Nếu phán quyết được chấp nhận nhưng bị lệch với đáp án ẩn `hidden_solution`, Engine sẽ nổ exception `GameEngineIntegrityError`. Đây là lỗi nội bộ kiểm tra tính đúng đắn của Solver/Encoder, không làm tiết lộ đáp án ra giao diện.

## 7. Các Quy tắc Tích hợp Quan trọng (Important Rules)

1. **Không truyền đối tượng `GameEngine`** vào `LogicAgent` hoặc `CNFEncoder`. Chỉ truyền `PublicKBSnapshot`, `VariableMap` và dữ liệu công khai của nhân vật.
2. **Không tự định nghĩa lại** các class/alias `VariableMap`, `Literal`, `Clause`, hoặc `CNFFormula` ở package khác.
3. **Không chỉnh sửa** các trường dữ liệu trong snapshot (đây là đối tượng read-only). Chỉ chuyển đổi clue thành dict thông qua `clue.to_dict()` khi thực sự cần định dạng JSON/dict.
4. **Không gửi phán quyết dựa trên 1 model duy nhất:** Một phán quyết hợp lệ bắt buộc phải dựa vào kết quả từ 2 phép kiểm tra SAT giả định.
5. **Đã kiểm tra tính giải được tuần tự:** File `sample_3x3.json` có nghiệm duy nhất trên 512 gán biến và giải được tuần tự từng bước từ `A1` qua chuỗi: `B1 -> C1 -> A2 -> B2 -> C2 -> A3 -> B3 -> C3`.
6. Hàm `PuzzleValidator.analyze_sequential_solvability()` là công cụ kiểm thử cạn cho small puzzle (tối đa 9 nhân vật). Nếu vượt quá giới hạn sẽ trả về `TOO_LARGE` chứ không treo máy.