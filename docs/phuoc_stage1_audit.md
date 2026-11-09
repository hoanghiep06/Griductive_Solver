# Repository audit trước triển khai — 09/11/2026

Baseline: `feat/hiep/core`, working tree sạch. Đã đọc cây file tracked,
toàn bộ source hiện có, schema, sample, tests và hai tài liệu TV1; không có
AGENTS.md áp dụng. Nhánh triển khai: `feature/phuoc-entailment-puzzles`.

| Thành phần | Trạng thái xác minh | Hợp đồng sử dụng |
|---|---|---|
| Hiệp: core, loader, validator | Có implementation và unittest | Schema 1.0, `GameEngine(path)`, `get_public_snapshot()`, `submit_verdict(cid, bool, EntailmentResult)` |
| PublicKB | Có snapshot bất biến, version, unit clauses | `revealed_clues`, `proved_verdicts`, `get_unit_clauses_for_verdicts()` |
| VariableMap | Có; canonical tại `src/core/variable_map.py` | Theo tên; primary frozen, auxiliary tách biệt; dùng `get_var()`, không suy từ tọa độ |
| EntailmentResult | Có hợp đồng chính thức của Hiệp | `from_sat_results()`, character ID + KB version; tái sử dụng, không định nghĩa lại |
| Huy: DPLL | File rỗng | Chưa có API thực tế; đề xuất adapter `solve(CNF) -> bool` |
| Phong: CNF Encoder | File rỗng | CNF chuẩn `list[list[int]]`; API encode chưa được chốt |
| Tài: semantic_eval, extended_clues | File rỗng | Dataset dùng sáu core clue và evaluator hiện có của Hiệp |
| Agent/GUI/main/benchmark | File rỗng | Chỉ triển khai entailment trong phạm vi Phước |
| Dataset hiện có | `sample_3x3.json` của Hiệp | Giữ nguyên sample; manifest liệt kê riêng đúng 15 map của Phước |

Validator của Hiệp kiểm tra cấu trúc và sự thật của clue. Sequential checker
duyệt cạn chỉ tối đa 9 nhân vật; không dùng cho 4×4/5×5. Cần chứng minh xây dựng
độc lập, không giả nhận đã chạy DPLL/Encoder. Không thay module của thành viên khác.

Môi trường đầu vào: Python 3.14.4 qua `python3`; không có lệnh `python`, pytest
chưa cài. Tạo `.venv` và dependency dev riêng để chạy pytest và JSON Schema.
