# Stage 2 — API Contract V1

Ngày audit: **18/11/2026**. Source được kiểm tra: commit `011982e` tại checkout local.
Tài liệu này là nguồn chuẩn về tên, kiểu dữ liệu và quy tắc giao tiếp Stage 2.

- **CONFIRMED**: interface có thật trong source hoặc yêu cầu phạm vi được người giao việc xác nhận.
- **PROPOSED**: thiết kế V1 để ba thành viên review; chưa phải sự chấp thuận của cả nhóm.
- **BLOCKED**: chưa thể tích hợp/kiểm chứng do thiếu implementation hoặc quyết định phụ thuộc.

Toàn bộ DTO, Protocol, signal và API Stage 2 bên dưới là **PROPOSED**, trừ phần A.
Chưa tạo `src/shared/` hoặc class Python mới. Các khối khai báo là đặc tả, không phải module import được.
Sau khi duyệt, Hiệp là người materialize hợp đồng chung, Tài và Phước cùng review; không tự sao chép DTO vào ba package.

## A. Interface Stage 1 có thật — CONFIRMED

| Import / signature | Ý nghĩa và giới hạn |
|---|---|
| `src.core.game_engine.GameEngine(puzzle_json_path: str \| Path, loader: Optional[PuzzleLoader] = None)` | Sở hữu puzzle đầy đủ; chỉ Controller được giữ reference |
| `engine.load_puzzle(puzzle_json_path: str \| Path) -> None` | Validate trước rồi thay trạng thái; lỗi giữ game cũ |
| `engine.restart() -> None` | Khôi phục initial reveals; version mới lớn hơn version cũ |
| `engine.get_public_snapshot() -> PublicKBSnapshot` | Snapshot bất biến, chỉ revealed clues và proved verdicts |
| `engine.characters -> tuple[Character, ...]` | Metadata công khai, tọa độ zero-based |
| `engine.grid_size -> int`, `engine.puzzle_id -> str` | Kích thước và ID hiện tại |
| `engine.var_map -> VariableMap` | Primary đã frozen; vùng auxiliary vẫn có thể cấp phát |
| `engine.public_kb_version -> int` | Version KB hiện tại |
| `engine.get_unsolved_characters() -> list[str]` | Thứ tự row-major |
| `engine.submit_verdict(char_id: str, claimed_status: bool, entailment: EntailmentResult) -> tuple[VerdictResponse, Optional[dict[str, Any]]]` | `True` là Criminal, `False` là Innocent; chỉ ACCEPTED trả clue mới |
| `engine.is_solved() -> bool` | Tất cả nhân vật đã có proved verdict |
| `engine.get_clue_for_character(char_id: str) -> Optional[dict[str, Any]]` | Chỉ trả clue khi chủ thẻ đã revealed |
| `engine.get_public_state() -> dict[str, Any]` | Public dict đã có, nhưng chưa có token/lifecycle của Stage 2 |
| `snapshot.get_unit_clauses_for_verdicts() -> CNFFormula` | Trả bản sao unit clauses dạng list |
| `VariableMap.get_var(char_id: str) -> int` | Tra ID thực tế; không suy SAT ID từ vị trí card |

Canonical imports: `src.core.variable_map.VariableMap`, `src.core.cnf_types.CNFFormula`,
`src.core.clue.Clue`, `src.core.character.Character`, `src.core.public_kb.PublicKBSnapshot`,
`src.core.entailment_result.EntailmentStatus` và `EntailmentResult`.
Các re-export trong `src/encoder/variable_map.py`, `src/solvers/cnf_formula.py` vẫn hợp lệ.

`PublicKBSnapshot` có `version: int`, `revealed_clues: tuple[Clue, ...]`,
`proved_verdicts: Mapping[str, bool]`, `unit_clauses: tuple[tuple[int, ...], ...]`.
`Character` có `id`, `name`, `profession: str`, `row`, `col: int`.
`Clue` có `clue_id`, `owner_id`, `clue_type: str`, `parameters: Mapping[str, Any]`;
JSON dùng tên `type`, không phải `clue_type`. Dùng `Clue.to_dict()` để chuyển đổi.

Entailment hiện có tại `src/agent/entailment.py`:

```python
class SATSolver(Protocol):
    def solve(self, clauses: CNFFormula) -> bool: ...

class EntailmentChecker:
    def __init__(self, solver: SATSolver, *, variable_map: VariableMap | None = None): ...
    def classify(self, clauses: Sequence[Sequence[int]], variable: int) -> ClassificationResult: ...
    def classify_all(self, clauses: Sequence[Sequence[int]], unresolved: Mapping[str, int]) -> BatchResult: ...
    def first_forced(self, clauses: Sequence[Sequence[int]], unresolved: Mapping[str, int]) -> tuple[str, ClassificationResult] | None: ...

class ClassificationResult:
    verdict: EntailmentStatus
    queries: tuple[SATQuery, ...]
    def to_engine_result(self, character_id: str, kb_version: int) -> EntailmentResult: ...
```

`SATQuery` gồm `assumption: int | None`, `satisfiable: bool`, `sequence: int`.
`BatchResult` gồm `results: Mapping[str, ClassificationResult]`, `queries: tuple[SATQuery, ...]`;
`sat_calls` đếm query thực tế, không đếm lặp base query.
`classify` gọi base, giả định âm, giả định dương; base UNSAT dừng sau một call.
`classify_all` gọi base một lần rồi hai giả định cho mỗi unresolved; ngay cả tập unresolved rỗng vẫn kiểm tra base.
`first_forced` trả `None` cho cả UNKNOWN lẫn INCONSISTENT, nên Agent không được dùng riêng `None` để kết luận STUCK.

`EntailmentResult` có `character_id`, `status`, `kb_version`, `kb_satisfiable`,
`criminal_assumption_satisfiable`, `innocent_assumption_satisfiable`.
Hai field giả định là `bool | None`; chỉ `None` khi base UNSAT.
Factory `from_sat_results(character_id, kb_version, kb_satisfiable, criminal_assumption_satisfiable=None, innocent_assumption_satisfiable=None)` đã có.
Không tạo enum verdict khác; `Verdict` trong entailment hiện là alias của `EntailmentStatus`.

`SolverProtocolError` báo solver không trả đúng bool hoặc evidence mâu thuẫn.
`SolverAdapter(solve, decode)` đã có cho API solver khác; timeout/error không được decode thành `False`.
DPLL và Encoder thật đang rỗng. Tên `DPLLSolver().solve(CNF) -> bool` và
`CNFEncoder().encode(clue, variable_map) -> CNFFormula` trong tests là **PROPOSED/BLOCKED**, chưa phải API đã triển khai.

## B. Quy ước chung cho hợp đồng mới — PROPOSED

1. DTO dự kiến là frozen dataclass, `slots=True`; collection qua tầng là tuple hoặc mapping sao chép và khóa sâu. `frozen=True` không tự khóa list/dict lồng nhau.
2. Field liệt kê đều bắt buộc khi xây DTO; `| None` có nghĩa nullable, không có nghĩa bỏ qua field. Không dùng `Any` hay dict puzzle tùy ý cho UI.
3. Cell ID và clue ID phải tồn tại trong public context. Chuỗi không rỗng, số đếm/version không âm; bool không được dùng thay int.
4. `Claim` là type alias `Literal[EntailmentStatus.CRIMINAL, EntailmentStatus.INNOCENT]`, tái sử dụng enum Core. Kiểm tra runtime ở boundary; UNKNOWN/INCONSISTENT không được submit.
5. `GameState` dự kiến: `NO_PUZZLE`, `READY`, `PROCESSING`, `ANIMATING`, `SOLVED`, `STUCK`, `ERROR`.
6. `Screen` dự kiến: `MAIN_MENU`, `LEVEL_SELECTION`, `GAMEPLAY`, `RESULTS`. Screen khác với GameState; How to Play là dialog, không thêm màn thứ năm.
7. `CardVisibility`: `HIDDEN`, `REVEALED`. `selected` và `highlighted` là cờ presentation độc lập; có thể đồng thời true với HIDDEN hoặc REVEALED.
8. DTO gửi GUI không chứa Engine, Puzzle, VariableMap, CNF, assignment SAT, đường dẫn file puzzle, `hidden_solution`, hoặc clue chưa reveal.

`grid_size` chỉ nhận 3, 4, 5; tọa độ thuộc `[0, grid_size)`; các thời lượng khi có phải hữu hạn và không âm.
Session ID là chuỗi mới không tái sử dụng trong vòng đời ứng dụng; request ID không tái sử dụng trong session,
kể cả sau request lỗi/cancel. Tất cả cell IDs trong clue/hint/trace phải thuộc board của session tương ứng.

### B1. Token và context nội bộ

| Type | Fields và invariant | Producer → consumer |
|---|---|---|
| `RequestToken` | `session_id: str`, `request_id: int`, `kb_version: int`; session mới mỗi Load/Restart thành công, request ID tăng trong session | Controller → worker/Agent; chỉ animation token cần tới GUI |
| `AnalysisContext` | `token: RequestToken`, `snapshot: PublicKBSnapshot`, `characters: tuple[Character, ...]`, `grid_size: int`, `variable_map: VariableMap`; `token.kb_version == snapshot.version`; metadata và mapping cùng puzzle | Controller → Agent, không tới GUI |
| `ForcedVerdict` | `token: RequestToken`, `proof: EntailmentResult`, `step: DeductionStepView`; proof.status là Claim, proof version bằng token version, cùng target với step | Agent → Controller |
| `AnimationToken` | `session_id: str`, `request_id: int`, `kb_version: int`, `cell_id: str`; version là **sau** commit ACCEPTED | Controller → GUI → Controller |

`AnalysisContext` không phải nguồn trạng thái thứ hai: là ảnh chụp read-only của Engine.
`VariableMap` chỉ frozen miền primary, nên không được giả định thread-safe.
Chỉ một job Agent/Encoder chạy tại một thời điểm; không mutate/encode cùng mapping từ hai thread.
Mỗi job có envelope `(RequestToken, result hoặc error)` do worker của Hiệp quản lý.
Controller loại result nếu token không còn là request đang chờ, session khác hoặc KB version không còn khớp.

### B2. DTO công khai cho GUI

| DTO | Fields | Invariant / nguồn |
|---|---|---|
| `PublicCharacterView` | `cell_id: str`, `name: str`, `profession: str`, `row: int`, `col: int`, `visibility: CardVisibility`, `verdict: Claim | None` | Metadata từ `engine.characters`; HIDDEN iff verdict is None; verdict chỉ lấy từ snapshot.proved_verdicts |
| `PublicClueView` | `clue_id: str`, `owner_id: str`, `clue_type: str`, `text: str`, `referenced_cells: tuple[str, ...]` | Chỉ chuyển từ snapshot.revealed_clues; không truyền raw parameters sang GUI; text plain text |
| `PublicBoardSnapshot` | `session_id: str`, `puzzle_id: str`, `grid_size: int`, `kb_version: int`, `characters: tuple[PublicCharacterView, ...]`, `clues: tuple[PublicClueView, ...]` | 9/16/25 card theo row-major, ID không trùng; mỗi revealed card có một public clue, hidden card không có clue |
| `DeductionStepView` | `session_id: str`, `request_id: int`, `kb_version: int`, `cell_id: str`, `verdict: Claim`, `explanation: str`, `source_clue_ids: tuple[str, ...]`, `support_kind: Literal["PUBLIC_KB", "VERIFIED_SUBSET"]`, `sat_calls: int | None`, `elapsed_ms: float | None` | Version **trước** reveal; clue IDs thuộc KB của version đó; đo đếm không có thì None |
| `HintView` | `session_id: str`, `kb_version: int`, `outcome: Literal["FORCED", "NO_FORCED"]`, `cell_id: str | None`, `verdict: Claim | None`, `text: str`, `source_clue_ids: tuple[str, ...]` | FORCED có target/verdict; NO_FORCED có hai field None và clue IDs rỗng; không tự reveal |
| `ActionResult` | `code: ActionCode`, `message: str`, `session_id: str | None`, `kb_version: int | None`, `cell_id: str | None` | Chỉ safe message; session/version None khi chưa có game. Không kèm raw exception hoặc secret |
| `LevelSummary` | `puzzle_id: str`, `title: str`, `grid_size: int`, `difficulty_label: str | None` | Whitelist từ manifest: ID, size, nhãn heuristic; title có thể sinh từ ID. Không gửi criminal_count, solution, trace, support stats |
| `ResultsView` | `session_id: str`, `puzzle_id: str`, `revealed: int`, `total: int`, `accepted_steps: int`, `hint_requests: int`, `elapsed_ms: float | None`, `sat_calls: int | None`, `next_puzzle_id: str | None` | Chỉ khi SOLVED; revealed == total; steps không gồm initial reveals; next theo thứ tự manifest |

Producer của Character/Clue/Board/Level/Results/ActionResult là Controller (Hiệp).
Agent (Tài) tạo Hint/DeductionStep; Controller kiểm tra token, public scope và chuyển tiếp.
Phước chỉ đọc DTO và có thể tự tạo **mock công khai tổng hợp** trong tests GUI.

`ActionCode` đề xuất dùng enum riêng cho kết quả UI:
`ACCEPTED`, `NOT_PROVABLE`, `CONTRADICTED`, `INCONSISTENT`, `ALREADY_SOLVED`, `STALE_PROOF`,
`INVALID_REQUEST`, `BUSY`, `LOAD_FAILED`, `CANCELLED`, `SOLVER_FAILED`, `INTERNAL_ERROR`.
Sáu giá trị đầu ánh xạ 1–1 từ `VerdictResponse`; enum UI không thay enum Core.

Trace giải thích bằng toàn bộ public KB được gắn `PUBLIC_KB`; không gọi là minimum support.
`VERIFIED_SUBSET` chỉ dùng khi Agent thực sự kiểm chứng tập con; cũng không đồng nghĩa minimum cardinality.
`source_clue_ids` không thay thế các proved unit facts: explanation phải nói rõ luôn dùng các verdict đã biết.
Không lấy trace dựng sẵn từ `tools/preview_puzzles.html` hoặc báo cáo authoring làm suy luận runtime.

Metrics đề xuất: Results elapsed_ms tính bằng monotonic clock từ Load/Restart thành công đến hoàn tất game,
gồm thời gian người chơi và animation, khác với thời gian solver. Hint requests đếm request hợp lệ đã được nhận,
không đếm nút bấm bị BUSY. Results sat_calls là tổng calls thực tế của các job còn hiệu lực trong session
(gồm manual/hint/auto, không gồm diagnostic uniqueness và job bị hủy); nếu chưa instrument đầy đủ thì None.
Không cộng `ClassificationResult.sat_calls` của mọi card để tính batch vì sẽ lặp base query.
Step sat_calls/elapsed_ms mô tả analysis tạo step đó, không phải giá trị cộng dồn; có thể dùng None khi không quy được chi phí chính xác.

### B3. Chuyển Core → public view

- Lấy **một** snapshot làm nguồn cho một lần projection; không ghép clue của version mới với verdict của version cũ.
- Kiểm tra `cid in snapshot.proved_verdicts`, không kiểm tra truthiness của value: `False` là Innocent đã chứng minh.
- Metadata lấy qua public properties; không gửi `engine._puzzle`, raw JSON hay `Puzzle` cho GUI/Agent.
- `PublicClueView.text` do `src/controller/public_projection.py` format từ sáu template. Escape/hiển thị plain text, không thực thi markup trong clue.
- FACT tham chiếu `target`; SAME/DIFFERENT tham chiếu `target1`, `target2`.
- Counting clue: ROW/COLUMN dùng `index` zero-based; NEIGHBORS gồm tối đa tám ô, không gồm center; EXPLICIT dùng `cells`. Trả tuple row-major, bỏ trùng.
- Controller thực hiện region projection trên metadata công khai theo schema. Không gọi private `_resolve_region_ids` của validator, không đẩy việc hiểu region sang GUI.
- Extension clue chưa được chốt schema/resolver thì báo lỗi hỗ trợ, không giả vờ highlight đúng.
- UI là cache để render; chỉ Engine quyết định logical reveal. Controller giữ duy nhất workflow state, selection, session, pending request và lịch sử accepted trace.

## C. GUI → Controller: event contract — PROPOSED

Facade duy nhất là `MainWindow`. Signal khai báo tại class level bằng PySide6 `Signal`;
type DTO/enum/tuple dùng `Signal(object)` và validate ở slot nhận. Child widget forward lên facade một lần.
Slot Controller cùng tên event, mọi slot trả `None`; signal không có giá trị trả về.

| Event / signature | PySide6 signal | Điều kiện và xử lý |
|---|---|---|
| `play_requested()` | `Signal()` | Main Menu → Level Selection, không tạo Engine |
| `how_to_play_requested()` | `Signal()` | Hiển thị hướng dẫn; không đổi KB |
| `exit_requested()` | `Signal()` | Controller ngừng auto, đóng job an toàn rồi gọi view.close() |
| `card_selected(cell_id: str)` | `Signal(str)` | Chỉ card thuộc board; Controller cập nhật selection và `set_selection` |
| `verdict_requested(cell_id: str, verdict: Claim)` | `Signal(str, object)` | READY, card hidden; STUCK vẫn có thể submit để nhận NOT_PROVABLE; còn lại BUSY/INVALID_REQUEST |
| `clue_selected(clue_id: str)` | `Signal(str)` | Clue đang public; lỗi ID không thay highlight |
| `load_requested(puzzle_id: str)` | `Signal(str)` | Chọn từ whitelist catalog; không nhận path tùy ý |
| `restart_requested()` | `Signal()` | Có puzzle; hủy logical job/auto trước khi restart |
| `hint_requested()` | `Signal()` | READY/STUCK; một request mỗi lần |
| `auto_solve_requested()` | `Signal()` | READY/STUCK; chạy từng bước với animation barrier |
| `back_requested()` | `Signal()` | Gameplay/Results/Level Selection → Main Menu; hủy pending job/animation, bỏ active session |
| `animation_finished(cell_id: str, token: AnimationToken)` | `Signal(str, object)` | Chỉ nhận đúng animation đang chờ; duplicate/old token bị bỏ qua |

**Thay đổi có chủ ý so với tên gợi ý:** thêm token vào `animation_finished` để không nhận nhầm completion của bàn trước.
UI không tự tạo token. Nút Next Puzzle ở Results phát `load_requested(results.next_puzzle_id)` khi khác None.
Nút Load ở Gameplay gọi `show_level_selection(catalog)` qua Controller; bổ sung event
`level_selection_requested()` / `Signal()` để mở màn chọn mà chưa load. Event này hủy auto/pending work,
đồng bộ card đang animation về committed snapshot, giữ Engine; không có thao tác Resume trong V1.

Card selection và clue selection chỉ cho phép khi READY/STUCK/SOLVED; khi PROCESSING/ANIMATING bỏ qua event nhập cũ.
Load/Restart/Back/Exit vẫn có thể dùng lúc busy theo cancellation policy, thay vì đợi animation xong mới cho bấm.
Controller cũng kiểm tra Screen hiện hành; event của Gameplay không được xử lý trên Main Menu/Level Selection/Results.
Các UI intent được chuyển đồng bộ trong main thread; chỉ worker replies và animation completion dùng queued delivery.

## D. Controller → GUI: ViewPort — PROPOSED

MainWindow implement các public methods dưới đây; Hiệp chỉ gọi facade, không tìm widget con hoặc gọi paint trực tiếp.
Tất cả trả `None`, chạy ở Qt main thread; update render không được tự phát ngược request tương ứng.

```python
class ViewPort(Protocol):
    def show_main_menu(self) -> None: ...
    def show_how_to_play(self) -> None: ...
    def show_level_selection(self, levels: tuple[LevelSummary, ...]) -> None: ...
    def show_gameplay(self, snapshot: PublicBoardSnapshot) -> None: ...
    def set_board(self, snapshot: PublicBoardSnapshot) -> None: ...
    def set_clues(self, clues: tuple[PublicClueView, ...]) -> None: ...
    def set_selection(self, cell_id: str | None) -> None: ...
    def append_deduction_step(self, step: DeductionStepView) -> None: ...
    def highlight_cells(self, cell_ids: tuple[str, ...]) -> None: ...
    def clear_highlights(self) -> None: ...
    def reveal_card(self, cell_id: str, public_data: PublicCharacterView, token: AnimationToken) -> None: ...
    def cancel_animations(self) -> None: ...
    def show_notification(self, result: ActionResult) -> None: ...
    def show_hint(self, hint: HintView) -> None: ...
    def set_progress(self, revealed: int, total: int) -> None: ...
    def set_busy(self, state: GameState) -> None: ...
    def show_results(self, results: ResultsView) -> None: ...
    def close(self) -> None: ...
```

| Methods | Preconditions, side effects, lỗi |
|---|---|
| `show_main_menu`, `show_how_to_play`, `show_level_selection` | Chỉ đổi screen/dialog; catalog immutable; không đọc puzzle từ disk |
| `show_gameplay` | Load/Restart hoặc dựng lại screen; hủy animation cũ, xóa selection/highlight/hint/trace, render snapshot và clues/progress ngay, không flip initial cards |
| `set_board` | Cùng session hiện hành, không lùi KB version; render committed snapshot không animation, đồng bộ board+clues+progress; giữ trace và selection còn hợp lệ |
| `set_clues` | Chỉ danh sách từ cùng snapshot đang render; full replace, không append duplicate |
| `set_selection`, `highlight_cells`, `clear_highlights` | Cell phải thuộc board; có thể highlight hidden card nhưng không thay verdict; selection và highlight độc lập |
| `append_deduction_step` | Chỉ sau ACCEPTED rồi animation completion hoặc explicit cancel/resync; idempotent theo `(session_id, request_id, cell_id)`; cho phép replay accepted ledger khi dựng lại screen |
| `reveal_card` | Card hidden, data là REVEALED cùng target, token hiện hành; bắt đầu đúng một animation; chưa render clue mới |
| `cancel_animations` | Dừng/cleanup animation, không phát completion thành công; Controller phải ngay lập tức resync snapshot hoặc đổi screen |
| `show_notification` | Safe text; không gây logical state transition |
| `show_hint` | Session/version khớp; render riêng với lịch sử accepted trace, không cập nhật board verdict |
| `set_progress` | `0 <= revealed <= total`, total bằng N²; chỉ public count |
| `set_busy` | Controller cung cấp state; disable actions theo transition table, không tự tính state từ số thẻ |
| `show_results` | Chỉ SOLVED sau animation cuối; render ResultsView, không đọc hidden key |
| `close` | Sau khi Controller xử lý shutdown; không terminate thread cưỡng bức |

DTO sai cấu trúc là lỗi lập trình (`TypeError`/`ValueError`); Controller bắt tại boundary, dừng auto và phát thông báo an toàn.
View không nuốt lỗi hoặc âm thầm sửa verdict. DTO/token stale bị bỏ qua và resync khi cần, không hiện lỗi cho từng callback cũ.
`set_board` đồng bộ toàn bộ public board, nên không gọi nó ngay trước `reveal_card` cho cùng card.
Resync cùng game dùng `set_board` để giữ trace; nếu cần `show_gameplay` để trở lại từ Level Selection sau Load lỗi,
Controller replay accepted ledger qua `append_deduction_step` và khôi phục selection hợp lệ.
Không gọi Agent lại chỉ để tái dựng lịch sử. Khi KB version tăng, `set_board` xóa hint cũ.

## E. Controller → Logic Agent — PROPOSED, runtime BLOCKED

Agent là pure Python. Constructor dự kiến nhận `encoder` đáp ứng EncoderPort và `solver` đáp ứng SATSolver;
không nhận GameEngine, QWidget, QObject, raw Puzzle hoặc path. Tài dùng EntailmentChecker hiện có.
EncoderPort dự kiến `encode(clue: Clue, variable_map: VariableMap) -> CNFFormula`; chỉ encode public clues
và thêm snapshot unit clauses. Phong cần xác nhận cách xử lý ROW/COLUMN/NEIGHBORS với metadata.
Nếu Encoder cần `characters/grid_size` lúc khởi tạo, đặt adapter của Tài tại `src/agent/bindings.py`;
không giả định interface này đã tồn tại hoặc sửa Encoder thay Phong.

```python
class LogicAgentPort(Protocol):
    def classify_unresolved(self, context: AnalysisContext) -> BatchResult: ...
    def get_next_forced_verdict(self, context: AnalysisContext) -> ForcedVerdict | None: ...
    def get_hint(self, context: AnalysisContext) -> HintView: ...
    def get_deduction_trace(self, context: AnalysisContext) -> tuple[DeductionStepView, ...]: ...
    def check_uniqueness(self, context: AnalysisContext) -> UniquenessResult: ...
```

| Method | Precondition / output | Side effects / caller / errors |
|---|---|---|
| `classify_unresolved` | Context hợp lệ; unresolved được suy từ metadata trừ proved IDs; trả BatchResult của checker theo row-major | Worker của Controller gọi; chỉ cache/metrics của Agent và auxiliary allocation của Encoder; không reveal. Base UNSAT được biểu diễn bởi query đầu và kết quả INCONSISTENT |
| `get_next_forced_verdict` | Kiểm tra consistency trước; lấy forced đầu row-major. `None` chỉ khi base SAT và không còn forced | Worker gọi cho Auto; base UNSAT raise `AgentInconsistentError`, không dùng None; Controller tự phân biệt solved với stuck bằng Engine |
| `get_hint` | FORCED gợi ý target, verdict và public explanation; NO_FORCED chỉ khi scan đầy đủ SAT và không forced | Worker gọi cho Hint; không submit Engine, không tăng accepted trace; base UNSAT raise `AgentInconsistentError` |
| `get_deduction_trace` | Trả **các đề xuất suy luận** thuộc context hiện tại, có thể rỗng; không mô phỏng clue tương lai | Worker gọi sau analysis nếu cần explanation; không phải lịch sử reveal. Controller mới sở hữu accepted history |
| `check_uniqueness` | Chỉ kiểm tra model của **public KB hiện tại**, projection trên tất cả primary variables | Worker gọi cho diagnostic độc lập, không nằm trong vòng Auto; không quyết định reveal. Chưa có implementation/model API được xác nhận |

`UniquenessResult` fields: `token: RequestToken`,
`status: Literal["UNIQUE", "MULTIPLE", "UNSAT", "UNAVAILABLE"]`, `sat_calls: int | None`, `reason: str | None`.
UNAVAILABLE dùng khi capability chưa có; không đồng nghĩa MULTIPLE hoặc UNSAT.
Đếm assignment của primary; auxiliary assignments khác nhau không tạo nghiệm game khác nhau.
Không đưa model lên GUI. Full-puzzle uniqueness với mọi clue là nhiệm vụ authoring riêng;
không đưa full clues vào AnalysisContext để phục vụ method này. Unique full puzzle không bảo đảm no-guess tuần tự.

Agent errors dự kiến: `AgentInconsistentError` (base KB UNSAT), `AgentUnavailableError` (thiếu dependency/capability),
`AgentExecutionError` (solver/protocol/encoding thất bại). Input sai: `TypeError`/`ValueError`.
Worker giữ exception chi tiết cho diagnostics nội bộ và chuyển safe `ActionResult` sang UI.
Không gửi thông báo có assignment/hidden clue; không coi timeout/cancel là SAT False.
Cache phải key theo session + KB version + mapping; kết quả trả về phải mang request token hiện tại.
Không reuse ForcedVerdict cũ chỉ vì cùng target. Đo sat_calls báo actual calls, cache hit không cộng lại.

## F. Gửi verdict và ánh xạ lỗi

Manual flow dùng `classify_unresolved(context)`, chọn result đúng target rồi gọi
`result.to_engine_result(cell_id, context.snapshot.version)`; không tạo proof từ lựa chọn người chơi.
Controller validate Claim trước, sau đó `claimed_status = (claim is EntailmentStatus.CRIMINAL)`.
Trước submit phải kiểm tra envelope token và engine version lần nữa.

| Kết quả / lỗi | ActionCode | Hành vi bắt buộc |
|---|---|---|
| ACCEPTED | ACCEPTED | Engine đã commit; giữ snapshot sau commit, chạy animation đúng một card |
| NOT_PROVABLE | NOT_PROVABLE | Không flip, không thêm clue/unit/accepted trace; quay idle trước request |
| CONTRADICTED | CONTRADICTED | Không flip; giải thích dựa trên entailment công khai |
| INCONSISTENT / AgentInconsistentError | INCONSISTENT | ERROR, stop auto; không reveal |
| STALE_PROOF | STALE_PROOF | Bỏ proof, stop auto, resync current snapshot; không retry vô hạn |
| ALREADY_SOLVED | ALREADY_SOLVED | Resync, không animation lặp; giữ trạng thái terminal/idle hợp lệ |
| Unknown ID / invalid Claim / TypeError / ValueError | INVALID_REQUEST | Không chạy solver nếu phát hiện ở input; không đổi KB |
| Request nghiệp vụ khi busy | BUSY | Không enqueue thêm verdict/hint/auto; navigation theo cancellation policy |
| PuzzleLoadError | LOAD_FAILED | Giữ Engine cũ; restore public view, auto tắt; nếu chưa có game → NO_PUZZLE |
| SolverProtocolError / AgentExecutionError / timeout | SOLVER_FAILED | ERROR, không đoán và không tạo proof giả |
| AgentUnavailableError | SOLVER_FAILED | ERROR với thông báo dependency chưa sẵn sàng; không fallback sang tools |
| GameEngineIntegrityError / unexpected exception | INTERNAL_ERROR | ERROR, giữ committed state gần nhất; thông báo chung, không gửi raw exception |
| Request bị thay thế bởi navigation | CANCELLED | Bỏ kết quả cũ; không cần popup cho từng callback |

## G. Thread, cancellation và animation handshake

**PROPOSED:** Hiệp sở hữu một worker serial cho Agent và Qt bridge; Engine mutation, state transition và mọi ViewPort call ở main thread.
Không chạy vòng DPLL đồng bộ dài trong GUI event handler. Agent không import Qt.
Implementation worker/QThread/process, deadline và cooperative cancellation cần nhóm duyệt;
baseline chỉ quy định một job có hiệu lực, UI event loop tiếp tục hoạt động và stale result không thể commit.

1. Controller đóng gói public snapshot + token trước khi dispatch; chuyển PROCESSING.
2. Khi worker trả, kiểm tra request còn hiệu lực, session và KB version. Chỉ sau đó submit Engine.
3. ACCEPTED tạo AnimationToken với version sau commit; chuyển ANIMATING và gọi reveal_card.
4. `animation_finished(cell_id, token)` phải khớp toàn bộ token đang chờ; xử lý đúng một lần.
5. Sau completion: `set_board(committed_snapshot)`, thêm accepted step, cập nhật progress, bỏ hint cũ;
   nếu solved → SOLVED + show_results; nếu auto → request mới với snapshot mới; còn lại READY.
6. Khi Load/Restart/Back/Exit/Level Selection tới lúc busy: tắt auto, vô hiệu hóa request đang chờ,
   cancel animation. Nếu Engine đã ACCEPTED thì commit không rollback; resync trước khi rời hoặc giữ game.
7. Worker cũ có thể vẫn tính. Không `terminate()` thread và không dùng lại mapping đó cho job mới
   trước khi worker cũ kết thúc. Navigation được ghi nhận ngay; tối đa một yêu cầu navigation mới nhất
   được giữ chờ, bỏ các yêu cầu trung gian. Exit ưu tiên cao nhất. Không block main thread bằng `wait()` dài.
8. Sau worker cũ kết thúc mới thực hiện Load/Restart cần dùng lại tài nguyên; thành công tạo session mới,
   reset trace/hint/selection và `show_gameplay`. Load thất bại giữ session cũ nhưng mọi request cũ đã invalid.
9. Cancel giữa animation sau ACCEPTED phải đưa accepted step vào ledger đúng một lần nếu giữ game cũ;
   Restart/Load thành công thì ledger mới rỗng. Không mất/nhân đôi count vì animation bị bỏ dở.

Nếu animation lỗi/không hoàn thành: watchdog do Hiệp sở hữu chuyển ERROR, cancel animation và resync
committed snapshot; không tự giải card tiếp theo. Reduced motion vẫn phát completion qua event queue,
không gọi đệ quy Auto trong cùng call stack. Watchdog timeout là cấu hình PROPOSED, không suy từ duration mà giả định chắc chắn đúng.

## H. Ví dụ tích hợp theo contract, chưa phải implementation

```text
Manual: READY tại KB=7
  verdict_requested("B1", CRIMINAL)
  Controller -> worker: classify_unresolved(context(token=S/12/7))
  worker -> Controller: (S/12/7, BatchResult)
  Controller kiểm tra token, chuyển ClassificationResult thành EntailmentResult
  engine.submit_verdict("B1", True, proof)
  ACCEPTED, KB=8 -> reveal_card("B1", public_card, AnimationToken(S,12,8,"B1"))
  animation_finished("B1", same_token)
  set_board(snapshot@8), append_deduction_step(step@7), READY hoặc SOLVED

Hint: get_hint(context@8) -> HintView(FORCED)
  show_hint(hint); engine version vẫn 8; không gọi submit_verdict

Restart trong lúc job S/13/8 đang chạy
  invalid request 13, auto=False; đợi worker hoàn tất mà không block event loop
  result S/13/8 bị bỏ; engine.restart(); tạo session T; show_gameplay(snapshot@new_version)
  completion animation của S bị bỏ, dù cell_id giống nhau
```

Phước test ViewPort với public DTO tự dựng; Hiệp test Controller với fake ViewPort/Agent;
Tài test Agent bằng public context và solver/encoder doubles trước khi dependency thật có sẵn.
Các doubles nằm trong tests, không được đưa vào đường chạy game để che dependency còn thiếu.
