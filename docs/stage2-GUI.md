# Tương tác chơi Griductive

Chạy `python main.py` hoặc `python -m src.gui.app` từ thư mục dự án.
Chạy `python -m src.gui.app --demo` để xem giao diện bằng dữ liệu mẫu.
Cài phụ thuộc bằng `python -m pip install -r requirements.txt -r requirements-dev.txt`.

## Các thao tác

- **Đổi hồ sơ** mở kho màn chơi từ `puzzles/manifest.json`. Chỉ sau khi engine
  nạp thành công mới thay ván hiện tại; lỗi nạp giữ lại ván trước.
- **Chơi lại** đưa ván về các ô mở ban đầu. Từ hai bước đã giải trở lên, cần
  xác nhận ngay trong thanh điều khiển. Có thể hủy hoặc nhấn Esc.
- Nhấp manh mối để tập trung vào các ô liên quan. Các ô khác giảm opacity;
  đối tượng chính và đối chiếu có viền khác sắc độ. Chip hiển thị tọa độ,
  hàng/cột nếu toàn vùng cùng hàng/cột. Nhấp lại, Esc hoặc vùng trống để bỏ.
- Tick hoặc nhấp đúp manh mối để đánh dấu đã dùng. Ghi chú tồn tại qua các
  bước suy luận; không loại manh mối khỏi KB và được xóa khi đổi/chơi lại.
- **Gợi ý** tìm bước bắt buộc tiếp theo, tô sáng chứng cứ, mở đúng một ô,
  tăng bộ đếm và giải thích kết luận. Nhật ký lưu chi tiết các bước.
- **Tự giải** dùng cùng quy trình chứng minh từng bước, nhịp khoảng 450 ms
  cộng thời gian SAT. **Tạm dừng** có hiệu lực cả khi đang chờ SAT hoặc lật
  thẻ. Bước đã được engine chấp nhận vẫn được giữ; kết quả đang chờ bị bỏ.
- **Chưa đủ dữ kiện** có nền amber: cả hai giả thiết còn hợp lệ. **Mâu thuẫn**
  có nền rose và rung nhẹ tại ô chọn sai. Nút **Soi điểm mâu thuẫn** dẫn tới
  tập chứng cứ đã kiểm chứng. Thông báo nằm trên bàn cờ, không đè lên ô.
  Chọn ô khác hoặc Esc để đóng.

## Ranh giới tích hợp

`src/gui/interaction_state.py` chứa trạng thái trình bày: `selected_clue_id`,
`highlighted_targets`, `active_hint`, `error_feedback`, `is_auto_solving`,
`solved_clues` và bộ đếm. Widgets chỉ nhận DTO công khai và phát tín hiệu.

`src/controller/gameplay_session.py` chuyển snapshot công khai thành DTO,
gọi nguyên bản `CNFEncoder`, `DPLLSolver`, `EntailmentChecker`. Mỗi lượt phân
tích có VariableMap riêng; không đọc đáp án ẩn. Tập chứng cứ được rút gọn bằng
SAT theo phép xóa từng nhóm manh mối/ô đã chứng minh: tập trả về là tối tiểu
theo bao hàm, không cam kết ít phần tử nhất. Chỉ `GameEngine.submit_verdict()`
chấp nhận proof tại đúng phiên bản KB mới được mở ô.

`src/controller/play_controller.py` nối các signal hiện có của MainWindow,
chạy SAT/nạp puzzle trên QThreadPool và tuần tự hóa thao tác bằng QTimer.
Generation loại kết quả cũ sau Pause/Restart/Load; KB version kiểm tra lần nữa
trước khi áp dụng. Token lật thẻ ngăn animation cũ ghi đè ván mới. Các thuật
toán trong `src/core`, `src/agent`, `src/encoder`, `src/solvers` được giữ nguyên.

Để ghép vào shell khác: tạo `MainWindow(demo_navigation=False)`, sau đó giữ
tham chiếu `PlayController(window)`. Không gắn cùng lúc controller demo hoặc
controller khác vào các signal chơi. `build_main_window()` vẫn mặc định demo
để giữ tương thích các preview/test widget hiện có.

## Kiểm tra

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest tests/gui/test_interaction_upgrade.py -q
python -m compileall -q src tests
```

Các ca tích hợp dùng solver thật, gồm 15 puzzle chính thức, hủy yêu cầu đang
chờ, Pause trong animation, phân biệt lỗi, kiểm tra ghi chú và reset state.
Trên Windows, backend `offscreen` có thể không có font hệ thống; để kiểm tra
ảnh/font thực tế hãy bỏ biến `QT_QPA_PLATFORM` và dùng backend Windows.
