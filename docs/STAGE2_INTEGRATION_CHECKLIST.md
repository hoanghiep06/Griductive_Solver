# Stage 2 — Integration Checklist V1

Ngày: **18/11/2026**. Checklist nghiệm thu implementation **sau baseline**, chưa phải kết quả test Stage 2.
Các mục `[ ]` chưa được xác minh. Contract chuẩn: [API](STAGE2_API_CONTRACT.md),
[kiến trúc](STAGE2_SHARED_BASELINE.md), [UI](STAGE2_UI_DESIGN.md).

## Gate 0 — Chấp thuận baseline và dependencies

- [ ] Tài, Phước, Hiệp review D1–D9; PROPOSED chỉ đổi nhãn khi có quyết định thực tế.
- [ ] Xác nhận revision main có Core/Entailment/dataset cần dùng; không dựa vào suy đoán remote.
- [ ] Materialize shared contracts sau review, đúng field/types/signatures; không định nghĩa lại Core verdict/CNF/map.
- [ ] Một maintainer shared, hai consumer reviewers; thay đổi breaking có kế hoạch cập nhật đồng bộ.
- [ ] Chốt Python/PySide6/pytest-qt version, import smoke test và Qt desktop launch trên máy nhóm.
- [ ] Huy xác nhận DPLL bool/model/error/metrics API; Phong xác nhận encoder/region/auxiliary API.
- [ ] Phân biệt team integration BLOCKED với reference authoring PASSED; không dùng fallback tools trong production.

## Tài — Logic Agent

- [ ] `logic_agent.py`, `deduction_trace.py`, `uniqueness.py` và adapter thuộc Tài; không sửa Core/Checker của người khác.
- [ ] Không Qt import, không Engine/Puzzle/path input, chỉ AnalysisContext public.
- [ ] CNF chỉ từ snapshot.revealed_clues và proved unit clauses; kiểm tra cả Innocent False không bị bỏ sót.
- [ ] VariableMap canonical/frozen primary, không hardcode row-major SAT IDs; allocation auxiliary an toàn trong serial worker.
- [ ] `classify_unresolved` trả BatchResult chính thức; base UNSAT rõ ràng kể cả unresolved rỗng.
- [ ] Forced theo row-major; `None` không che INCONSISTENT; UNKNOWN không thành Claim.
- [ ] Solver timeout/protocol error không bị decode thành UNSAT; không fabricate proof.
- [ ] Hint không submit/reveal; source clue IDs đều đã public tại KB version ghi trong hint.
- [ ] Trace proposal không được ghi như accepted history; PUBLIC_KB/VERIFIED_SUBSET được gắn đúng, không tự nhận minimum support.
- [ ] Cache gắn session/version/mapping; current request token được giữ đúng, stats không cộng lại cache hits.
- [ ] Public uniqueness chỉ đếm primary assignment, không phụ thuộc hidden key/full clues; UNAVAILABLE minh bạch khi chưa hỗ trợ.
- [ ] Tests: forced/unknown/inconsistent, empty unresolved, shuffled names/mapping, invalid context, stale cache, solver errors.
- [ ] Test thật với Encoder/DPLL sau bàn giao; reference solver không được dùng để đánh dấu mục này đạt.

## Phước — Presentation

- [ ] Bốn screen và đủ 12 component theo UI spec, tất cả Controller access qua MainWindow/ViewPort.
- [ ] Không import Agent/Encoder/DPLL implementation; không đọc raw puzzle, private solution hoặc preview payload.
- [ ] LevelSelection render đúng 15 summaries, chỉ public metadata whitelist.
- [ ] Card hidden không có clue/verdict; revealed có Claim đúng; selection/highlight/focus là overlays độc lập.
- [ ] Nhận immutable public DTO; không sửa field bên trong hoặc dùng DTO làm nguồn authoritative game state.
- [ ] Emit signal đúng tên/kiểu, một lần mỗi action; update programmatic không phát vòng lặp.
- [ ] Verdict buttons chỉ tạo CRIMINAL/INNOCENT; disabled theo GameState nhưng Controller vẫn validate input.
- [ ] Clue selection chỉ emit ID; visual helper chỉ tô cell IDs đã nhận, không resolve region.
- [ ] Reveal chỉ khi Controller yêu cầu với token hợp lệ; animation completion một lần, cancel không completion.
- [ ] Reduced motion queued completion; resize khi animation không nhân đôi event; initial reveal render không flip.
- [ ] MainWindow set_board resync board/clues/progress nhất quán, bỏ hint stale và giữ trace hợp lệ.
- [ ] Trace accepted và hint tách riêng; Results chỉ từ ResultsView, None stats hiển thị “—”.
- [ ] Layout QA 3×3/4×4/5×5, minimum window, long text/tiếng Việt, keyboard, contrast và HiDPI.
- [ ] pytest-qt dùng public mocks, waitSignal cho animation; không dùng sleep cố định làm điều kiện pass.
- [ ] Desktop smoke test ngoài offscreen; không tuyên bố integration đạt chỉ từ mock UI.

## Hiệp — Controller, worker và composition root

- [ ] Sở hữu Controller/worker/projection/catalog/main, không thao tác internal widgets.
- [ ] Một Engine authoritative; Controller chỉ quản lý workflow/session/selection/accepted history.
- [ ] Projection lấy một public snapshot, `cid in proved_verdicts`; không đọc hidden data để quyết định UI.
- [ ] Catalog whitelist 15 ID, không cho path tùy ý hoặc gửi answer-derived metadata lên GUI.
- [ ] Resolve FACT/SAME/DIFFERENT/counting đúng schema, zero-based ROW/COLUMN, NEIGHBORS tám hướng bỏ center.
- [ ] Manual claim được validate trước analysis; proof bridge từ result đúng cell/version, không từ claim.
- [ ] NOT_PROVABLE/CONTRADICTED/ALREADY_SOLVED không animation hoặc append clue; STALE_PROOF resync.
- [ ] INCONSISTENT, solver failure, GameEngineIntegrityError → ERROR/safe message, stop auto.
- [ ] Chỉ một worker job; Qt main thread không chạy solver blocking, không mutate shared mapping đồng thời.
- [ ] Kiểm tra token trước commit; duplicate/stale worker completion và stale animation completion bị loại.
- [ ] Auto mỗi lần chỉ chứng minh/commit một card; đợi animation barrier rồi chụp KB mới cho bước tiếp.
- [ ] ACCEPTED commit đúng một lần; animation cancel giữ committed truth, accepted history không mất/nhân đôi.
- [ ] Load/Restart/Back/Exit/Level Selection khi busy invalidate pending job, auto tắt, cancel effect, xử lý navigation an toàn.
- [ ] Không force-terminate thread; queue tối đa navigation mới nhất, Exit ưu tiên, không block event loop khi đợi job cũ.
- [ ] Failed Load giữ Engine cũ và restore stable state; initial Load lỗi → NO_PUZZLE.
- [ ] Restart/Load thành công đổi session, reset history/hint/selection; core version không tái sử dụng.
- [ ] Animation timeout/error → ERROR + resync, không Auto bước tiếp; initial/completed puzzle xử lý được.
- [ ] Chỉ SOLVED sau final animation/resync; Next Puzzle lấy thứ tự catalog, không suy từ filename tùy ý.
- [ ] Tests dùng fake Agent/View cho mọi transition; binding real GUI/Agent được kiểm chứng riêng.

## Full-system integration — cả ba, Hiệp điều phối

| Scenario | Kết quả bắt buộc | Trạng thái nghiệm thu |
|---|---|---|
| Load cả 15 map | Đúng N², initial reveal/clue công khai, không thêm sample | [ ] |
| Manual forced đúng | ACCEPTED, KB +1, một flip, một clue, một accepted step | [ ] |
| Manual UNKNOWN, thử cả hai claim | NOT_PROVABLE, KB/UI logical data không đổi | [ ] |
| Manual claim trái forced | CONTRADICTED, không flip hoặc thêm clue | [ ] |
| Base KB UNSAT | ERROR/INCONSISTENT, không giả STUCK | [ ] |
| Proof cũ / sai target / auxiliary ID | Reject, không commit | [ ] |
| Hint ở forced và stuck | KB không đổi; hint công khai; chỉ full scan mới STUCK | [ ] |
| Auto trên 15 map | Từng bước no-guess với DPLL/Encoder thật; Results sau flip cuối | [ ] |
| Load/Restart trong solver đang chạy | Result cũ không commit, session mới hợp lệ, UI responsive | [ ] |
| Load/Restart giữa animation | Commit cũ không rollback giả; callback cũ không mở card mới | [ ] |
| Failed Load khi đang Auto/Animating | Game cũ resync đúng, auto tắt, history/count nhất quán | [ ] |
| Callback trùng / thiếu / trễ | Một completion có hiệu lực; timeout không khiến Auto chạy tiếp | [ ] |
| Double click verdict/hint/auto | Không hai job cùng hiệu lực hoặc hai lần submit | [ ] |
| Menu/Level Selection/Exit khi busy | Cancel an toàn, không thread leak hoặc widget access sau destroy | [ ] |
| Highlight cả sáu template/bốn vùng | Đúng IDs public, không đổi KB; extension chưa hỗ trợ báo rõ | [ ] |
| Public-data audit | Không key/unrevealed clue/model trong DTO, tooltip, hints, notifications, trace UI | [ ] |
| Uniqueness diagnostic | Phân biệt public/full scope, primary-only; không dùng làm reveal shortcut | [ ] |
| Resize/HiDPI/reduced motion | Chữ đọc được, không overlap, token/event không nhân đôi | [ ] |
| Reference vs team solver | Kết quả/metrics gắn nguồn đúng; tests skip không tính pass | [ ] |

## Quy trình ghi nhận kết quả

Chạy regression hiện có từ repo root: `.venv/bin/python -m pytest -q`.
Sau khi GUI dependencies đã chốt, thêm test GUI bằng `PYTEST_QT_API=pyside6`; offscreen chỉ dùng khi platform hỗ trợ.
Khi có lỗi, ghi commit, môi trường, puzzle ID, thao tác tái hiện, expected/actual và test liên quan;
không dán hidden solution vào log dành cho người chơi.
Chỉ tick mục khi đã có test hoặc kiểm chứng thực tế; chưa triển khai không có nghĩa là failed test.

## Audit gói tài liệu V1

- [x] Đủ năm Markdown, không thêm implementation hoặc thay puzzle/source/dependencies.
- [x] Đánh dấu CONFIRMED/PROPOSED/BLOCKED, ownership cũ/mới được giải thích.
- [x] Có architecture/state Mermaid, wireframes, component inventory, API/DTO/error/token contract.
- [x] Baseline cho phép mock GUI, fake Controller dependencies, Agent public tests độc lập.
- [ ] Nhóm duyệt V1 và thực hiện các gate triển khai phía trên.

Kết quả kiểm tra tài liệu và regression của lần soạn được ghi trong mục “Kiểm tra bản bàn giao” ở Shared Baseline.
