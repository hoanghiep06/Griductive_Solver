"""Editable tutorial script. Only already-public clues may justify a move.

The puzzle key lives in level.json and never enters the presentation model.
Rows/columns/neighbors are region forms, not additional clue types. The
encoder's NO shorthand is taught using the schema-compatible EXACTLY 0.
"""

from dataclasses import dataclass
from pathlib import Path

LEVEL_PATH = Path(__file__).with_name("level.json")


@dataclass(frozen=True, slots=True)
class TutorialStep:
    title: str
    observation: str
    analysis: str
    conclusion: str
    focus: str = "move"
    clue_id: str | None = None
    target: str | None = None
    verdict: str | None = None


TUTORIAL_STEPS = (
    TutorialStep(
        "Chào mừng, thám tử!",
        "Đây là bàn tập 4 × 4. A–D là cột; 1–4 là hàng. A1 đã được mở sẵn.",
        "Mỗi người thuộc một trong hai phe: Tội phạm hoặc Vô tội. Thẻ úp chưa cho biết phe.",
        "Mục tiêu là chứng minh phe của cả 16 người bằng manh mối công khai. Hãy bấm Tiếp tục hoặc chạm nền tối.",
        focus="board",
    ),
    TutorialStep(
        "Đọc manh mối trước khi kết luận",
        "Manh mối nằm ngay dưới thẻ A1. Khung đọc bên phải hiển thị đầy đủ: B1 là tội phạm.",
        "Mở một thẻ sẽ công khai cả phe lẫn manh mối của người đó. Lời khai vẫn đúng khi người nói là tội phạm.",
        "Mỗi lượt: đọc manh mối → suy luận → chọn ô sáng → bấm phán quyết. Tiếp tục chỉ mở khóa sau khi bạn làm đúng.",
        focus="clue", clue_id="t_A1",
    ),
    TutorialStep(
        "Sự thật trực tiếp · FACT",
        "Lời khai của A1 khẳng định B1 là tội phạm.",
        "Đây là thông tin trực tiếp; không cần đếm hoặc giả định thêm điều gì.",
        "Do đó B1 chắc chắn là Tội phạm. Chọn B1 trên bàn, rồi bấm Tội phạm.",
        clue_id="t_A1", target="B1", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Cùng phe · SAME",
        "Lời khai vừa mở của B1 cho biết B1 và C1 cùng phe.",
        "B1 đã được chứng minh là tội phạm. Cùng phe nghĩa là hai người có cùng trạng thái.",
        "Do đó C1 cũng là Tội phạm. Chọn C1 và xác nhận phán quyết.",
        clue_id="t_B1", target="C1", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Đếm chính xác trên hàng · EXACTLY",
        "C1 cho biết hàng 1 có đúng 3 tội phạm.",
        "A1, B1, C1 đã là 3 tội phạm. Hàng này chỉ còn D1 chưa mở; chỉ tiêu đã đủ.",
        "Nếu D1 là tội phạm thì tổng sẽ thành 4. Do đó D1 là Vô tội.",
        clue_id="t_C1", target="D1", verdict="INNOCENT",
    ),
    TutorialStep(
        "Khác phe · DIFFERENT",
        "D1 cho biết D1 và A2 khác phe.",
        "D1 vừa được chứng minh vô tội. Hai phe khác nhau nên A2 phải thuộc phe còn lại.",
        "Do đó A2 là Tội phạm.",
        clue_id="t_D1", target="A2", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Giới hạn trên · AT_MOST",
        "A2 cho biết trong nhóm B1, B2 có nhiều nhất 1 tội phạm.",
        "B1 đã là tội phạm, nên giới hạn 1 đã đạt. B2 không thể là tội phạm nữa.",
        "Do đó B2 là Vô tội. “Nhiều nhất 1” nói chung cho phép 0 hoặc 1; ở đây ta đã biết có 1.",
        clue_id="t_A2", target="B2", verdict="INNOCENT",
    ),
    TutorialStep(
        "Giới hạn dưới · AT_LEAST",
        "B2 cho biết trong nhóm B2, C2 có ít nhất 1 tội phạm.",
        "B2 đã vô tội, nên chỉ C2 có thể đáp ứng số lượng tối thiểu này.",
        "Do đó C2 là Tội phạm. “Ít nhất” là giới hạn dưới, không phải lúc nào cũng là số lượng chính xác.",
        clue_id="t_B2", target="C2", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Chẵn và lẻ · PARITY",
        "C2 cho biết nhóm D1, B2, D2 có số tội phạm lẻ.",
        "D1 và B2 đều vô tội: đã biết 0 tội phạm. Chỉ còn D2 chưa rõ; tổng có thể là 0 hoặc 1.",
        "Chỉ 1 là số lẻ. Do đó D2 là Tội phạm. Lưu ý: lẻ có thể là 1, 3, 5… tùy kích thước nhóm.",
        clue_id="t_C2", target="D2", verdict="CRIMINAL",
    ),
    TutorialStep(
        "So sánh hai nhóm · COUNT_COMPARE",
        "D2 cho biết số tội phạm trong {A3, D1} bằng số trong {B1, B2}.",
        "Nhóm B1, B2 có 1 tội phạm. D1 vô tội, nên để nhóm A3, D1 cũng có 1, A3 phải là tội phạm.",
        "Do đó A3 là Tội phạm. Rule này còn hỗ trợ <, ≤, ≠, ≥, >; luôn so sánh số tội phạm, không so số ô.",
        clue_id="t_D2", target="A3", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Đếm trên cột · EXACTLY",
        "A3 cho biết cột A có đúng 4 tội phạm.",
        "Cột A gồm A1, A2, A3, A4. Ba ô đầu đã là tội phạm; chỉ còn A4 để đạt đủ 4.",
        "Do đó A4 là Tội phạm. Quy tắc đếm áp dụng cho cột giống như cho hàng.",
        clue_id="t_A3", target="A4", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Đủ 8 ô xung quanh · NEIGHBORS",
        "A4 cho biết có đúng 8 tội phạm xung quanh B2.",
        "Vùng này gồm A1, B1, C1, A2, C2, A3, B3, C3: tính cả đường chéo, không tính B2. Cả 8 ô phải là tội phạm.",
        "Sáu ô đã mở đều là tội phạm. Do đó B3 và C3 đều là Tội phạm. Trước tiên hãy mở B3.",
        clue_id="t_A4", target="B3", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Hoàn tất vùng lân cận",
        "Ta tiếp tục dùng manh mối của A4: 8 tội phạm quanh B2.",
        "B3 vừa mở nên đã có 7 tội phạm được xác nhận trong 8 ô. Ô cuối cùng của vùng là C3.",
        "Do đó C3 là Tội phạm. Ở cạnh hoặc góc bàn, vùng lân cận chỉ có 5 hoặc 3 ô, không phải luôn là 8.",
        clue_id="t_A4", target="C3", verdict="CRIMINAL",
    ),
    TutorialStep(
        "Hai nhóm đều có số lượng 0",
        "C3 cho biết nhóm {D3} có số tội phạm bằng nhóm {D1}.",
        "D1 vô tội nên nhóm bên phải có 0 tội phạm. Nhóm bên trái chỉ có D3 và cũng phải có 0.",
        "Do đó D3 là Vô tội. Hai nhóm bằng số lượng không nhất thiết có cùng số ô hoặc cùng từng người.",
        clue_id="t_C3", target="D3", verdict="INNOCENT",
    ),
    TutorialStep(
        "Đủ giới hạn trên của hàng",
        "D3 cho biết hàng 4 có nhiều nhất 1 tội phạm.",
        "A4 đã là tội phạm. Vì vậy B4, C4, D4 đều phải vô tội để không vượt quá giới hạn.",
        "Do đó B4 là Vô tội. Hãy mở B4 để đọc thêm manh mối xác nhận các ô cuối.",
        clue_id="t_D3", target="B4", verdict="INNOCENT",
    ),
    TutorialStep(
        "Không có tội phạm · EXACTLY 0",
        "B4 cho biết nhóm C4, D4 có đúng 0 tội phạm.",
        "Số lượng bằng 0 có nghĩa là không ai trong nhóm được thuộc phe tội phạm.",
        "Do đó cả C4 và D4 đều Vô tội. Hãy mở C4 trước. Đây cũng là ý nghĩa của quy tắc “không có”.",
        clue_id="t_B4", target="C4", verdict="INNOCENT",
    ),
    TutorialStep(
        "Phán quyết cuối cùng",
        "Manh mối của B4 vẫn khẳng định C4, D4 có 0 tội phạm.",
        "C4 đã được xác nhận vô tội. D4 cũng không thể là tội phạm vì tổng phải giữ bằng 0.",
        "Do đó D4 là Vô tội. Hãy tự tay khép lại hồ sơ tập luyện!",
        clue_id="t_B4", target="D4", verdict="INNOCENT",
    ),
    TutorialStep(
        "Hoàn thành! Bạn đã phá án",
        "Cả 16 thẻ đã được chứng minh mà không cần đoán.",
        "Bạn đã dùng đủ 8 loại manh mối và các vùng hàng, cột, lân cận, nhóm ô. Khi chơi thật, hãy đọc manh mối mới sau mỗi lần mở thẻ.",
        "Bấm Hoàn thành để trở về giao diện trước đó. Ván chơi chính của bạn vẫn được giữ nguyên.",
        focus="complete",
    ),
)
