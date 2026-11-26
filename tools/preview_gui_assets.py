"""Bộ sinh trang xem trước Design System & Asset Contact Sheet cho Giai đoạn 1.

Tạo ra:
    1. ``docs/PHUOC_GUI_PHASE1_DESIGN_PREVIEW.html`` — Bảng xem trước trực quan
       bằng tiếng Việt (giữ thuật ngữ kỹ thuật tiếng Anh) hiển thị đủ 18 PNG gốc
       V1.2, so sánh làm sạch Alpha cho 3 ảnh RGBA trên nền #101B30, bảng màu
       Design Tokens và kiểm định tương phản WCAG 2.1.
    2. ``assets/derived/contact_sheet_v1_2.png`` — Ảnh contact sheet 18 tài nguyên
       (khi môi trường Python có sẵn Pillow).

Công cụ này KHÔNG tạo mới hình minh họa và KHÔNG sửa 18 file PNG gốc.
"""

from __future__ import annotations

import html
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gui.asset_registry import DEFAULT_REGISTRY
from src.gui.styles.tokens import (
    ANIMATION,
    COLORS,
    GEOMETRY,
    PRIMITIVE_COLORS,
    TYPOGRAPHY,
    contrast_ratio,
)

_SCREEN_VI = {
    "MAIN_MENU": "Màn hình chính",
    "MAIN_WINDOW": "Cửa sổ chính (MainWindow)",
    "LEVEL_SELECTION": "Chọn vụ án",
    "GAMEPLAY": "Màn chơi",
    "RESULTS": "Kết quả",
    "HOW_TO_PLAY": "Hướng dẫn chơi",
}

_ASSET_NOTES_VI = {
    "A01_CARD_BACK": [
        "Ảnh raster chi tiết (tỷ lệ 3:4); cần lớp phủ scrim tối phía sau chữ Tên/Nghề/UNVERIFIED trên thẻ HIDDEN; dùng khung gọn ở bàn cờ 5×5."
    ],
    "A02_CARD_FRONT_TEMPLATE": [
        "QUAN TRỌNG: Khung verdict góc dưới trái được tô sẵn màu đỏ thẫm. PySide6 bắt buộc vẽ đè pill đặc INNOCENT_TEAL (#41B99A) che kín vùng này khi kết quả là INNOCENT để tránh hiểu nhầm thành CRIMINAL. Dùng chế độ gọn cho bàn 5×5."
    ],
    "A03_MAIN_MENU_BACKGROUND": [
        "PNG bảng màu 256 màu (mode P) có dithering nhẹ từ gói nén <20MB; phủ scrim tối phía sau cụm nút để giữ tương phản >= 4.5:1."
    ],
    "A04_LOGO_WIDE": [
        "Kênh Alpha gốc còn 11.7% nhiễu sáng/mù checkerboard ngoài viền thấy rõ trên nền #101B30. Dùng bản làm sạch không phá hủy assets/derived/A04_logo_wide_clean.png khi hiển thị."
    ],
    "A04_APP_EMBLEM": [
        "Ảnh thám tử hoạt hình (cartoon detective, không phải anime) 1024×1024 RGB do người dùng cung cấp ở GĐ3. Bản V1.2 cũ được sao lưu tại assets/backup/v1_2_original/. Bản icon hình tròn RGBA dùng cho cửa sổ nằm tại assets/derived/A04_app_emblem_clean.png."
    ],
    "A05_GAMEPLAY_BACKGROUND": [
        "PNG bảng màu 256 màu (mode P) có dithering nhẹ ở vùng tường tối; phủ scrim dịu để bàn cờ GameBoard luôn nổi bật nhất."
    ],
    "A06_CASE_COVER_3X3": [
        "Chỉ là ảnh bìa minh họa tĩnh (đúng 3×3 = 9 ô, 1440×1080 tỷ lệ 4:3). Không dùng làm lưới chơi tương tác. Phong cách khung thẳng bo tròn hơi khác nhẹ so với khung bảng kraft nghiêng của bìa 4×4 và 5×5."
    ],
    "A06_CASE_COVER_4X4": [
        "Chỉ là ảnh bìa minh họa tĩnh (đúng 4×4 = 16 ô, 1440×1080 tỷ lệ 4:3). Ghi chú thẩm mỹ nhẹ: kính lúp góc dưới trái che khoảng ~40% ô (4, 1)."
    ],
    "A06_CASE_COVER_5X5": [
        "Chỉ là ảnh bìa minh họa tĩnh (đúng 5×5 = 25 ô, 1440×1080 tỷ lệ 4:3). Ghi chú thẩm mỹ nhẹ: kính lúp góc dưới trái che phần lớn ô (5, 1) và chạm ô (4, 1); góc trên phải ô (1, 5) sát mép trên."
    ],
    "A07_CASE_CLOSED_EMBLEM": [
        "Kênh Alpha gốc còn 19.6% hạt bụi trắng ở vùng ngoài kèm viền sáng ~1px trên #101B30. Dùng bản làm sạch assets/derived/A07_case_closed_emblem_clean.png; chữ CASE CLOSED do PySide6 vẽ động lên dải ruy-băng navy giữa."
    ],
    "A08_EVIDENCE_TEXTURE": [
        "KHÔNG phải seamless tile (cấm lặp gạch). PNG mode P 256 màu. Nền giấy sáng kỵ chữ trắng nếu không phủ scrim tối >= 85% hoặc giảm mờ <= 12%. Con dấu đỏ góc trên phải có ký tự AI vô nghĩa nên phải crop bỏ."
    ],
    "A10_CLUE_ICON_ATLAS": [
        "Ảnh RGB đặc (839×876) gộp đủ 6 loại manh mối kèm logo & nhãn sẵn; chỉ dùng tham khảo / hộp thoại Hướng dẫn chơi, không dùng làm sprite sheet trong suốt."
    ],
    "A10_FACT": [
        "Ảnh raster RGB (232×221) có sẵn khung tối và nhãn FACT. Đọc rõ ở >= 48px (chú giải/header); KHÔNG thu nhỏ xuống 16–32px (dùng vector Qt cho icon nhỏ)."
    ],
    "A10_SAME": [
        "Ảnh raster RGB (228×221) có sẵn khung tối và nhãn SAME. Đọc rõ ở >= 48px; dùng vector Qt cho icon nội tuyến <= 32px."
    ],
    "A10_DIFFERENT": [
        "Ảnh raster RGB (228×221) có sẵn khung tối và nhãn DIFFERENT. Đọc rõ ở >= 48px; dùng vector Qt cho icon nội tuyến <= 32px."
    ],
    "A10_EXACTLY": [
        "Ảnh raster RGB (234×215) có sẵn khung tối và nhãn EXACTLY. Đọc rõ ở >= 48px; dùng vector Qt cho icon nội tuyến <= 32px."
    ],
    "A10_AT_LEAST": [
        "Ảnh raster RGB (233×217) có sẵn khung tối và nhãn AT_LEAST. Đọc rõ ở >= 48px; dùng vector Qt cho icon nội tuyến <= 32px."
    ],
    "A10_AT_MOST": [
        "Ảnh raster RGB (233×219) có sẵn khung tối và nhãn AT_MOST. Đọc rõ ở >= 48px; dùng vector Qt cho icon nội tuyến <= 32px."
    ],
}

_DERIVED_METHOD_VI = {
    "A04_LOGO_WIDE": (
        "Làm sạch không phá hủy bằng flood-fill vùng biên ngoài (alpha < 140) + khử viền sáng 1px: "
        "xóa 184.586 pixel nhiễu nền & 1.499 pixel viền trắng. Giữ nguyên 100% nét vẽ bên trong."
    ),
    "A04_APP_EMBLEM": (
        "Áp mặt nạ hình tròn RGBA khử răng cưa 4x (inset 4px) không phá hủy lên ảnh thám tử hoạt hình "
        "1024×1024 do người dùng cung cấp để hiển thị biểu tượng ứng dụng sắc nét; giữ nguyên ảnh gốc RGB có nền navy."
    ),
    "A07_CASE_CLOSED_EMBLEM": (
        "Làm sạch không phá hủy bằng flood-fill vùng biên ngoài (alpha < 140) + khử viền sáng 1px: "
        "xóa 76.022 pixel hạt bụi trắng & 631 pixel viền sáng. Giữ lại vết anti-alias rất mảnh (~1px) ở vài đoạn cạnh vàng để không ăn mòn nét gốc."
    ),
}


def generate_html_preview(manifest: dict, output_path: Path) -> None:
    """Sinh file HTML tham chiếu kiểm duyệt tài nguyên & Design System bằng tiếng Việt."""
    assets = manifest["assets"]
    derived = manifest["derived_assets"]

    contrast_pairs = [
        ("Chữ chính trên nền ứng dụng (App BG)", COLORS.primary_text, COLORS.app_background),
        ("Chữ chính trên panel nổi (Elevated Panel)", COLORS.primary_text, COLORS.elevated_panel),
        ("Chữ chính trên Detective Blue", COLORS.primary_text, COLORS.card_background),
        ("Chữ phụ trên nền ứng dụng (App BG)", COLORS.secondary_text, COLORS.app_background),
        ("Chữ phụ trên panel nổi (Elevated Panel)", COLORS.secondary_text, COLORS.elevated_panel),
        ("Chữ phụ trên Detective Blue", COLORS.secondary_text, COLORS.card_background),
        ("Chữ vô hiệu hóa (Disabled) trên Panel", COLORS.disabled_text, COLORS.elevated_panel),
        ("Chữ Navy trên nút CTA Evidence Gold", COLORS.text_on_gold, COLORS.accent_primary),
        ("Chữ Paper White trên badge CRIMINAL", COLORS.text_on_crimson, COLORS.criminal_verdict),
        ("Chữ CRIMINAL sáng trên Elevated Panel", COLORS.criminal_text, COLORS.elevated_panel),
        ("Chữ Navy trên badge INNOCENT", COLORS.text_on_innocent, COLORS.innocent_verdict),
        ("Chữ INNOCENT sáng trên Elevated Panel", COLORS.innocent_text, COLORS.elevated_panel),
        ("Highlight Clue Cyan trên App BG", COLORS.clue_highlight, COLORS.app_background),
        ("Highlight Clue Cyan trên Detective Blue", COLORS.clue_highlight, COLORS.card_background),
        ("Cảnh báo (Warning Amber) trên Panel", COLORS.warning, COLORS.elevated_panel),
        ("Báo lỗi (Error Coral) trên Panel", COLORS.error, COLORS.elevated_panel),
    ]

    swatch_cards = []
    for name, hx in PRIMITIVE_COLORS.items():
        fg = "#101B30" if contrast_ratio("#101B30", hx) >= contrast_ratio("#F2F5FA", hx) else "#F2F5FA"
        swatch_cards.append(
            f'<div class="swatch" style="background:{hx};color:{fg}">'
            f'<div class="swatch-name">{html.escape(name)}</div>'
            f'<div class="swatch-hex">{html.escape(hx)}</div>'
            f"</div>"
        )

    contrast_rows = []
    for label, fg, bg in contrast_pairs:
        ratio = contrast_ratio(fg, bg)
        badge = "Đạt AAA" if ratio >= 7.0 else ("Đạt AA" if ratio >= 4.5 else "Không đạt")
        badge_cls = "pass" if ratio >= 4.5 else "fail"
        contrast_rows.append(
            f"<tr>"
            f"<td>{html.escape(label)}</td>"
            f'<td><span class="sample-chip" style="background:{bg};color:{fg}">Mẫu chữ Aa 123 Tiếng Việt</span></td>'
            f"<td><code>{fg}</code> trên <code>{bg}</code></td>"
            f"<td><strong>{ratio:.2f}:1</strong></td>"
            f'<td><span class="pill {badge_cls}">{badge}</span></td>'
            f"</tr>"
        )

    derived_by_source = {d["source_asset_id"]: d for d in derived}
    alpha_comparisons = []
    for src_id in ("A04_LOGO_WIDE", "A04_APP_EMBLEM", "A07_CASE_CLOSED_EMBLEM"):
        orig = next(a for a in assets if a["asset_id"] == src_id)
        clean = derived_by_source[src_id]
        method_vi = _DERIVED_METHOD_VI.get(src_id, clean["method"])
        alpha_comparisons.append(
            f'<div class="compare-row">'
            f"<h4>{html.escape(src_id)} ({orig['dimensions']['width']}×{orig['dimensions']['height']} RGBA)</h4>"
            f'<div class="compare-grid">'
            f'<div class="compare-box">'
            f'<div class="compare-label">Ảnh gốc (từ file ZIP — giữ nguyên byte-for-byte)</div>'
            f'<div class="navy-stage"><img src="../assets/{html.escape(orig["relative_path"])}" alt="{html.escape(src_id)} gốc"></div>'
            f"</div>"
            f'<div class="compare-box">'
            f'<div class="compare-label">Bản làm sạch Alpha (<code>{html.escape(clean["relative_path"])}</code>)</div>'
            f'<div class="navy-stage"><img src="../assets/{html.escape(clean["relative_path"])}" alt="{html.escape(src_id)} đã làm sạch"></div>'
            f"</div>"
            f"</div>"
            f'<p class="note">{html.escape(method_vi)}</p>'
            f"</div>"
        )

    asset_cards = []
    for a in assets:
        w, h = a["dimensions"]["width"], a["dimensions"]["height"]
        status_cls = "warn" if a["validation_status"] == "NEEDS_FIX" else "ok"
        screens_vi = ", ".join(_SCREEN_VI.get(s, s) for s in a["intended_screen"])
        notes_list = _ASSET_NOTES_VI.get(a["asset_id"], a["known_limitations"])
        limits_html = "".join(f"<li>{html.escape(x)}</li>" for x in notes_list)
        alpha_label = "Có" if a["transparency"] else "Không"
        asset_cards.append(
            f'<article class="asset-card">'
            f'<div class="asset-thumb"><img src="../assets/{html.escape(a["relative_path"])}" alt="{html.escape(a["asset_id"])}"></div>'
            f'<div class="asset-meta">'
            f'<div class="asset-title"><strong>{html.escape(a["asset_id"])}</strong> '
            f'<span class="pill {status_cls}">{html.escape(a["validation_status"])}</span> '
            f'<span class="pill pending">{html.escape(a["approval_status"])}</span></div>'
            f'<div class="asset-sub"><code>{html.escape(a["relative_path"])}</code></div>'
            f'<div class="asset-specs">{w}×{h} (tỷ lệ {a["dimensions"]["aspect_ratio"]}) · mode={html.escape(a["color_mode"])} · '
            f'Alpha: {alpha_label} · {a["file_size_bytes"]:,} byte</div>'
            f'<div class="asset-screens">Màn hình sử dụng: {html.escape(screens_vi)}</div>'
            f'<ul class="asset-notes">{limits_html}</ul>'
            f"</div></article>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>GRIDUCTIVE — Xem trước Tài nguyên &amp; Design System Giai đoạn 1 (V1.2)</title>
  <style>
    :root {{
      --bg: {COLORS.app_background};
      --deep: {COLORS.backdrop_deep};
      --panel: {COLORS.elevated_panel};
      --blue: {COLORS.card_background};
      --gold: {COLORS.accent_primary};
      --cyan: {COLORS.clue_highlight};
      --crimson: {COLORS.criminal_verdict};
      --teal: {COLORS.innocent_verdict};
      --text: {COLORS.primary_text};
      --muted: {COLORS.secondary_text};
      --border: {COLORS.border_subtle};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 28px;
      background: var(--bg); color: var(--text);
      font-family: "Noto Sans", "Inter", "DejaVu Sans", sans-serif;
      line-height: 1.5;
    }}
    h1, h2, h3, h4 {{ margin-top: 0; color: var(--gold); }}
    .banner {{
      background: var(--panel); border: 1px solid var(--gold);
      border-radius: 12px; padding: 18px 22px; margin-bottom: 24px;
    }}
    .banner p {{ margin: 6px 0; color: var(--muted); }}
    .section {{ margin-bottom: 34px; }}
    .swatches {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(175px, 1fr)); gap: 10px; }}
    .swatch {{ padding: 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.12); }}
    .swatch-name {{ font-weight: 700; font-size: 12px; }}
    .swatch-hex {{ font-family: monospace; font-size: 13px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 10px; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; font-size: 13px; }}
    th {{ background: var(--blue); color: var(--gold); }}
    .sample-chip {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-weight: 600; }}
    .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }}
    .pill.pass, .pill.ok {{ background: var(--teal); color: #101B30; }}
    .pill.warn {{ background: #F2B84B; color: #101B30; }}
    .pill.fail {{ background: var(--crimson); color: #F2F5FA; }}
    .pill.pending {{ background: var(--blue); color: var(--gold); border: 1px solid var(--gold); }}
    .compare-row {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    .compare-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .compare-label {{ font-size: 12px; color: var(--muted); margin-bottom: 8px; }}
    .navy-stage {{
      background: #101B30; border: 1px solid var(--border); border-radius: 8px;
      padding: 16px; display: flex; align-items: center; justify-content: center; min-height: 220px;
    }}
    .navy-stage img {{ max-width: 100%; max-height: 240px; object-fit: contain; }}
    .note {{ font-size: 12px; color: var(--muted); margin: 10px 0 0; }}
    .assets-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; }}
    .asset-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }}
    .asset-thumb {{
      background: #0B1220; height: 220px; display: flex; align-items: center; justify-content: center; padding: 10px;
      border-bottom: 1px solid var(--border);
    }}
    .asset-thumb img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
    .asset-meta {{ padding: 14px; font-size: 13px; }}
    .asset-title {{ margin-bottom: 6px; }}
    .asset-sub {{ color: var(--cyan); font-size: 12px; margin-bottom: 4px; }}
    .asset-specs, .asset-screens {{ color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
    .asset-notes {{ margin: 8px 0 0; padding-left: 18px; color: var(--text); font-size: 12px; }}
    .tokens-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
    .token-box {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 14px; font-size: 13px; }}
    code {{ font-family: "DejaVu Sans Mono", monospace; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="banner">
    <h1>GRIDUCTIVE — Hồ sơ Phá án · Xem trước Tài nguyên &amp; Design System GĐ1 (V1.2)</h1>
    <p><strong>Phạm vi:</strong> Bảng tham chiếu kiểm duyệt tài nguyên &amp; Design System của GĐ1 — <strong>KHÔNG phải màn hình chơi PySide6 chạy thật</strong>.</p>
    <p><strong>Phân tách bắt buộc:</strong> Ảnh tĩnh (A01–A10) chỉ là nền/khung/bìa trang trí. Toàn bộ lưới chơi N×N, tên nhân vật, nghề nghiệp, phán quyết CRIMINAL/INNOCENT, manh mối công khai và chữ CASE CLOSED do PySide6 vẽ động từ public DTO ở GĐ2–GĐ5.</p>
    <p><strong>Trạng thái duyệt gói:</strong> <span class="pill pending">{html.escape(manifest["package_approval_status"])}</span> · 18 PNG gốc bảo toàn nguyên vẹn + 3 PNG làm sạch Alpha tại <code>assets/derived/</code>.</p>
  </div>

  <section class="section">
    <h2>1. Bảng màu cơ bản (Primitive Color Tokens)</h2>
    <div class="swatches">{"".join(swatch_cards)}</div>
  </section>

  <section class="section">
    <h2>2. Kiểm định độ đọc &amp; tương phản chuẩn WCAG 2.1</h2>
    <table>
      <thead><tr><th>Cặp màu ngữ nghĩa</th><th>Xem trước</th><th>Mã Hex</th><th>Tỷ lệ</th><th>Chuẩn WCAG</th></tr></thead>
      <tbody>{"".join(contrast_rows)}</tbody>
    </table>
  </section>

  <section class="section">
    <h2>3. Tóm tắt thông số Geometry, Spacing, Typography &amp; Animation</h2>
    <div class="tokens-grid">
      <div class="token-box">
        <h4>Thang khoảng cách (Spacing)</h4>
        <code>4 / 8 / 12 / 16 / 24 / 32 px</code><br>
        Đệm panel: <code>{GEOMETRY.panel_padding}px</code> · Chiều cao nút tối thiểu: <code>{GEOMETRY.button_min_height}px</code>
      </div>
      <div class="token-box">
        <h4>Tỷ lệ Thẻ bài &amp; Cửa sổ</h4>
        Thẻ chuẩn: <code>{GEOMETRY.card_design_width}×{GEOMETRY.card_design_height} px (3:4)</code><br>
        Thẻ gọn 5×5: <code>{GEOMETRY.card_compact_width}×{GEOMETRY.card_compact_height} px (3:4)</code><br>
        Cửa sổ mặc định / tối thiểu: <code>1600×900</code> / <code>{GEOMETRY.window_min_width}×{GEOMETRY.window_min_height}</code>
      </div>
      <div class="token-box">
        <h4>Thông số Animation</h4>
        Lật thẻ (Card Flip): <code>{ANIMATION.card_flip_duration_ms}ms ({ANIMATION.easing_card_flip})</code><br>
        Hover / Highlight: <code>{ANIMATION.hover_duration_ms}ms / {ANIMATION.highlight_duration_ms}ms</code><br>
        Chuyển panel / Kết quả: <code>{ANIMATION.panel_transition_ms}ms / {ANIMATION.result_reveal_ms}ms</code><br>
        Giảm chuyển động (Reduced Motion): <code>{ANIMATION.reduced_motion_duration_ms}ms (queued)</code>
      </div>
      <div class="token-box">
        <h4>Bộ chữ (Typography)</h4>
        UI: <code>{html.escape(", ".join(TYPOGRAPHY.font_family_ui[:4]))}</code><br>
        Tiêu đề: <code>{html.escape(", ".join(TYPOGRAPHY.font_family_display[:3]))}</code><br>
        Nội dung / Phụ chú / Tối thiểu: <code>{TYPOGRAPHY.size_body}px / {TYPOGRAPHY.size_metadata}px / {TYPOGRAPHY.size_min_readable}px</code>
      </div>
    </div>
  </section>

  <section class="section">
    <h2>4. Kiểm định kênh trong suốt (Alpha) — Trước &amp; Sau khi làm sạch trên nền #101B30</h2>
    {"".join(alpha_comparisons)}
  </section>

  <section class="section">
    <h2>5. Toàn bộ danh mục 18 ảnh PNG gốc (V1.2)</h2>
    <div class="assets-grid">{"".join(asset_cards)}</div>
  </section>
</body>
</html>
"""
    output_path.write_text(html_doc, encoding="utf-8")


def generate_contact_sheet(manifest: dict, output_path: Path) -> bool:
    """Sinh ảnh contact sheet 18 tài nguyên nếu môi trường có Pillow."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    assets = manifest["assets"]
    cols = 3
    rows = (len(assets) + cols - 1) // cols
    cell_w, cell_h = 360, 250
    pad = 16
    header_h = 64
    canvas_w = cols * cell_w + (cols + 1) * pad
    canvas_h = header_h + rows * cell_h + (rows + 1) * pad

    sheet = Image.new("RGB", (canvas_w, canvas_h), (0x10, 0x1B, 0x30))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle([(0, 0), (canvas_w, header_h)], fill=(0x15, 0x22, 0x38))
    draw.text(
        (pad, 16),
        "GRIDUCTIVE - Detective Case Files | V1.2 Asset Contact Sheet (18 Original PNGs - PENDING_FINAL_APPROVAL)",
        fill=(0xE4, 0xB9, 0x6D),
    )
    draw.text(
        (pad, 38),
        "Decorative artwork reference only. Runtime UI text, grids, verdicts and clues are rendered dynamically by PySide6.",
        fill=(0xB8, 0xC4, 0xD8),
    )

    assets_root = DEFAULT_REGISTRY.root
    for idx, entry in enumerate(assets):
        r, c = divmod(idx, cols)
        x0 = pad + c * (cell_w + pad)
        y0 = header_h + pad + r * (cell_h + pad)
        draw.rounded_rectangle(
            [(x0, y0), (x0 + cell_w, y0 + cell_h)],
            radius=10,
            fill=(0x15, 0x22, 0x38),
            outline=(0x42, 0x54, 0x6E),
            width=1,
        )
        img_box_h = 186
        with Image.open(assets_root / entry["relative_path"]) as raw_im:
            rgba = raw_im.convert("RGBA")
            rgba.thumbnail((cell_w - 20, img_box_h - 14))
            bg = Image.new("RGBA", rgba.size, (0x0B, 0x12, 0x20, 255))
            comp = Image.alpha_composite(bg, rgba).convert("RGB")
            px = x0 + (cell_w - comp.width) // 2
            py = y0 + 8 + (img_box_h - 14 - comp.height) // 2
            sheet.paste(comp, (px, py))

        dims = entry["dimensions"]
        label1 = f"{entry['asset_id']} [{entry['validation_status']}]"
        label2 = f"{dims['width']}x{dims['height']} | mode={entry['color_mode']} | alpha={entry['transparency']}"
        draw.text((x0 + 10, y0 + img_box_h + 4), label1, fill=(0xF2, 0xF5, 0xFA))
        draw.text((x0 + 10, y0 + img_box_h + 24), label2, fill=(0xB8, 0xC4, 0xD8))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)
    return True


def main() -> int:
    report = DEFAULT_REGISTRY.validate(verify_sha256=True)
    if not report.valid:
        print("ASSET VALIDATION FAILED:", report.errors, file=sys.stderr)
        return 1
    manifest = DEFAULT_REGISTRY.load_manifest()
    html_out = ROOT / "docs" / "PHUOC_GUI_PHASE1_DESIGN_PREVIEW.html"
    generate_html_preview(manifest, html_out)
    print(f"Wrote HTML design preview: {html_out}")

    sheet_out = ROOT / "assets" / "derived" / "contact_sheet_v1_2.png"
    if generate_contact_sheet(manifest, sheet_out):
        print(f"Wrote PNG contact sheet: {sheet_out}")
    else:
        print("Skipped PNG contact sheet (Pillow not installed in this interpreter).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
