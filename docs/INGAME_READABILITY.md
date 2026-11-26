# Bàn điều tra và hướng dẫn tân thủ

Giao diện giữ manh mối dưới mỗi thẻ và dấu nháp riêng của người chơi. Khung
`ClueReader` hiển thị nguyên văn manh mối công khai ở cỡ chữ 14 px, không phụ
thuộc mức thu nhỏ của bàn 3×3 / 4×4 / 5×5. Hover xem tạm; nhấp dải để ghim;
rời chuột trả về manh mối đã ghim hoặc luật toàn bàn đang công khai.

Nháp và Nhật ký nằm ở hai tab. Gợi ý hoặc bước suy luận mới mở tab Nhật ký;
đổi tab giữ nguyên ghi chú và dấu nháp. Restart / hồ sơ mới vẫn làm sạch nháp.

Nền bàn, viền và hiệu ứng trang trí dịu hơn. Ánh sáng theo chuột trên bàn giảm
bán kính từ 190 xuống 42 px; quầng sương toàn cửa sổ cũng còn khoảng 1/3 kích
thước cũ và giảm độ đậm. Khi vào ingame, sao/bụi toàn cửa sổ mờ hơn. Reduced
motion vẫn hoạt động theo cơ chế cũ.

Thanh tiêu đề chia ba cột, hai bên cân bằng để bảng tên GRIDUCTIVE SOLVER
nằm đúng giữa cửa sổ. Tên hồ sơ rút gọn bằng dấu … khi thiếu chỗ, giữ bản đầy
đủ trong tooltip; ở cửa sổ hẹp, bảng tên tự ẩn để chừa chỗ cho chữ và nút.

Tutorial dùng cùng khung đọc, nền, màu và dải manh mối như ingame; spotlight
cả dải nguồn lẫn bản đọc, rồi chuyển mũi tên đến ô / phán quyết. Kịch bản và
proof SAT giữ nguyên, phiên chính vẫn tách biệt.

Các điểm chỉnh sau này:

- `src/gui/styles/investigation.py`: bảng màu, kiểu khung đọc/tab, bán kính
  và độ đậm ánh sáng chuột.
- `src/gui/components/clue_reader.py`: bản đọc đầy đủ của một manh mối.
- `src/gui/screens/gameplay_screen.py`: bố cục và đồng bộ hover/ghim/tab.
- `src/gui/tutorial_dialog.py`: bố cục tutorial và tọa độ spotlight nguồn.

Kiểm tra: 45 test liên quan đạt trên Qt offscreen; 21 test giao diện mới và
tutorial đạt trên Qt Windows. Đã kiểm tra ảnh ở 960×640 và 1366×768, cùng các
test tọa độ tutorial từ 760×560 đến 1920×1080. Nhóm test UI cũ còn 15 lỗi có
sẵn trước sửa, chủ yếu tham chiếu CluePanel đã bị bỏ trong bản giao diện mới.
