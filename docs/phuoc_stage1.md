# Giai đoạn 1 — Nguyễn Hoài Phước

> Tài liệu lịch sử của dataset V1 tại commit `b940b8c`. Dataset hiện tại đã nâng
> cấp V2, dùng SAT tham chiếu và exact minimum support. Xem
> [báo cáo V2](phuoc_dataset_v2_report.md); bảng map và phương pháp dataset bên
> dưới mô tả bản V1 được bảo toàn trong `puzzles_baseline/`.

## A. Phạm vi và trạng thái

Triển khai EntailmentChecker, dataset **15 puzzle** và công cụ kiểm định độc lập.
Không thay source Core của Hiệp, DPLL của Huy, Encoder của Phong hoặc Evaluator
của Tài. Audit baseline trước chỉnh sửa: [phuoc_stage1_audit.md](phuoc_stage1_audit.md).

**Phần độc lập đã hoàn thành. Tích hợp DPLL/CNF thực tế đang BLOCKED.**
Các trạng thái PASSED trong manifest nói về schema, ngữ nghĩa, chứng minh xây
dựng uniqueness và no-guess; trường `dpll_cnf_integration` vẫn là `SKIPPED`.

## B. Cơ sở lý thuyết

Đặt `Ci=True` là CRIMINAL, `Ci=False` là INNOCENT.

```text
KB |= Ci      <=>  KB AND NOT Ci is UNSAT
KB |= NOT Ci  <=>  KB AND Ci is UNSAT
```

Một SAT model chỉ cho biết **một** trạng thái phù hợp. Ví dụ `[[1,2]]` có cả
model `C1=True,C2=False` và model `C1=False,C2=True`; không thể kết luận C1.
Entailment yêu cầu trạng thái đúng trong **mọi** model của KB công khai.

```text
KB_t = CNF(snapshot.revealed_clues) + snapshot.get_unit_clauses_for_verdicts()
```

KB không nhận private key hoặc clue chưa mở. Manh mối của Criminal cũng đúng.

| SAT(KB) | SAT(KB AND -Ci) | SAT(KB AND +Ci) | Phân loại |
|---|---|---|---|
| False | Không gọi | Không gọi | INCONSISTENT |
| True | False | True | CRIMINAL |
| True | True | False | INNOCENT |
| True | True | True | UNKNOWN |
| True | False | False | SolverProtocolError: evidence không hợp lệ |

## C. API và thuật toán

File production duy nhất được triển khai: `src/agent/entailment.py`.

- `Verdict` là alias của **EntailmentStatus của Hiệp**, không tạo enum cạnh tranh.
- `SATSolver`: protocol `solve(list[list[int]]) -> bool`. Phải trả đúng kiểu bool;
  `None`, model dict, tuple, số 0/1, chuỗi SAT/UNSAT đều bị từ chối.
- `SolverAdapter(solve, decode)`: chuẩn hóa **tường minh** API khác. Hàm decode
  phải raise lỗi với timeout/UNKNOWN/error và trả bool với SAT/UNSAT. Không có
  fallback hay SAT solver production thứ hai. Metrics vẫn do solver/caller quản lý.
- `SATQuery(assumption, satisfiable, sequence)`: dataclass bất biến; assumption
  `None` cho KB gốc, số nguyên có dấu cho unit giả định, sequence bắt đầu tại 1.
- `ClassificationResult(verdict, queries)`: kết quả và SAT evidence; `sat_calls`
  đếm query trong kết quả; `to_engine_result(character_id, kb_version)` tạo đúng
  **EntailmentResult của Hiệp**. Vì Core đã có tên lớp này, wrapper được đặt tên
  khác API gợi ý để giữ tương thích. Caller phải gắn đúng ID và snapshot version.
- `BatchResult(results, queries)`: mapping chỉ đọc; `verdicts` là mapping verdict,
  `sat_calls` đếm tổng truy vấn thực tế, query KB gốc chỉ tính một lần.
- `EntailmentChecker(solver, variable_map=None)`: dependency injection. Khi tích
  hợp game, truyền `variable_map` chính thức đã freeze để loại auxiliary hoặc
  mapping sai. Standalone không có metadata để biết một ID tùy ý là primary hay
  auxiliary; lúc đó caller chịu trách nhiệm cung cấp mapping primary đúng.

```python
result = checker.classify([[1, 2], [-1, 2]], variable=2)
assert result.verdict is Verdict.CRIMINAL
assert result.sat_calls == 3

batch = checker.classify_all(public_cnf, {"A1": 7, "B1": 2})
assert batch.sat_calls == 5  # nếu KB SAT
first = checker.first_forced(public_cnf, unresolved)
```

Không giả định A1 luôn có variable ID 1. `classify_all` sắp xếp theo tọa độ ID
`A1,B1,...,A2,...`, độc lập với thứ tự dict và chỉ số SAT. Hàm hỗ trợ cột nhiều
chữ và hàng nhiều chữ số. Mapping batch dùng cell ID chuẩn, không ID tùy ý.

```text
validate CNF + variable IDs + duplicate mapping before any solver call
copy input CNF
base = SAT(KB)
if not base: return INCONSISTENT for every unresolved cell
for cell in row-major order:
    i_sat = SAT(fresh_copy(KB) + [[-variable]])
    c_sat = SAT(fresh_copy(KB) + [[+variable]])
    reject both UNSAT
    classify from the table; record actual ordered queries
```

`classify`: 1 call nếu base UNSAT, ngược lại 3 calls. `classify_all`: 1 call nếu
UNSAT, ngược lại `1+2n`, kể cả batch rỗng (`n=0`). Không cache qua các lần gọi để
tránh dùng kết quả của KB version cũ. Mỗi query nhận bản sao sâu theo cấp clause,
nên solver sửa input cũng không làm bẩn KB hay query kế tiếp.

`first_forced` dùng batch đầy đủ rồi lấy phần tử forced đầu tiên; trả `(cid,
ClassificationResult)` hoặc `None` khi không có forced, kể cả INCONSISTENT.
Khi cần phân biệt terminal state hoặc ghi đủ số calls, dùng `classify_all`.
Các query trong kết quả từng cell dùng chung base query; không cộng `sat_calls`
của từng cell để tính số calls batch. Dùng `batch.sat_calls`.

CNF nhận list/tuple của list/tuple; literal phải có `type(x) is int`, khác 0.
CNF `[]` là TRUE, `[[]]` là FALSE. TypeError cho sai kiểu, ValueError cho miền
giá trị sai, KeyError cho ID không có trong VariableMap. Solver output lỗi gây
SolverProtocolError; timeout/exception của solver được truyền nguyên lên caller.

## D. Dataset và schema

Dùng nguyên [schema v1.0 của Hiệp](../schemas/puzzle.schema.json), không dùng
schema tạm. Mỗi file có đúng các trường:

| Trường | Ý nghĩa |
|---|---|
| schema_version | Chuỗi `1.0` |
| puzzle_id | ID khớp tên file, ví dụ `3x3_01` |
| grid_size | 3, 4 hoặc 5 |
| characters | N² đối tượng `id,name,profession,row,col`; tọa độ zero-based |
| hidden_solution | Mapping riêng tư `cell -> bool` |
| initial_revealed | Một hoặc hai cell mở sẵn |
| clues | N² đối tượng `clue_id,owner_id,type,parameters` |

Tên nhân vật distinct và alphabet theo row-major. Mỗi cell sở hữu một clue.
FACT dùng `target,status`; SAME/DIFFERENT dùng `target1,target2`; counting dùng
`k,region_type` kèm `index` cho ROW/COLUMN, `center` cho NEIGHBORS hoặc `cells`
cho EXPLICIT. Hàng/cột bắt đầu từ 0. Neighbors có cả đường chéo, bỏ trung tâm.
EXPLICIT không lặp. `0 <= k <= region_size`. Không có extension tự định nghĩa.

Giữ nguyên `sample_3x3.json` của Hiệp: thư mục chứa **16 puzzle thực tế**, trong
đó đúng **15 puzzle của Phước** được manifest và `PUZZLE_IDS` liệt kê. Manifest
không phải puzzle. Không glob mọi JSON rồi đưa manifest vào GameEngine.

| Puzzle ID | Size | Criminal | Innocent | Clues | Mở sẵn | Kiểm định độc lập |
|---|---|---:|---:|---:|---:|---|
| 3x3_01 | 3×3 | 3 | 6 | 9 | 1 | PASSED |
| 3x3_02 | 3×3 | 4 | 5 | 9 | 2 | PASSED |
| 3x3_03 | 3×3 | 5 | 4 | 9 | 1 | PASSED |
| 3x3_04 | 3×3 | 6 | 3 | 9 | 2 | PASSED |
| 3x3_05 | 3×3 | 7 | 2 | 9 | 1 | PASSED |
| 4x4_01 | 4×4 | 5 | 11 | 16 | 1 | PASSED |
| 4x4_02 | 4×4 | 7 | 9 | 16 | 2 | PASSED |
| 4x4_03 | 4×4 | 9 | 7 | 16 | 1 | PASSED |
| 4x4_04 | 4×4 | 10 | 6 | 16 | 2 | PASSED |
| 4x4_05 | 4×4 | 12 | 4 | 16 | 1 | PASSED |
| 5x5_01 | 5×5 | 8 | 17 | 25 | 1 | PASSED |
| 5x5_02 | 5×5 | 11 | 14 | 25 | 2 | PASSED |
| 5x5_03 | 5×5 | 14 | 11 | 25 | 1 | PASSED |
| 5x5_04 | 5×5 | 16 | 9 | 25 | 2 | PASSED |
| 5x5_05 | 5×5 | 18 | 7 | 25 | 1 | PASSED |

PASSED ở bảng này là schema + semantics + constructive uniqueness + no-guess.
DPLL/CNF integration: SKIPPED cho cả 15 map.

### Sinh dữ liệu tái lập

Seed gốc `20261109`; seed từng case `seed + size*100 + case`. RNG cục bộ, không
đụng trạng thái random của caller. Không có timestamp làm thay đổi output.
Generator kiểm định từng map và coverage toàn batch trước khi ghi file.

Mỗi map chọn đáp án, path và phân bố nghề nghiệp. Năm case dùng đường đi hàng
zíc zắc, cột zíc zắc, hoán vị ngẫu nhiên, từ trong ra biên và hoán vị khác.
Tỉ lệ Criminal thay đổi theo case. Một hoặc hai vị trí trên path mở sẵn.

Với prefix đã biết và target kế tiếp, owner hiện tại nhận SAME/DIFFERENT với
một cell trước đó, hoặc counting trên vùng gồm target và các cell prefix.
EXACTLY với tổng đúng ép target; AT_LEAST được chọn khi target=True và ngưỡng
vượt số Criminal đã biết một đơn vị; AT_MOST khi target=False và ngưỡng bằng
số Criminal đã biết. Ưu tiên template/region chưa dùng để tạo đa dạng.

Owner cuối có FACT ép cell đầu. Khi xét toàn bộ clue, FACT này tạo mốc suy luận
để chứng minh tất cả trạng thái mà **không dùng initial status units**. Khi chơi,
cell đầu đã mở nên chuỗi public có thể bắt đầu dù FACT cuối chưa được mở.
Mỗi map chỉ có một FACT; tất cả 15 map hiện có đủ 6 template và cả 4 loại vùng.
Các nhãn Easy–Hard trong manifest chỉ là mục tiêu thiết kế, `difficulty_measured`
là false; chưa có thực nghiệm DPLL để xác nhận độ khó.

### Phương pháp kiểm định đã thực thi

1. JSON Schema bằng jsonschema, sau đó `PuzzleValidator.validate` của Hiệp
   kiểm tra tham chiếu, cardinality và sự thật của **mọi clue** theo key.
2. `forced_from_public(known, clues, characters, size)` chỉ xét tối đa 8 biến
   chưa biết trong **một clue**. Mọi local model cùng giá trị thì verdict được
   chứng minh. Hàm không nhận puzzle, key hay GameEngine.
3. Uniqueness: bật toàn bộ clue, bắt đầu `known={}`. Từng verdict local là hệ
   quả của tập clue. Nếu chứng minh đủ N² biến thì có tối đa một nghiệm;
   semantic truth của key chứng minh tồn tại ít nhất một nghiệm. Suy ra đúng một.
4. No-guess: harness khởi tạo đúng thông tin thẻ mở sẵn. Reasoner chỉ nhận clue
   đã mở, chọn first-forced row-major. Harness kiểm tra verdict, sau đó mới thêm
   clue của owner. Ghi source clue và tập clue active cho từng bước. Kiểm tra cả
   clue cuối sau reveal. Không tạo bằng chứng SAT giả để gửi vào GameEngine.
5. Riêng năm map 3×3 còn đối chiếu độc lập toàn bộ 512 assignment, và chạy
   sequential checker duyệt cạn của Hiệp. Không nâng giới hạn duyệt cạn cho 4×4/5×5.

Chứng chỉ từng bước lưu ở [phuoc_validation.json](phuoc_validation.json).
Đây là chứng minh ngữ nghĩa xây dựng, **chưa phải SAT validation**. Thuật toán
local là điều kiện đủ, không đầy đủ: gặp map khó hơn có thể không chứng minh
được mặc dù map hợp lệ; khi đó báo lỗi chứng nhận, không kết luận vô nghiệm.
Tools này chỉ phục vụ tác giả dữ liệu, không thay LogicAgent/CNF/DPLL production.

## E. Kết quả kiểm thử

Bảng từng testcase và trạng thái thực chạy được lưu tại
[phuoc_test_results.md](phuoc_test_results.md). Không tính test tích hợp bị skip
là passed. Bộ test bao gồm:

- Bốn verdict, ví dụ đề, empty CNF/clause, tautology, biến vắng khỏi KB.
- KB chỉ kiểm tra một lần trong batch; thứ tự/calls chính xác; kết quả bất biến.
- Solver sửa CNF, input sai kiểu/0/bool, variable trùng, auxiliary, output sai,
  hai giả định UNSAT trái với base SAT, adapter và timeout.
- Dataset: schema, đủ 15 map, 6 clue/4 vùng, tên, ngữ nghĩa, chứng minh uniqueness,
  no-guess, seed tái lập byte-for-byte và các dữ liệu lỗi.
- Regression map unique nhưng kẹt và map mơ hồ; spy bảo đảm clue chưa mở không
  được đưa vào reasoner; guard không duyệt hơn 8 biến local.
- Core thật: load/restart 15 map; bridge bằng FACT public với SAT oracle chỉ
  trong tests; nhận ACCEPTED, từ chối UNKNOWN/CONTRADICTED và proof version cũ.
- 30 ca end-to-end dành cho DPLL/CNF thật, skip rõ dependency còn thiếu.

## F. Tích hợp với nhóm

```text
Private puzzle -> GameEngine -> PublicKBSnapshot -> CNFEncoder
                -> EntailmentChecker(DPLL, frozen VariableMap)
                -> official EntailmentResult -> GameEngine.submit_verdict
```

Ví dụ ghép có dependency injection, chỉ dùng dữ liệu công khai để chọn bước:

```python
from src.agent.entailment import EntailmentChecker, Verdict

def prove_next(snapshot, variable_map, solver, encode_clue, public_cell_ids):
    cnf = []
    for clue in snapshot.revealed_clues:
        cnf.extend(encode_clue(clue, variable_map))
    cnf += snapshot.get_unit_clauses_for_verdicts()
    unresolved = {cid: variable_map.get_var(cid) for cid in public_cell_ids
                  if cid not in snapshot.proved_verdicts}
    checker = EntailmentChecker(solver, variable_map=variable_map)
    batch = checker.classify_all(cnf, unresolved)
    for cid, result in batch.results.items():
        if result.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT):
            return cid, result.to_engine_result(cid, snapshot.version), batch
    return None, None, batch

# Controller sở hữu engine; engine không được truyền xuống prove_next:
# snapshot = engine.get_public_snapshot()
# cid, proof, batch = prove_next(snapshot, engine.var_map, solver,
#                               encode_clue, [c.id for c in engine.characters])
# if proof is not None:
#     engine.submit_verdict(cid, proof.status is Verdict.CRIMINAL, proof)
```

| Thành viên | Đã xác minh | Công việc tích hợp tiếp theo |
|---|---|---|
| Hiệp | Schema, loader, PublicKB, mapping, Core result, proof version và submit | Core smoke/bridge đã chạy; full pipeline còn chờ Encoder/DPLL |
| Huy | DPLL file rỗng | Chốt API solver và dạng SAT/UNSAT; nếu cần dùng SolverAdapter |
| Phong | CNF Encoder file rỗng; VariableMap re-export đúng | Chốt encode(Clue, VariableMap), quản lý aux, thêm unit verdict |
| Tài | semantic_eval/extended_clues rỗng | Chạy đối chiếu evaluator chính thức khi có; hiện dùng evaluator của Hiệp |

`tests/test_integration_phuoc.py` đề xuất binding `DPLLSolver().solve(CNF)->bool`
và `CNFEncoder().encode(clue, variable_map)->CNF`. **Chưa phải API chính thức
của Huy/Phong.** Khi các bạn công bố API, chỉnh fixture `team_bindings` và helper
`encode_clues` thay vì sửa source của các bạn. Test runtime fail sau khi có binding
sẽ báo FAILED, không bị che thành SKIPPED. Uniqueness integration có bước SAT
với key primary units rồi blocking clause chỉ trên primary; không block auxiliary.

## G. Hạn chế, tái chạy và bàn giao

Chưa đo runtime/decision/propagation/backtrack của DPLL, số clauses/aux thực tế
hoặc độ khó. Chưa có GUI, LogicAgent hoàn chỉnh hay tích hợp extension. Đây là
phạm vi các giai đoạn/thành viên khác. Không tuyên bố pipeline end-to-end đã đạt.

Chạy từ root repository trên Ubuntu, Python >=3.10:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/test_entailment.py -v
.venv/bin/python -m tools.generate_puzzles
.venv/bin/python -m tools.validate_puzzles --report docs/phuoc_validation.json
.venv/bin/python -m pytest tests/test_puzzles.py -v
.venv/bin/python -m pytest tests/test_integration_phuoc.py -v -rs
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src tests tools
```

Nếu Ubuntu thiếu ensurepip: cài gói `python3-venv`, hoặc dùng system pip đã có
như môi trường thực chạy này:

```bash
python3 -m venv --without-pip .venv
pip --python .venv/bin/python install -r requirements-dev.txt
```

Lệnh direct script tương đương: `.venv/bin/python tools/generate_puzzles.py` và
`.venv/bin/python tools/validate_puzzles.py`. Generator chỉ ghi 15 map và manifest,
không sửa sample của Hiệp. Custom output: `--output-dir /tmp/my-puzzles`; validator
nhận `--directory /tmp/my-puzzles`. Khi đổi seed, các certificate phải được kiểm
định lại; không tự giữ manifest PASSED cũ.

AI hỗ trợ triển khai và kiểm thử phần Phước theo prompt đính kèm ngày 09/11/2026.
Khi viết report nhóm, ghi việc sử dụng AI và prompt theo mục Appendix của đề;
thành viên cần hiểu các truy vấn phủ định, chứng minh uniqueness và ranh giới
public/private để giải thích trong vấn đáp.
