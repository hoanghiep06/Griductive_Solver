# Stage 2 — Hướng dẫn bắt đầu cho Tài, Phước và Hiệp

**18/11/2026 · V1 · PROPOSED — chờ nhóm review.**
Gói này gồm tài liệu kiến trúc và contracts; chưa triển khai Logic Agent, Controller hoặc GUI.
Đọc audit theo checkout `011982e`, không coi đây là trạng thái mới nhất của mọi nhánh remote.

## Đọc theo thứ tự

1. [Shared Baseline](STAGE2_SHARED_BASELINE.md): hiện trạng, phân lớp, ownership, state machine, merge order.
2. [API Contract](STAGE2_API_CONTRACT.md): nguồn chuẩn DTO, signatures, signals, lỗi, cancellation.
3. [UI Design](STAGE2_UI_DESIGN.md): bốn màn hình, component interfaces, tokens, animation/layout.
4. [Integration Checklist](STAGE2_INTEGRATION_CHECKLIST.md): điều kiện review riêng và tích hợp chung.

`CONFIRMED`: có thật trong source hoặc yêu cầu phạm vi. `PROPOSED`: thiết kế mới chưa được nhóm duyệt.
`BLOCKED`: cần module/quyết định khác trước khi kiểm chứng runtime.

## Đã xác nhận gì, đang đề xuất gì?

**CONFIRMED:** Core, PublicKBSnapshot, VariableMap, EntailmentResult, EntailmentChecker và 15 map đã có trong checkout.
DPLL và CNF Encoder vẫn là file rỗng; Agent/GUI/controller chưa có implementation dùng được.
Yêu cầu hiện tại giao **Agent cho Tài**, **GUI cho Phước**, **Controller cho Hiệp**.
Tài liệu TV1 Stage 1 cũ có ownership khác; không dùng số TV cũ để suy ra người viết phần Stage 2.

**PROPOSED:** PySide6 + Qt Widgets, QGraphicsView/Scene, Qt Animation, Signals/Slots;
DTO immutable/pure Python; MainWindow là ViewPort; Controller giữ workflow; Agent chỉ phân tích public KB.
V1 chưa được cả nhóm phê duyệt, chưa pin/cài PySide6 hoặc pytest-qt.

## Mỗi người làm độc lập thế nào?

| Thành viên | Được sửa trong nhánh riêng | Đầu vào để bắt đầu | Không triển khai chồng |
|---|---|---|---|
| **Tài** | `src/agent/logic_agent.py`, `deduction_trace.py`, `uniqueness.py`, adapter `bindings.py` nếu cần; agent tests | Public AnalysisContext + solver/encoder doubles trong tests | Không sửa EntailmentChecker/Core, không import Qt, không gọi Engine.submit_verdict |
| **Phước** | `src/gui/`, GUI assets/styles/tests | Public DTO mocks tự dựng; API ViewPort và UI spec | Không đọc raw puzzle/HTML preview payload, không resolve clue region, không sửa main/controller |
| **Hiệp** | `src/controller/`, `main.py`, controller tests; cấu hình chung sau review | Fake ViewPort + fake LogicAgentPort trong tests | Không viết deduction/GUI internals; không truy cập child widgets |

Các file Stage 1 giữ owner hiện tại. `src/shared/` chưa tạo; sau review Hiệp materialize DTO/Enum/Protocol,
Tài và Phước review. Không tạo `GuiVerdict`, `AgentVerdict`, `ControllerVerdict` khác nhau: reuse EntailmentStatus của Core.
Không thay đổi breaking interface trong shared mà không thông báo và cập nhật cả ba consumer.

## Những API phải giữ nhất quán

- GUI phát event qua MainWindow; Controller gọi ViewPort, bao gồm `show_gameplay`, `set_board`, `reveal_card`, `show_hint`.
- `animation_finished(cell_id, token)` có AnimationToken; không quay về signature chỉ có cell ID.
- Agent nhận AnalysisContext; trả BatchResult/ForcedVerdict/HintView theo API; không nhận Engine hoặc raw Puzzle.
- Core submit giữ nguyên `(char_id, claimed_status: bool, entailment: EntailmentResult)`.
- Claim chỉ CRIMINAL/INNOCENT; NOT_PROVABLE/CONTRADICTED không lật thẻ.
- Controller loại stale token trước commit; Engine kiểm tra KB version. Animation xong mới chạy Auto bước tiếp.
- Agent trace là đề xuất suy luận theo KB hiện tại; accepted history do Controller ghi sau commit, không lẫn với Hint.
- Public uniqueness không phải full-puzzle uniqueness. Không truyền hidden clues vào runtime Agent để kiểm tra toàn bộ màn.

## Cách tích hợp

1. Review D1–D9 trong Shared Baseline, ghi rõ lựa chọn còn mở; đặc biệt worker và Encoder/DPLL binding.
2. Hiệp kiểm tra main đã có Stage 1 cần dùng. Merge tài liệu baseline trước, rồi shared contracts/dependencies.
3. Ba nhánh dựa cùng main revision, viết tests riêng với doubles; doubles chỉ ở tests.
4. Tích hợp Agent với Encoder/DPLL thật; nối ViewPort vào Controller; chạy checklist full system trên 15 map.
5. Mọi API thay đổi cần sửa `STAGE2_API_CONTRACT.md` và phối hợp consumer cùng PR. Không sửa âm thầm internal module của người khác.

Nhánh dự kiến: `feat/tai/stage2-logic-agent`, `feat/phuoc/stage2-gui`, `feat/hiep/stage2-controller`.
Gói docs nằm ở `docs/phuoc/stage2-shared-baseline`; shared types dự kiến ở `feat/hiep/stage2-shared-contracts`.
Tuân thủ `<type>/<member>/<feature>` và commit `type(scope): mô tả ngắn`; chia commit theo thay đổi nhỏ.
Chưa push/merge main trong bước baseline này.

## Những việc cần nhóm xác nhận

- DTO/ports, token lifecycle, atomic projection và ownership maintainer shared.
- Python dev, phiên bản PySide6/pytest-qt; smoke test trên máy nhóm.
- Encoder cần metadata vùng thế nào; DPLL trả bool/model/metrics/error ra sao.
- Worker mechanism, deadline/cancel; không block GUI hay terminate thread cưỡng bức.
- Mức giải thích Hint/Trace: toàn bộ public KB hay verified subset; không mặc định có minimum-support algorithm.
- Public uniqueness capability và UI design tokens/minimum window/animation policy.

Không dùng reference MiniSat/tools để giả nhận DPLL nhóm đã hoàn thành; không lấy authoring trace làm lời giải runtime.
Không sửa dataset, schema hoặc implement nghiệp vụ đầy đủ trong PR baseline. Sau khi nhóm duyệt, mới triển khai phần riêng.
