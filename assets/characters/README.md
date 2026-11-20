# GRIDUCTIVE — Bộ 46 chân dung nhân vật 2D

## Nội dung

- **46 ảnh PNG** trong `portraits/` (512×512, RGBA, vùng mép làm mềm để phù hợp nền giấy kem).
- **12 nghề nghiệp** theo dữ liệu của 15 màn chính thức.
- **250 ánh xạ** `(puzzle_id, cell_id)` → `portrait_path` trong `portrait_manifest.json` và `portrait_mapping_250.csv`.
- `preview_all_46.jpg`: bảng xem trước toàn bộ portrait.

## Cách tích hợp PySide6

1. Chép thư mục `portraits/` vào thư mục asset GUI, ví dụ `assets/characters/portraits/`.
2. Nạp `portrait_manifest.json` một lần, tạo lookup bằng `(puzzle_id, cell_id)`.
3. Khi có public character metadata, lấy `portrait_path` từ lookup, sử dụng `QPixmap` và cache theo file path.
4. Render trong **vùng trên** của `CharacterCard` (bên trong A02) theo `KeepAspectRatio`; không ghi thông tin lên ảnh tĩnh.
5. Tên, nghề, mã ô, CLUE, CRIMINAL/INNOCENT tiếp tục do Qt render theo public state. Portrait không chứa đáp án.
6. Hỗ trợ 3×3,4×4,5×5; ở 5×5 ưu tiên vùng mặt/đầu, ẩn bớt chi tiết trang trí nếu nhỏ.
7. Những màn mock tiếng Việt dùng fixture riêng; không ánh xạ nhầm `MOCK_*` sang puzzle chính thức.

## Giới hạn cần lưu ý

Bộ này sử dụng **46 biến thể nghề** để phủ 250 vị trí và đảm bảo **không lặp cùng một file portrait trong một màn**. Đây không phải 250 gương mặt riêng. Vì 25 tên được tái sử dụng nhưng nghề thay đổi giữa màn, một tên không nhất thiết giữ cùng gương mặt xuyên suốt 15 màn.

**Về chất lượng ảnh:** Một số chân dung xuất từ bố cục contact sheet thay vì ảnh gốc độc lập, nên chi tiết ở mức phù hợp thẻ UI nhỏ, **không nên xem là file 1024px có chi tiết gốc đầy đủ**. Bộ có cả nền trong suốt thực và lớp nền giấy sáng được feather để giảm viền cứng; trước khi đưa vào production hãy xem thực tế trên thẻ 5×5 và cân chỉnh khung.

Không tự sửa bộ `puzzles/*.json` để gắn ảnh; dùng manifest ở GUI layer.
