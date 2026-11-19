# GRIDUCTIVE — Detective Case Files · Assets Directory (V1.2)

Thư mục tài nguyên hình ảnh chính thức cho Giai đoạn 1 (`GRIDUCTIVE_Detective_Assets_V1_2_UNDER_20MB_(1).zip`), thuộc quyền sở hữu trình bày của **Phước (Thành viên 2 — GUI Engineer)**.

> **Trạng thái duyệt toàn gói:** `PENDING_FINAL_APPROVAL` (đã import và kiểm định kỹ thuật; chờ người dùng phê duyệt sản xuất cuối cùng trước khi phát hành).

## Cấu trúc thư mục

```text
assets/
├── branding/                     # A04: Logo ngang & biểu tượng ứng dụng
│   ├── A04_logo_wide.png         # 1920×819 RGBA (giữ nguyên bản gốc; dùng derived để render)
│   └── A04_app_emblem.png        # 1024×1024 RGB thám tử hoạt hình mới (GĐ3; bản V1.2 cũ sao lưu tại assets/backup/v1_2_original/)
├── backgrounds/                  # A03 & A05: Nền màn hình (PNG indexed 256 màu)
│   ├── A03_main_menu_background.png   # 1672×941 (mode P)
│   └── A05_gameplay_background.png    # 1672×941 (mode P)
├── cards/                        # A01 & A02: Thẻ hồ sơ nghi phạm (tỷ lệ 3:4)
│   ├── A01_card_back.png              # 1086×1448 RGB
│   └── A02_card_front_template.png    # 1086×1448 RGB
├── case_covers/                  # A06 (V1.2 Zoomed): Bìa minh họa chọn màn (1440×1080, 4:3)
│   ├── A06_case_cover_3x3.png         # Minh họa lưới 3×3 (tĩnh, KHÔNG tương tác)
│   ├── A06_case_cover_4x4.png         # Minh họa lưới 4×4 (tĩnh, KHÔNG tương tác)
│   └── A06_case_cover_5x5.png         # Minh họa lưới 5×5 (tĩnh, KHÔNG tương tác)
├── results/                      # A07: Huy hiệu hoàn thành vụ án (gốc từ ZIP)
│   └── A07_case_closed_emblem.png     # 716×535 RGBA (có hạt trắng nền -> dùng bản derived để render)
├── textures/                     # A08: Minh họa giấy chứng cứ (KHÔNG seamless)
│   └── A08_evidence_texture.png       # 858×876 (mode P)
├── clue_icons/                   # A10: Bộ 6 biểu tượng manh mối (RGB có nền + nhãn)
│   ├── A10_clue_icon_atlas.png        # 839×876 RGB (bảng tổng hợp tham khảo)
│   ├── A10_fact.png                   # 232×221 RGB
│   ├── A10_same.png                   # 228×221 RGB
│   ├── A10_different.png              # 228×221 RGB
│   ├── A10_exactly.png                # 234×215 RGB
│   ├── A10_at_least.png               # 233×217 RGB
│   └── A10_at_most.png                # 233×219 RGB
├── derived/                      # Bản làm sạch kỹ thuật không phá hủy (giữ nguyên 18 ảnh gốc)
│   ├── A04_logo_wide_clean.png        # Làm sạch alpha nền ngoài cho A04_logo_wide
│   ├── A04_app_emblem_clean.png       # Loại bỏ checkerboard nền ngoài cho A04_app_emblem
│   ├── A07_case_closed_emblem_clean.png # Làm sạch hạt trắng nền ngoài cho A07_case_closed_emblem
│   └── contact_sheet_v1_2.png         # Bảng duyệt toàn bộ tài nguyên (Phase H Preview)
├── manifest.json                 # Nguồn siêu dữ liệu chuẩn duy nhất (18 gốc + 3 derived)
└── README.md                     # Tài liệu này
```

## Quy tắc tích hợp bắt buộc cho GĐ2+

1. **Truy cập chuẩn qua Registry:** Mọi module PySide6 phải lấy đường dẫn qua `src/gui/asset_registry.py` (`resolve_asset(...)`), **không** hardcode đường dẫn tuyệt đối hoặc phụ thuộc vào thư mục làm việc (`CWD`).
2. **Giữ nguyên 18 file gốc:** Không ghi đè file gốc bằng bản nén lossy hay chỉnh sửa trực tiếp; các bản làm sạch kỹ thuật nằm tại `assets/derived/` và được truy xuất mặc định khi `prefer_derived=True`.
3. **A06 chỉ là ảnh bìa minh họa:** Tuyệt đối không tạo hotspot tương tác hay logic bàn cờ từ pixel của `A06_case_cover_*.png`. `GameBoard` phải được PySide6 dựng động từ `PublicBoardSnapshot`.
4. **A02 và phân biệt `INNOCENT`:** Khung dưới bên trái của `A02_card_front_template.png` được vẽ sẵn màu đỏ thẫm; khi hiển thị `INNOCENT`, PySide6 **bắt buộc** vẽ đè pill/badge `INNOCENT_TEAL` (`#41B99A`) che kín vùng này.
5. **A08 không lặp tile:** `A08_evidence_texture.png` là giấy sáng có góc đạo cụ và con dấu lỗi chữ góc phải trên — không tile lặp, không đặt chữ trắng trực tiếp nếu chưa phủ scrim tối `>= 85%`.
6. **A10 ở kích thước nhỏ:** Chỉ dùng `A10_*.png` ở kích thước `>= 48px`; với biểu tượng nội tuyến `16–32px`, vẽ ký hiệu vector/Qt-native.
7. **Không nhúng dữ liệu runtime/ẩn:** Tên, nghề, trạng thái `CRIMINAL`/`INNOCENT`, manh mối và chữ `CASE CLOSED` đều do PySide6 render động từ public DTO.
