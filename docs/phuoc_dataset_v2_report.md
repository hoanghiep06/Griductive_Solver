# Dataset V2 — Nguyễn Hoài Phước

Ngày kiểm định: 10/11/2026. Baseline được giữ nguyên từ commit `b940b8c`.

## A. Đánh giá lại baseline bằng cùng một phép đo SAT

Cả V1 và V2 đều dùng first-forced row-major, giữ nguyên tất cả verdict đã biết K.
Không lấy số bước từ chứng chỉ local V1 cũ để so với trace SAT V2.

| Bộ | Puzzle | Lượt suy luận | Single-clue | Multi-clue | Support ≥3 |
|---|---:|---:|---:|---:|---:|
| V1 | 15 | 229 | 221 | 8 | 0 |
| V2 | 15 | 214 | 127 | 87 | 23 |

Baseline vẫn có một số bước multi-clue theo trace SAT row-major. Đặc biệt 3x3_04
đã có 3 bước; không mặc định tất cả map cũ chỉ single-clue. Phần lớn baseline
là chuỗi suy luận trực tiếp. Coverage V1 đã đủ sáu clue và bốn vùng.

## B. Kết quả từng màn

| Puzzle | Size | Nhãn đo theo heuristic | Mở sẵn | Steps | V1 multi | V2 multi | ≥3 clue | Unique | No-guess | Mục tiêu multi |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 3x3_01 | 3×3 | Tutorial (0.93) | 1 | 8 | 0 | 0 | 0 | PASSED | PASSED | 0 ≥ 0: PASS |
| 3x3_02 | 3×3 | Easy (17.45) | 2 | 7 | 1 | 1 | 0 | PASSED | PASSED | 1 ≥ 0: PASS |
| 3x3_03 | 3×3 | Medium (29.91) | 2 | 7 | 0 | 3 | 0 | PASSED | PASSED | 3 ≥ 1: PASS |
| 3x3_04 | 3×3 | Medium (29.85) | 2 | 7 | 3 | 3 | 0 | PASSED | PASSED | 3 ≥ 1: PASS |
| 3x3_05 | 3×3 | Hard (40.59) | 3 | 6 | 0 | 2 | 1 | PASSED | PASSED | 2 ≥ 1: PASS |
| 4x4_01 | 4×4 | Medium (26.44) | 2 | 14 | 0 | 5 | 0 | PASSED | PASSED | 5 ≥ 3: PASS |
| 4x4_02 | 4×4 | Medium (26.62) | 2 | 14 | 1 | 5 | 0 | PASSED | PASSED | 5 ≥ 3: PASS |
| 4x4_03 | 4×4 | Hard (42.4) | 3 | 13 | 0 | 5 | 2 | PASSED | PASSED | 5 ≥ 3: PASS |
| 4x4_04 | 4×4 | Very Hard (48.11) | 3 | 13 | 1 | 6 | 3 | PASSED | PASSED | 6 ≥ 3: PASS |
| 4x4_05 | 4×4 | Very Hard (48.16) | 3 | 13 | 0 | 6 | 3 | PASSED | PASSED | 6 ≥ 3: PASS |
| 5x5_01 | 5×5 | Medium (29.84) | 2 | 23 | 0 | 10 | 0 | PASSED | PASSED | 10 ≥ 6: PASS |
| 5x5_02 | 5×5 | Medium (29.89) | 2 | 23 | 1 | 10 | 0 | PASSED | PASSED | 10 ≥ 6: PASS |
| 5x5_03 | 5×5 | Hard (46.18) | 3 | 22 | 0 | 10 | 4 | PASSED | PASSED | 10 ≥ 6: PASS |
| 5x5_04 | 5×5 | Very Hard (47.57) | 3 | 22 | 1 | 10 | 5 | PASSED | PASSED | 10 ≥ 6: PASS |
| 5x5_05 | 5×5 | Very Hard (49.67) | 3 | 22 | 0 | 11 | 5 | PASSED | PASSED | 11 ≥ 6: PASS |

Nhãn mục tiêu trong yêu cầu và nhãn từ số liệu được lưu riêng trong manifest.
Ví dụ hai màn 5×5 đầu được chấm Medium theo quy tắc dù mục tiêu thiết kế là
Medium-Hard/Hard. Không nâng nhãn bằng tay để khớp bảng mong muốn.

## C. Thiết kế và chất lượng suy luận

- Giữ 3x3_01 làm tutorial và giữ 3x3_02 làm easy reference. 13 map còn lại được thiết kế lại.
- Pair stage: DIFFERENT(a,b) hoặc EXACTLY(1,[a,b]) cùng một counting clue trên [a,b,c] ép c.
- Overlapping-count stage: hai phương trình đếm có phần giao chung, dùng hiệu số để ép biến còn lại.
- Bridge stage: SAME(a,b), DIFFERENT(b,c), EXACTLY(1+d,[a,c,d]) ép d với support 3; clue của d mở khóa a,b,c bằng support nhỏ hơn.
- Triangle stage: ba counting constraint phối hợp; không một cặp nào đủ chứng minh verdict đầu.
- Khi vùng tự nhiên chứa đúng các biến stage chưa giải và filler đã biết, generator dùng ROW/COLUMN/NEIGHBORS thay EXPLICIT.
- Các stage có nhiều verdict forced cùng lúc. Trace lưu toàn bộ lựa chọn và UNKNOWN→forced.
- FACT giới hạn 1–3 mỗi map. Không sinh counting singleton hoặc AT_LEAST(0)/AT_MOST(|R|) trong V2 mới.
- Tất cả candidate phải đạt unique, no-guess và số bước multi mục tiêu trước khi được xuất.

Đây vẫn là generator theo mô-đun constraint, chưa phải thiết kế thủ công đa phong cách.
Một số nhóm stage còn nối tiếp nhau; số liệu chỉ chứng nhận trace row-major đã chạy,
không bảo đảm mọi thứ tự chơi đều có cùng support hoặc cùng số bước multi.

### Cách xác nhận support tối thiểu

Ở từng bước, giữ toàn bộ K. Kiểm tra SAT(K ∧ R) và UNSAT(K ∧ R ∧ opposite).
Thu nhỏ một witness để lấy cận trên, sau đó duyệt tập con theo cardinality tăng dần.
Mọi tập con nhỏ hơn witness cuối đều phải SAT với opposite. Đây là minimum cardinality,
không chỉ một irreducible UNSAT core. Tất cả SAT results được lưu trong trace.
Support ba clue được xác nhận sau khi kiểm tra cả tập rỗng, mọi singleton và mọi pair.

### Phát hiện map gần trùng

WL fingerprint chạy bốn vòng trên đồ thị hai phía nhân vật/clue, có cạnh ownership và scope.
Màu nút gồm kiểu clue, vùng, cardinality và thẻ mở sẵn; không dùng tên hoặc ID cell.
Test hoán vị cell xác nhận tính bất biến. 15 fingerprint đều khác nhau.
So sánh histogram: 50% clue family + 25% kích thước scope + 25% minimum-support histogram.
Ngưỡng cờ review 0.96: 0 cặp. Đây là cảnh báo thống kê, không phải chứng minh hai puzzle khác nhau về mọi mặt.

### Quy tắc độ khó (chủ quan, công khai trọng số)

score = 45·multi_ratio + 30·triple_ratio + 20·min(max(max_support−1,0)/2,1) + 5·mean_scope_Jaccard.
Không có điểm thưởng theo N. Không có điểm runtime. Tutorial nếu không có multi;
Easy nếu score<18, Medium nếu <35, Hard nếu <47, còn lại Very Hard.
Điểm thưởng support cực đại giúp phản ánh bước cần 3 clue; overlap chỉ chiếm 5% để hạn chế filler làm tăng điểm.
Các chỉ số lựa chọn forced, SAT calls và clause count được báo riêng. Score chưa được hiệu chuẩn với người chơi.

## D. CNF, SAT và ranh giới tích hợp

Đã chạy MiniSat22 của python-sat 1.9.dev21 trong tools, cùng reference encoder combinatorial.
Đã đối chiếu CNF với evaluator độc lập của Hiệp trên mọi assignment thuộc scope của từng clue
trong cả 15 map, cùng các ca biên k=0 và k=|R|. Encoder tham chiếu không có biến phụ.
Selector variables chỉ kích hoạt nhóm clause trong harness; không được tính là nhân vật hoặc đưa vào blocking clause.
Uniqueness dùng model SAT đầu tiên, block toàn bộ primary assignment đó, lần hai UNSAT.
CNF full trong bảng sau là CNF tham chiếu trước khi thêm selectors/known-status units.

| Puzzle | Primary | Aux encoding | Full reference clauses | Calls phân loại | Calls reference gồm support |
|---|---:|---:|---:|---:|---:|
| 3x3_01 | 9 | 0 | 19 | 80 | 176 |
| 3x3_02 | 9 | 0 | 33 | 63 | 152 |
| 3x3_03 | 9 | 0 | 23 | 63 | 173 |
| 3x3_04 | 9 | 0 | 23 | 63 | 176 |
| 3x3_05 | 9 | 0 | 44 | 48 | 127 |
| 4x4_01 | 16 | 0 | 107 | 224 | 599 |
| 4x4_02 | 16 | 0 | 134 | 224 | 600 |
| 4x4_03 | 16 | 0 | 174 | 195 | 715 |
| 4x4_04 | 16 | 0 | 83 | 195 | 815 |
| 4x4_05 | 16 | 0 | 111 | 195 | 631 |
| 5x5_01 | 25 | 0 | 224 | 575 | 1932 |
| 5x5_02 | 25 | 0 | 342 | 575 | 1934 |
| 5x5_03 | 25 | 0 | 105 | 528 | 2584 |
| 5x5_04 | 25 | 0 | 130 | 528 | 3520 |
| 5x5_05 | 25 | 0 | 280 | 528 | 3495 |

**Benchmark DPLL của Huy + Encoder của Phong: BLOCKED.** Hai file vẫn rỗng ở snapshot này.
Không có decision/propagation/backtrack/runtime của DPLL nhóm để báo. Stats MiniSat trong JSON
được ghi nhãn reference_solver_stats, không đổi tên thành DPLL backtracks.
Semantic Evaluator của Tài vẫn rỗng: dùng evaluator Core của Hiệp và không sửa module của Tài.
Đã có test full reveal với GameEngine thật + EntailmentChecker thật + reference encoder/SAT, chạy hai lần kiểm tra deterministic.

## E. Ba ví dụ lấy từ trace thực tế

### 3x3_03 — bước 1: C2

K trước khi suy luận (toàn bộ verdict đã biết):
```json
{
  "B2": false,
  "A3": true
}
```
Clue đang công khai: CLUE_B2, CLUE_A3.

Support tối thiểu: CLUE_B2, CLUE_A3.

```json
[
  {
    "clue_id": "CLUE_B2",
    "owner_id": "B2",
    "type": "DIFFERENT",
    "parameters": {
      "target1": "B1",
      "target2": "C3"
    }
  },
  {
    "clue_id": "CLUE_A3",
    "owner_id": "A3",
    "type": "EXACTLY",
    "parameters": {
      "k": 2,
      "region_type": "EXPLICIT",
      "cells": [
        "B1",
        "C2",
        "C3"
      ]
    }
  }
]
```

Công thức: K ∧ CNF(support). Quy ước +i=Criminal, −i=Innocent. Mapping và CNF thực tế:
```json
{
  "primary_mapping": {
    "A1": 1,
    "B1": 2,
    "C1": 3,
    "A2": 4,
    "B2": 5,
    "C2": 6,
    "A3": 7,
    "B3": 8,
    "C3": 9
  },
  "clauses_by_clue": {
    "CLUE_B2": [
      [
        2,
        9
      ],
      [
        -2,
        -9
      ]
    ],
    "CLUE_A3": [
      [
        -2,
        -6,
        -9
      ],
      [
        2,
        6
      ],
      [
        2,
        9
      ],
      [
        6,
        9
      ]
    ]
  },
  "opposite_assumption": -6
}
```

SAT(K ∧ support) = SAT; SAT(K ∧ support ∧ opposite) = UNSAT.
Đã kiểm tra 4 tập con trong phép tìm cardinality tối thiểu; mọi tập nhỏ hơn 2 đều SAT với opposite.

Lý do UNSAT, kiểm tra độc lập: sau khi cố định K và giả định ngược, còn 2 biến local; cả 4 assignment đều vi phạm ít nhất một clue support:

| Assignment còn lại | Clue bị vi phạm |
|---|---|
| B1=I, C3=I | CLUE_B2, CLUE_A3 |
| B1=I, C3=C | CLUE_A3 |
| B1=C, C3=I | CLUE_A3 |
| B1=C, C3=C | CLUE_B2 |

Kết luận: C2 là CRIMINAL. Sau chấp nhận mới reveal CLUE_C2.

### 4x4_02 — bước 1: B4

K trước khi suy luận (toàn bộ verdict đã biết):
```json
{
  "A1": false,
  "A2": true
}
```
Clue đang công khai: CLUE_A1, CLUE_A2.

Support tối thiểu: CLUE_A1, CLUE_A2.

```json
[
  {
    "clue_id": "CLUE_A1",
    "owner_id": "A1",
    "type": "EXACTLY",
    "parameters": {
      "k": 2,
      "region_type": "COLUMN",
      "index": 0
    }
  },
  {
    "clue_id": "CLUE_A2",
    "owner_id": "A2",
    "type": "AT_LEAST",
    "parameters": {
      "k": 2,
      "region_type": "EXPLICIT",
      "cells": [
        "A3",
        "A4",
        "B4"
      ]
    }
  }
]
```

Công thức: K ∧ CNF(support). Quy ước +i=Criminal, −i=Innocent. Mapping và CNF thực tế:
```json
{
  "primary_mapping": {
    "A1": 1,
    "B1": 2,
    "C1": 3,
    "D1": 4,
    "A2": 5,
    "B2": 6,
    "C2": 7,
    "D2": 8,
    "A3": 9,
    "B3": 10,
    "C3": 11,
    "D3": 12,
    "A4": 13,
    "B4": 14,
    "C4": 15,
    "D4": 16
  },
  "clauses_by_clue": {
    "CLUE_A1": [
      [
        -1,
        -5,
        -9
      ],
      [
        -1,
        -5,
        -13
      ],
      [
        -1,
        -9,
        -13
      ],
      [
        -5,
        -9,
        -13
      ],
      [
        1,
        5,
        9
      ],
      [
        1,
        5,
        13
      ],
      [
        1,
        9,
        13
      ],
      [
        5,
        9,
        13
      ]
    ],
    "CLUE_A2": [
      [
        9,
        13
      ],
      [
        9,
        14
      ],
      [
        13,
        14
      ]
    ]
  },
  "opposite_assumption": -14
}
```

SAT(K ∧ support) = SAT; SAT(K ∧ support ∧ opposite) = UNSAT.
Đã kiểm tra 4 tập con trong phép tìm cardinality tối thiểu; mọi tập nhỏ hơn 2 đều SAT với opposite.

Lý do UNSAT, kiểm tra độc lập: sau khi cố định K và giả định ngược, còn 2 biến local; cả 4 assignment đều vi phạm ít nhất một clue support:

| Assignment còn lại | Clue bị vi phạm |
|---|---|
| A3=I, A4=I | CLUE_A1, CLUE_A2 |
| A3=I, A4=C | CLUE_A2 |
| A3=C, A4=I | CLUE_A2 |
| A3=C, A4=C | CLUE_A1 |

Kết luận: B4 là CRIMINAL. Sau chấp nhận mới reveal CLUE_B4.

### 5x5_05 — bước 1: A2

K trước khi suy luận (toàn bộ verdict đã biết):
```json
{
  "E2": true,
  "C1": false,
  "E3": true
}
```
Clue đang công khai: CLUE_E2, CLUE_C1, CLUE_E3.

Support tối thiểu: CLUE_E2, CLUE_C1, CLUE_E3.

```json
[
  {
    "clue_id": "CLUE_E2",
    "owner_id": "E2",
    "type": "SAME",
    "parameters": {
      "target1": "A3",
      "target2": "E1"
    }
  },
  {
    "clue_id": "CLUE_C1",
    "owner_id": "C1",
    "type": "DIFFERENT",
    "parameters": {
      "target1": "E1",
      "target2": "B3"
    }
  },
  {
    "clue_id": "CLUE_E3",
    "owner_id": "E3",
    "type": "EXACTLY",
    "parameters": {
      "k": 3,
      "region_type": "EXPLICIT",
      "cells": [
        "A2",
        "E2",
        "A3",
        "B3",
        "E3"
      ]
    }
  }
]
```

Công thức: K ∧ CNF(support). Quy ước +i=Criminal, −i=Innocent. Mapping và CNF thực tế:
```json
{
  "primary_mapping": {
    "A1": 1,
    "B1": 2,
    "C1": 3,
    "D1": 4,
    "E1": 5,
    "A2": 6,
    "B2": 7,
    "C2": 8,
    "D2": 9,
    "E2": 10,
    "A3": 11,
    "B3": 12,
    "C3": 13,
    "D3": 14,
    "E3": 15,
    "A4": 16,
    "B4": 17,
    "C4": 18,
    "D4": 19,
    "E4": 20,
    "A5": 21,
    "B5": 22,
    "C5": 23,
    "D5": 24,
    "E5": 25
  },
  "clauses_by_clue": {
    "CLUE_E2": [
      [
        -11,
        5
      ],
      [
        11,
        -5
      ]
    ],
    "CLUE_C1": [
      [
        5,
        12
      ],
      [
        -5,
        -12
      ]
    ],
    "CLUE_E3": [
      [
        -6,
        -10,
        -11,
        -12
      ],
      [
        -6,
        -10,
        -11,
        -15
      ],
      [
        -6,
        -10,
        -12,
        -15
      ],
      [
        -6,
        -11,
        -12,
        -15
      ],
      [
        -10,
        -11,
        -12,
        -15
      ],
      [
        6,
        10,
        11
      ],
      [
        6,
        10,
        12
      ],
      [
        6,
        10,
        15
      ],
      [
        6,
        11,
        12
      ],
      [
        6,
        11,
        15
      ],
      [
        6,
        12,
        15
      ],
      [
        10,
        11,
        12
      ],
      [
        10,
        11,
        15
      ],
      [
        10,
        12,
        15
      ],
      [
        11,
        12,
        15
      ]
    ]
  },
  "opposite_assumption": 6
}
```

SAT(K ∧ support) = SAT; SAT(K ∧ support ∧ opposite) = UNSAT.
Đã kiểm tra 8 tập con trong phép tìm cardinality tối thiểu; mọi tập nhỏ hơn 3 đều SAT với opposite.

Lý do UNSAT, kiểm tra độc lập: sau khi cố định K và giả định ngược, còn 3 biến local; cả 8 assignment đều vi phạm ít nhất một clue support:

| Assignment còn lại | Clue bị vi phạm |
|---|---|
| A3=I, B3=I, E1=I | CLUE_C1 |
| A3=I, B3=I, E1=C | CLUE_E2 |
| A3=I, B3=C, E1=I | CLUE_E3 |
| A3=I, B3=C, E1=C | CLUE_E2, CLUE_C1, CLUE_E3 |
| A3=C, B3=I, E1=I | CLUE_E2, CLUE_C1, CLUE_E3 |
| A3=C, B3=I, E1=C | CLUE_E3 |
| A3=C, B3=C, E1=I | CLUE_E2, CLUE_E3 |
| A3=C, B3=C, E1=C | CLUE_C1, CLUE_E3 |

Kết luận: A2 là INNOCENT. Sau chấp nhận mới reveal CLUE_A2.

## F. Tái chạy và review

```bash
pip --python .venv/bin/python install -r requirements-dev.txt
.venv/bin/python -m tools.generate_puzzles
.venv/bin/python -m tools.validate_puzzles --report docs/phuoc_validation.json
.venv/bin/python -m tools.report_dataset
.venv/bin/python -m tools.build_preview
.venv/bin/python -m pytest -q
xdg-open tools/preview_puzzles.html
```

Python >=3.10. Nếu chưa có .venv: `python3 -m venv .venv` trước khi cài dependency.
Preview tự chứa dữ liệu offline: chọn V1/V2 và map, kéo bước hoặc dùng mũi tên;
clue support tô xanh, bấm clue để highlight scope. Chế độ đáp án tách riêng và mặc định tắt.
Đây là công cụ review dữ liệu của tác giả, không thay GUI nhóm và không bảo mật key trong HTML.

## G. Hạn chế và trạng thái kiểm thử

- Tất cả 15 map unique/no-guess; cả 15 đạt mục tiêu multi tương ứng. 13 map được tái thiết kế.
- Exact support đo theo một trace row-major và toàn bộ K, không đánh giá mọi thứ tự giải.
- Generator mô-đun còn tái sử dụng một số gadget. Fingerprint/histogram không phải kiểm tra graph isomorphism hoàn chỉnh.
- Một số clue không xuất hiện trong support tối thiểu được chọn. JSON liệt kê các clue đó; điều này không chứng minh clue vô ích trong mọi trace.
- 5×5_05 là stress candidate về cấu trúc; chưa xác nhận stress/runtime của DPLL nhóm.
- Quy tắc difficulty chưa được user-study; một màn 4×4 có thể được chấm cao hơn 5×5.
- Generator chỉ publish sau khi batch pass và khôi phục bytes cũ khi lỗi ghi. Rollback không bảo đảm trước mất điện/process kill.
- Kết quả pytest thực chạy nằm ở `docs/phuoc_dataset_v2_tests.md`; 30 test team DPLL/CNF vẫn SKIPPED/BLOCKED.

Không sửa schema, Core, GUI, DPLL hoặc Encoder của các thành viên khác. Production EntailmentChecker giữ nguyên.
Baseline đầy đủ trong puzzles_baseline/ và Git commit b940b8c.
