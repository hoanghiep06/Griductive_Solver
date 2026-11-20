# TV1 Core Foundation — Ghi Chú Phát Hành & Tích Hợp (Push Notes)

Code hiện tại hoàn thiện toàn bộ các yêu cầu tinh chỉnh kiến trúc và sửa lỗi kiểm thử cho phần Core Engine trước khi các thành viên TV2, TV3, TV4, TV5 tiến hành tích hợp.

## Các Thay Đổi & Nâng Cấp Chính

1. **Phân tích Tính Giải Được Tuần Tự (Sequential Solvability):**
   * Tích hợp hàm `PuzzleValidator.analyze_sequential_solvability()` để duyệt cạn chuỗi lật bài No-Guess cho các puzzle nhỏ.
   * Giới hạn mặc định `max_characters=9`. Các puzzle lớn hơn sẽ trả về trạng thái `TOO_LARGE` thay vì chạy duyệt cạn vô hạn.

2. **Cập nhật File Puzzle Mẫu `puzzles/sample_3x3.json`:**
   * Đảm bảo tính duy nhất nghiệm (1 model trên 512 trường hợp gán biến).
   * Đảm bảo giải được tuần tự từng bước mà không cần đoán từ lá bài `A1` ban đầu với chuỗi lật bài:
     $$\text{A1} \to \text{B1} \to \text{C1} \to \text{A2} \to \text{B2} \to \text{C2} \to \text{A3} \to \text{B3} \to \text{C3}$$

3. **Đồng bộ Thứ tự Tên Nhân vật theo Chuẩn Hàng (Row-Major):**
   * Các nhân vật trong `sample_3x3.json` được xếp thứ tự alphabet từ trái sang phải, từ trên xuống dưới: Abel (A1), Bea (B1), Clara (C1), Derek (A2), Eliza (B2), Franz (C2), Grant (A3), Hannah (B3), Ivy (C3).
   * Thứ tự ID biến mệnh đề trong `VariableMap` khớp hoàn toàn với vị trí trên bàn cờ: $A1=1, B1=2, C1=3, A2=4, B2=5, C2=6, A3=7, B3=8, C3=9$.

4. **Chốt An Toàn Nội Bộ (`GameEngineIntegrityError`):**
   * Ngay trước khi chấp nhận phán quyết (`ACCEPTED`), `GameEngine` tự động so sánh `forced_status` với đáp án ẩn `_hidden_solution`.
   * Nếu có sự mâu thuẫn, Engine sẽ quăng lỗi `GameEngineIntegrityError` để báo hiệu bug mã hóa CNF/DPLL nội bộ mà không làm rò rỉ đáp án ra bên ngoài.

5. **Giao Dịch Lật Bài Nguyên Tử (Atomic Reveal Transaction):**
   * Mỗi bước lật bài thành công (thêm phán quyết + manh mối mới) thông qua `PublicKB.record_reveal()` chỉ tăng `version` của KB đúng **1 lần**.

6. **Tăng Tính Đơn Điệu Của KB Version (Monotonic Versioning):**
   * Khi gọi `restart()` hoặc `load_puzzle()`, `version` của KB sẽ tiếp tục tăng lên dải giá trị cao hơn, đảm bảo các `EntailmentResult` cũ không bao giờ bị sử dụng lại.

7. **Chuẩn Hóa API Tri Thức Công Khai:**
   * `get_public_snapshot()` là phương thức duy nhất để lấy snapshot tri thức (đã xóa property `public_kb` dư thừa).
   * `get_revealed_clues()` trả về `tuple[Clue, ...]`, hoàn toàn đồng nhất về kiểu dữ liệu với snapshot.

---

## Nước Đi Đầu Tiên Được Ép Buộc Tranh Luận trong Puzzle Mẫu

Sau khi load `puzzles/sample_3x3.json`, lá bài `A1` được lật ban đầu là **Innocent**. Manh mối của `A1` ép buộc **`B1` phải là Criminal**.

> *Lưu ý:* Tuyệt đối không dùng ví dụ cũ gửi phán quyết cho `A2`. Puzzle mẫu đã cập nhật và `A2` hiện tại là Innocent.

---

## Đoạn Mã Tích Hợp Mẫu Chuẩn (Canonical Integration Snippet)

```python
from src.core.game_engine import GameEngine, VerdictResponse
from src.core.entailment_result import EntailmentResult

# 1. Khởi tạo GameEngine
engine = GameEngine("puzzles/sample_3x3.json")
snapshot = engine.get_public_snapshot()

# 2. TV5 tạo EntailmentResult dựa trên câu truy vấn SAT
result = EntailmentResult.from_sat_results(
    character_id="B1",
    kb_version=snapshot.version,
    kb_satisfiable=True,
    criminal_assumption_satisfiable=True,   # SAT(KB AND C_B1)
    innocent_assumption_satisfiable=False,  # UNSAT(KB AND NOT C_B1)
)

# 3. Gửi phán quyết vào GameEngine
response, revealed_clue = engine.submit_verdict(
    char_id="B1", 
    claimed_status=True, 
    entailment=result
)

assert response is VerdictResponse.ACCEPTED
print("Manh mối mới nhận được:", revealed_clue)
```

---

## Lệnh Kiểm Thử Toàn Bộ Mã Nguồn

Chạy các lệnh sau tại thư mục gốc `Lab02/`:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```