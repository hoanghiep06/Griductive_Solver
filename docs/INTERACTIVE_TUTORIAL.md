# Interactive Tutorial — Griductive Solvers

## Kết quả khảo sát code

Ứng dụng là desktop Python/PySide6, khởi chạy bằng `python main.py` hoặc
`python -m src.gui.app`. `MainWindow` là facade chuyển các intent từ màn hình
đến controller. `ScreenRouter` quản lý các màn menu, giới thiệu, kho hồ sơ,
bàn chơi và kết quả; router không sở hữu trạng thái puzzle.

- `src/core`: `PuzzleLoader`/`PuzzleValidator` kiểm tra màn trước khi nạp;
  `GameEngine` giữ đáp án và manh mối chưa mở. `PublicKB`/snapshot chỉ cung cấp
  trạng thái đã chứng minh và manh mối công khai, có version chống proof cũ.
- `src/encoder`: 6 rule cơ bản và 2 rule mở rộng được mã hóa thành CNF;
  `semantic_eval` và evaluator trong validator kiểm tra nghĩa trực tiếp.
- `src/solvers` và `src/agent`: DPLL, truy vấn entailment, tìm bước ép buộc,
  tối thiểu hóa chứng cứ, trace và kiểm tra nghiệm duy nhất. Lật thẻ yêu cầu
  proof từ `SAT(KB)`, `SAT(KB ∧ C)`, `SAT(KB ∧ ¬C)`.
- `src/controller/play_controller.py`: chạy yêu cầu SAT ở worker, quản lý
  generation, auto-play, pending reveal và animation token. `GameplaySession`
  chuyển dữ liệu công khai thành DTO cho UI.
- `src/gui/controller.py`: adapter tương tác cũ; launcher hiện tại dùng
  `src/controller/play_controller.py`, nên tutorial được tích hợp ở facade mới.
- `src/gui/grid_view.py`: `QGraphicsView` chứa `CharacterCard`, fit/scale theo
  viewport. `CluePanel`, `ActionBar`, `DeductionPanel`, progress và motion
  coordinator chỉ trình bày dữ liệu công khai.

### Rule thực tế

| Rule | Ý nghĩa |
| --- | --- |
| `FACT` | Một người thuộc phe được khẳng định trực tiếp |
| `SAME` | Hai người cùng trạng thái |
| `DIFFERENT` | Hai người khác trạng thái |
| `EXACTLY` | Vùng có đúng k tội phạm |
| `AT_LEAST` | Vùng có ít nhất k tội phạm |
| `AT_MOST` | Vùng có nhiều nhất k tội phạm |
| `PARITY` | Số tội phạm trong nhóm chẵn hoặc lẻ |
| `COUNT_COMPARE` | So sánh số tội phạm hai nhóm: `<`, `<=`, `==`, `!=`, `>=`, `>` |

`ROW`, `COLUMN`, `NEIGHBORS`, `EXPLICIT` là dạng vùng, không phải rule độc lập.
`NEIGHBORS` tính cả đường chéo, loại tâm: 8 ô ở giữa, 5 ở cạnh, 3 ở góc.
Encoder còn nhận shorthand `NO`, nhưng loader/validator không nhận nó như
một type của puzzle. Tutorial dạy cùng ý nghĩa bằng `EXACTLY 0` hợp schema.
Manh mối luôn đúng, kể cả lời khai thuộc một thẻ tội phạm.

## Bố cục và chuỗi suy luận

Bàn cố định 4×4; A1 mở sẵn là tội phạm. Mỗi thẻ có đúng một manh mối.
Bàn này nằm ngoài `puzzles/manifest.json`, không thay đổi 15 hồ sơ chính thức.
Mỗi lượt dưới đây chỉ cần manh mối được nêu và các trạng thái đã chứng minh.

| Bước | Quan sát → phân tích → kết luận |
| --- | --- |
| 1 | Giới thiệu tọa độ, hai phe và mục tiêu 16 thẻ |
| 2 | Giới thiệu dải manh mối dưới thẻ, khung đọc đầy đủ và thao tác chọn ô → phán quyết |
| 3 | A1: FACT B1 tội phạm → thông tin trực tiếp → B1 tội phạm |
| 4 | B1: B1 SAME C1 → B1 tội phạm → C1 tội phạm |
| 5 | C1: hàng 1 EXACTLY 3 → A1/B1/C1 đã đủ 3 → D1 vô tội |
| 6 | D1: D1 DIFFERENT A2 → D1 vô tội → A2 tội phạm |
| 7 | A2: {B1,B2} AT_MOST 1 → B1 đã chiếm 1 → B2 vô tội |
| 8 | B2: {B2,C2} AT_LEAST 1 → B2 vô tội → C2 tội phạm |
| 9 | C2: {D1,B2,D2} PARITY odd → hai người đầu vô tội → D2 tội phạm |
| 10 | D2: count{A3,D1} == count{B1,B2} → vế phải 1, D1 vô tội → A3 tội phạm |
| 11 | A3: cột A EXACTLY 4 → 3 ô đầu tội phạm → A4 tội phạm |
| 12 | A4: NEIGHBORS B2 EXACTLY 8 → cả 8 ô phải tội phạm → mở B3 tội phạm |
| 13 | Cùng manh mối A4 → đã biết 7/8 → C3 tội phạm |
| 14 | C3: count{D3} == count{D1} → D1 có số lượng 0 → D3 vô tội |
| 15 | D3: hàng 4 AT_MOST 1 → A4 đã tội phạm → B4 vô tội |
| 16 | B4: {C4,D4} EXACTLY 0 → không ai là tội phạm → mở C4 vô tội |
| 17 | Cùng manh mối B4 → không có tội phạm → D4 vô tội |
| 18 | Đủ 16/16, chúc mừng và trở về giao diện trước đó |

Kịch bản dùng một ví dụ suy luận cho mỗi loại rule; không phải bài tập riêng
cho mọi biến thể toán tử so sánh hoặc cả hai parity. Lời dẫn giải thích các
biến thể đó. Toàn bộ lời dẫn tiếng Việt nằm trong `src/tutorial/data.py`.

## UX và tích hợp

Menu có nút **Hướng dẫn chơi · Tân thủ**, màn chơi có nút **? Tân thủ**.
Tutorial mở trong cửa sổ modal cùng kích thước cửa sổ game, dùng phiên
`GameEngine` mới. Giao diện tái sử dụng `GameBoard`, `ClueReader`, dải manh mối
dưới thẻ, portrait và hiệu ứng lật thẻ thật. Dải nguồn và bản đọc đầy đủ cùng
được spotlight. Chỉ hiển thị manh mối công khai đang được giải thích.

Overlay làm tối vùng ngoài spotlight, vẽ glow và mũi tên động. Các ô tham chiếu
của manh mối đều sáng; mũi tên chỉ vào ô cần chọn rồi chuyển đến phán quyết.
Hộp lời dẫn ở cạnh bàn, dưới manh mối và trên hai nút phán quyết, có vùng cuộn
để không mất nội dung khi chiều cao nhỏ.

- Hai bước đầu và bước cuối cho phép chạm nền tối, Enter/Space hoặc nút tiếp.
- Mỗi lượt bắt buộc chọn đúng ô rồi chọn phe. Có nút chọn ô hỗ trợ bàn phím;
  Tab đến hai nút phán quyết để tự xác nhận.
- Chọn sai phe giữ nguyên KB và hiển thị giải thích thử lại. Chọn ô khác
  hoặc bấm tiếp trước khi chứng minh không thay đổi trạng thái.
- Chuyển bước chỉ mở khóa sau khi engine chấp nhận **và** animation hoàn tất.
- **Bỏ qua**, Escape và nút đóng cửa sổ đều hủy animation/timer của tutorial.
  Chạy lại luôn khởi tạo bàn tập mới.
- Reduced motion giữ spotlight tĩnh và dùng completion queued của motion
  coordinator; không phụ thuộc thời gian animation để mở khóa bước.

Trước khi mở tutorial, `PlayController.stop()` hủy worker generation cũ,
dừng auto-play và commit phần hiển thị của giao dịch đã được chấp nhận nếu
đang lật thẻ. Engine/session chính, trace, hint/mistake counter, selection và
screen hiện tại được giữ lại. Auto-play ở trạng thái dừng sau khi thoát để
người chơi chủ động tiếp tục. Thời gian xem tutorial được loại khỏi đồng hồ
phiên chính.

Escape được xử lý theo cửa sổ nhận phím: event filter của màn chơi chính
không chặn Escape trong modal tutorial.

### Chia module

| File | Trách nhiệm |
| --- | --- |
| `src/tutorial/level.json` | Bàn tập cố định, schema 1.0, 16 nhân vật và 16 clue |
| `src/tutorial/data.py` | `TutorialStep`, mảng `TUTORIAL_STEPS`, nội dung và hành động yêu cầu |
| `src/tutorial/session.py` | Tiến độ và proof thật từ đúng clue đang dạy + verdict công khai |
| `src/controller/tutorial_controller.py` | Chọn ô, phán quyết, phản hồi, animation và chuyển bước |
| `src/gui/tutorial_dialog.py` | Layout và tính hình chữ nhật mục tiêu |
| `src/gui/components/tutorial_overlay.py` | Dim, glow, pointer, tooltip và điều phối hit test |
| `src/gui/assets/tutorial_portraits.py` | 16 ánh xạ portrait riêng, không đổi mapping 250 thẻ chính |

Tọa độ thẻ đi qua `card_rect → mapRectToScene → mapFromScene → viewport global
→ overlay local`; widget dùng `mapToGlobal/mapFromGlobal`. Không nhân tọa độ
với DPI hoặc ghi cứng kích thước ô. Resize/move/layout/scroll đều cập nhật;
vẽ và hit test dùng chung nguồn tọa độ. Bàn vẫn fit bằng cơ chế hiện có.

Để thêm lượt: sửa level theo schema, thêm `TutorialStep` có `clue_id` đã mở,
`target`, `verdict`, rồi chạy kiểm thử. Các bước giới thiệu dùng `focus` và
không cần target. Test kiểm tra suy luận của **chính manh mối đang dạy** để
không vô tình dựa vào một manh mối khác và che lỗi lời thoại.

## Kiểm tra

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q tests/test_tutorial.py tests/gui/test_tutorial.py
# Kiểm tra bằng Qt Windows thật (có mở cửa sổ trong lúc chạy):
$env:QT_QPA_PLATFORM='windows'
python -m pytest -q tests/gui/test_tutorial.py
```

Các test bao gồm đủ rule/vùng, đối chiếu semantic bằng mọi gán còn khả dụng
ở từng lượt, proof SAT, sai phe không đổi KB, full walkthrough bằng click,
đóng khi đang lật, replay, giữ phiên chính, Escape trong gameplay, sự kiện cảm ứng, giảm hiệu
ứng, giữ giao dịch chính đang lật, và tọa độ tại 760×560, 960×640, 1280×720,
1366×768, 1600×900, 1920×1080.

Baseline trước thay đổi: 537 passed, 3 failed trong
`tests/gui/test_interaction_upgrade.py`: `test_hint_reveals_only_forced_step_with_verified_source`,
`test_restart_inline_confirmation_and_counters`,
`test_auto_completes_and_pause_during_flip_keeps_accepted_progress`.
Các lỗi này liên quan kỳ vọng Hint mở thẻ và hành vi/timing interaction có sẵn;
không sửa hành vi Hint/auto-play ngoài phạm vi tính năng tutorial.

Kết quả kiểm tra tính năng: **17 passed** với cả Qt offscreen và Qt Windows.
Lần chạy toàn bộ suite sau tích hợp: **552 passed, 3 failed**, cùng 3 lỗi
baseline; hai test bổ sung sau đó (thoát/lật thẻ chính và cảm ứng) đều đạt
trong bộ kiểm thử tính năng. `compileall` và `git diff --check` cũng đạt.
