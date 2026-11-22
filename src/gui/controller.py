from __future__ import annotations

import importlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.gui.clue_highlighter import ClueHighlighter, Coord, HighlightState


class GuessErrorType(str, Enum):
    """Phân loại lỗi khi người dùng đoán sai hoặc đoán chưa đủ căn cứ."""

    NONE = "NONE"
    NOT_PROVABLE = "NOT_PROVABLE"  # Chưa đủ dữ kiện trong KB_t (UNKNOWN)
    CONTRADICTED = "CONTRADICTED"  # Mâu thuẫn trực tiếp với KB_t (UNSAT)


class AutoSolveStatus(str, Enum):
    """Trạng thái kết thúc của một bước hoặc toàn bộ phiên Auto Solve."""

    STEP_APPLIED = "STEP_APPLIED"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    PAUSED = "PAUSED"


@dataclass
class ErrorDialogPayload:
    """Dữ liệu hiển thị hộp thoại giải thích lỗi khi người chơi đoán sai."""

    error_type: GuessErrorType
    title: str
    message: str
    row: int
    col: int
    guessed_label: str  # "CRIMINAL" | "INNOCENT"
    related_clue_ids: List[str] = field(default_factory=list)
    can_request_hint: bool = True


@dataclass
class GuessOutcome:
    """Kết quả trả về sau khi người dùng chọn trạng thái cho một ô."""

    accepted: bool
    row: int
    col: int
    assigned_label: Optional[str] = None
    newly_revealed_clues: List[Any] = field(default_factory=list)
    error_dialog: Optional[ErrorDialogPayload] = None
    is_puzzle_solved: bool = False


@dataclass
class HintResult:
    """Kết quả gợi ý 2 tầng (Tier 1: Nudge chỉ hướng -> Tier 2: Reveal đáp án)."""

    available: bool
    tier: int  # 1 = Nudge (highlight ô + manh mối), 2 = Reveal (công bố kết luận + metrics)
    row: Optional[int] = None
    col: Optional[int] = None
    inferred_label: Optional[str] = None  # Chỉ có ở Tier 2
    supporting_clue_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class AutoSolveStepResult:
    """Kết quả mỗi nhịp thực thi Auto Solve."""

    status: AutoSolveStatus
    row: Optional[int] = None
    col: Optional[int] = None
    assigned_label: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


class InteractionController:
    """
    Tầng điều phối trung tâm của TV 3:
    - Kết nối GameEngine, PublicKB, EntailmentChecker với giao diện (GridView / AppWindow).
    - Tách biệt hoàn toàn khỏi thư viện đồ họa để test headless và dễ gắn với mọi GUI.
    """

    def __init__(
        self,
        engine_factory: Optional[Callable[[Any], Any]] = None,
        kb_factory: Optional[Callable[[Any], Any]] = None,
        entailment_factory: Optional[Callable[[Any, Any], Any]] = None,
        validator: Optional[Any] = None,
    ) -> None:
        self._engine_factory = engine_factory
        self._kb_factory = kb_factory
        self._entailment_factory = entailment_factory
        self._validator = validator

        self.puzzle_data: Optional[Any] = None
        self.puzzle_path: Optional[str] = None
        self.engine: Optional[Any] = None
        self.public_kb: Optional[Any] = None
        self.entailment_checker: Optional[Any] = None
        self.highlighter = ClueHighlighter()

        # Trạng thái phiên chơi
        self.step_count: int = 0
        self.mistake_count: int = 0
        self.hint_count: int = 0
        self.start_time: float = time.perf_counter()
        self.is_auto_solving: bool = False
        self.is_paused: bool = False
        self.step_delay_ms: int = 450

        # Trạng thái Hint 2 tầng
        self._last_hint_cell: Optional[Coord] = None
        self._last_hint_tier: int = 0

        # Event hooks cho GUI (TV 2 đăng ký callback vào đây)
        self.on_state_changed: Optional[Callable[[], None]] = None
        self.on_card_flipped: Optional[Callable[[int, int, str], None]] = None
        self.on_highlight_changed: Optional[Callable[[HighlightState], None]] = None
        self.on_error_dialog: Optional[Callable[[ErrorDialogPayload], None]] = None
        self.on_status_message: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # 1. NẠP MÀN CHƠI & KHỞI ĐỘNG LẠI (Load Puzzle & Restart)
    # ------------------------------------------------------------------

    @staticmethod
    def list_manifest_puzzles(manifest_path: str | Path = "puzzles/manifest.json") -> List[Dict[str, Any]]:
        """Đọc danh sách màn chơi từ puzzles/manifest.json để hiển thị menu chọn map."""
        path = Path(manifest_path)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            if "puzzles" in raw and isinstance(raw["puzzles"], list):
                return raw["puzzles"]
            if "maps" in raw and isinstance(raw["maps"], list):
                return raw["maps"]
        return []

    def load_puzzle(self, puzzle_source: str | Path | Any, validate: Optional[bool] = None) -> None:
        """Nạp màn chơi từ đường dẫn JSON hoặc đối tượng Puzzle đã parse."""
        should_validate = (
            validate
            if validate is not None
            else (self._validator is not None or self._engine_factory is None)
        )

        if isinstance(puzzle_source, (str, Path)):
            path = Path(puzzle_source)
            self.puzzle_path = str(path)
            raw_json = json.loads(path.read_text(encoding="utf-8"))
            if should_validate:
                self._validate_loaded_puzzle(raw_json)
            self.puzzle_data = self._parse_puzzle_object(raw_json, path)
        else:
            self.puzzle_path = None
            if should_validate and isinstance(puzzle_source, dict):
                self._validate_loaded_puzzle(puzzle_source)
            self.puzzle_data = puzzle_source

        self._initialize_session()
        self._emit_status(f"Đã nạp màn chơi ({self.grid_size}x{self.grid_size}).")

    def restart(self) -> None:
        """Khôi phục tức thì ván chơi hiện tại về KB_0."""
        if self.puzzle_data is None:
            raise RuntimeError("Chưa có màn chơi nào được nạp để Restart.")
        self._initialize_session()
        self._emit_status("Đã đặt lại ván chơi về trạng thái ban đầu (KB_0).")

    def _initialize_session(self) -> None:
        self.is_auto_solving = False
        self.is_paused = False
        self.step_count = 0
        self.mistake_count = 0
        self.hint_count = 0
        self._last_hint_cell = None
        self._last_hint_tier = 0
        self.start_time = time.perf_counter()

        self.engine = self._build_engine(self.puzzle_data)
        self.public_kb = self._build_public_kb(self.puzzle_data, self.engine)
        self.entailment_checker = self._build_entailment_checker(self.puzzle_data, self.public_kb)

        self._sync_highlighter_with_kb()
        self.highlighter.clear()
        self._emit_highlight()
        self._emit_state()

    # ------------------------------------------------------------------
    # 2. HIGHLIGHT HAI CHIỀU
    # ------------------------------------------------------------------

    def on_clue_clicked(self, clue_id: str) -> HighlightState:
        """Người dùng bấm vào 1 manh mối -> Tô sáng ô nguồn + vùng tham chiếu."""
        state = self.highlighter.select_clue(clue_id, toggle=True)
        self._emit_highlight()
        return state

    def on_cell_inspected(self, row: int, col: int) -> HighlightState:
        """Người dùng inspect ô (row, col) -> Tô sáng các manh mối liên quan."""
        state = self.highlighter.inspect_cell(row, col)
        self._emit_highlight()
        return state

    def clear_highlights(self) -> HighlightState:
        state = self.highlighter.clear()
        self._emit_highlight()
        return state

    # ------------------------------------------------------------------
    # 3. XỬ LÝ ĐOÁN CỦA NGƯỜI CHƠI & HỘP THOẠI LỖI (NOT_PROVABLE vs CONTRADICTED)
    # ------------------------------------------------------------------

    def submit_guess(self, row: int, col: int, guessed_is_criminal: bool) -> GuessOutcome:
        """
        Xử lý khi người chơi gán nhãn CRIMINAL / INNOCENT cho ô (row, col).
        - Chỉ cho phép lật khi KB_t chứng minh được trạng thái đó (No-Guess invariant).
        - Nếu sai/chưa chứng minh được: phân biệt rõ CONTRADICTED và NOT_PROVABLE.
        """
        if self.engine is None or self.public_kb is None:
            raise RuntimeError("Chưa nạp màn chơi.")

        if self.is_auto_solving and not self.is_paused:
            return GuessOutcome(
                accepted=False,
                row=row,
                col=col,
                error_dialog=ErrorDialogPayload(
                    error_type=GuessErrorType.NOT_PROVABLE,
                    title="Đang chạy Auto Solve",
                    message="Hệ thống đang tự động suy luận. Hãy tạm dừng (Pause) trước khi thao tác tay.",
                    row=row,
                    col=col,
                    guessed_label="CRIMINAL" if guessed_is_criminal else "INNOCENT",
                    can_request_hint=False,
                ),
            )

        if self.is_cell_revealed(row, col):
            return GuessOutcome(accepted=True, row=row, col=col, is_puzzle_solved=self.is_solved())

        guessed_label = "CRIMINAL" if guessed_is_criminal else "INNOCENT"
        proven_status, _ = self._evaluate_cell_entailment(row, col)

        # Trường hợp 1: Đúng với trạng thái bị ép buộc bởi KB_t
        if proven_status == guessed_label:
            new_clues = self._apply_reveal(row, col, guessed_is_criminal)
            self._last_hint_cell = None
            self._last_hint_tier = 0
            solved = self.is_solved()
            if solved:
                self._emit_status("Chúc mừng! Bạn đã giải xong toàn bộ bàn cờ không cần đoán mò.")
            return GuessOutcome(
                accepted=True,
                row=row,
                col=col,
                assigned_label=guessed_label,
                newly_revealed_clues=new_clues,
                is_puzzle_solved=solved,
            )

        # Trường hợp 2: Không được phép lật -> Tăng bộ đếm lỗi và phân loại nguyên nhân
        self.mistake_count += 1
        active_clues = self.get_active_clues()

        # Kiểm tra xem giả thiết H_i = (row, col == guessed_is_criminal) có mâu thuẫn với KB_t không
        is_consistent = self._is_hypothesis_consistent(active_clues, row, col, guessed_is_criminal)

        if not is_consistent:
            # KB_t ∧ H_i == UNSAT -> CONTRADICTED
            culprit_ids = self._find_contradicting_clue_ids(active_clues, row, col, guessed_is_criminal)
            if culprit_ids:
                self.highlighter.highlight_contradiction((row, col), culprit_ids)
                self._emit_highlight()

            culprit_text = ", ".join(culprit_ids) if culprit_ids else "tập manh mối hiện tại"
            payload = ErrorDialogPayload(
                error_type=GuessErrorType.CONTRADICTED,
                title="Mâu thuẫn logic (CONTRADICTED)",
                message=(
                    f"Gán ô ({row + 1}, {col + 1}) là {guessed_label} mâu thuẫn trực tiếp với "
                    f"manh mối đang mở ({culprit_text}). Các manh mối liên quan đã được tô sáng đỏ."
                ),
                row=row,
                col=col,
                guessed_label=guessed_label,
                related_clue_ids=culprit_ids,
                can_request_hint=True,
            )
        else:
            # KB_t ∧ H_i == SAT và KB_t ∧ ¬H_i == SAT -> NOT_PROVABLE (UNKNOWN)
            payload = ErrorDialogPayload(
                error_type=GuessErrorType.NOT_PROVABLE,
                title="Chưa đủ dữ kiện chứng minh (NOT_PROVABLE)",
                message=(
                    f"Từ các manh mối hiện có trong KB_{self.step_count}, chưa thể khẳng định chắc chắn "
                    f"ô ({row + 1}, {col + 1}) là {guessed_label}. Luật No-Guess không cho phép đoán mò."
                ),
                row=row,
                col=col,
                guessed_label=guessed_label,
                related_clue_ids=[],
                can_request_hint=True,
            )

        self._emit_state()
        if self.on_error_dialog is not None:
            self.on_error_dialog(payload)

        return GuessOutcome(
            accepted=False,
            row=row,
            col=col,
            error_dialog=payload,
            is_puzzle_solved=False,
        )

    # ------------------------------------------------------------------
    # 4. GỢI Ý THÔNG MINH 2 TẦNG (Hint)
    # ------------------------------------------------------------------

    def hint(self) -> HintResult:
        """
        Gợi ý thông minh 2 tầng theo thứ tự duyệt row-major:
        - Lần 1 trên ô (r, c): Tô sáng ô mục tiêu + tập manh mối hỗ trợ tối thiểu (Nudge).
        - Lần 2 trên cùng ô (r, c): Công bố rõ CRIMINAL / INNOCENT kèm SAT metrics (Reveal).
        """
        if self.engine is None or self.public_kb is None:
            raise RuntimeError("Chưa nạp màn chơi.")

        forced = self._find_next_forced_cell_row_major()
        if forced is None:
            msg = (
                "Bàn cờ đã được giải hoàn toàn."
                if self.is_solved()
                else "Không tìm thấy ô nào bị ép buộc thêm từ KB hiện tại (STUCK)."
            )
            self._emit_status(msg)
            return HintResult(available=False, tier=0, message=msg)

        row, col, label, metrics = forced
        coord = (row, col)
        supporting_ids = self._find_minimal_supporting_clues(row, col, label == "CRIMINAL")

        if self._last_hint_cell == coord and self._last_hint_tier >= 1:
            tier = 2
            self._last_hint_tier = 2
            msg = (
                f"Gợi ý chi tiết: Ô ({row + 1}, {col + 1}) bắt buộc là {label} "
                f"(dựa trên {', '.join(supporting_ids) if supporting_ids else 'KB hiện tại'})."
            )
        else:
            tier = 1
            self._last_hint_cell = coord
            self._last_hint_tier = 1
            self.hint_count += 1
            msg = (
                f"Gợi ý hướng suy luận: Hãy kiểm tra ô ({row + 1}, {col + 1}) "
                f"bằng cách đối chiếu các manh mối đang được tô sáng."
            )

        self.highlighter.highlight_hint(coord, supporting_ids)
        self._emit_highlight()
        self._emit_state()
        self._emit_status(msg)

        return HintResult(
            available=True,
            tier=tier,
            row=row,
            col=col,
            inferred_label=label if tier == 2 else None,
            supporting_clue_ids=supporting_ids,
            metrics=metrics,
            message=msg,
        )

    # ------------------------------------------------------------------
    # 5. TỰ ĐỘNG GIẢI NO-GUESS (Auto Solve)
    # ------------------------------------------------------------------

    def start_auto_solve(self, step_delay_ms: Optional[int] = None) -> None:
        if step_delay_ms is not None:
            self.step_delay_ms = max(0, int(step_delay_ms))
        self.is_auto_solving = True
        self.is_paused = False
        self._emit_state()

    def pause_auto_solve(self) -> None:
        if self.is_auto_solving:
            self.is_paused = True
            self._emit_state()

    def resume_auto_solve(self) -> None:
        if self.is_auto_solving:
            self.is_paused = False
            self._emit_state()

    def auto_solve_step(self) -> AutoSolveStepResult:
        """Thực thi đúng 1 bước suy luận No-Guess (gọi bởi GUI timer hoặc vòng lặp)."""
        if self.engine is None or self.public_kb is None:
            raise RuntimeError("Chưa nạp màn chơi.")

        if self.is_paused:
            return AutoSolveStepResult(status=AutoSolveStatus.PAUSED, message="Auto Solve đang tạm dừng.")

        if self.is_solved():
            self.is_auto_solving = False
            self._emit_state()
            return AutoSolveStepResult(status=AutoSolveStatus.SOLVED, message="Đã giải xong toàn bộ bàn cờ.")

        forced = self._find_next_forced_cell_row_major()
        if forced is None:
            self.is_auto_solving = False
            self._emit_state()
            msg = "Auto Solve dừng lại: Không còn ô nào bị ép buộc (STUCK)."
            self._emit_status(msg)
            return AutoSolveStepResult(status=AutoSolveStatus.STUCK, message=msg)

        row, col, label, metrics = forced
        self._apply_reveal(row, col, label == "CRIMINAL")
        self.highlighter.highlight_hint((row, col), [])
        self._emit_highlight()

        if self.is_solved():
            self.is_auto_solving = False
            self._emit_state()
            msg = f"Hoàn thành! Bước cuối: ({row + 1}, {col + 1}) = {label}."
            self._emit_status(msg)
            return AutoSolveStepResult(
                status=AutoSolveStatus.SOLVED,
                row=row,
                col=col,
                assigned_label=label,
                metrics=metrics,
                message=msg,
            )

        msg = f"Bước {self.step_count}: Suy ra ({row + 1}, {col + 1}) = {label}."
        self._emit_status(msg)
        return AutoSolveStepResult(
            status=AutoSolveStatus.STEP_APPLIED,
            row=row,
            col=col,
            assigned_label=label,
            metrics=metrics,
            message=msg,
        )

    def run_auto_solve(self, max_steps: int = 200) -> List[AutoSolveStepResult]:
        """Chạy trọn vẹn vòng lặp No-Guess (dùng cho chế độ Instant hoặc kiểm thử)."""
        self.start_auto_solve(step_delay_ms=0)
        history: List[AutoSolveStepResult] = []
        for _ in range(max_steps):
            res = self.auto_solve_step()
            history.append(res)
            if res.status in (AutoSolveStatus.SOLVED, AutoSolveStatus.STUCK, AutoSolveStatus.PAUSED):
                break
        self.is_auto_solving = False
        self._emit_state()
        return history

    # ------------------------------------------------------------------
    # 6. THUẬT TOÁN RÚT GỌN MANH MỐI (MUS / MINIMAL SUPPORTING SET)
    # ------------------------------------------------------------------

    def _find_contradicting_clue_ids(
        self, active_clues: Sequence[Any], row: int, col: int, guessed_is_criminal: bool
    ) -> List[str]:
        """Tìm tập manh mối tối thiểu (MUS) trong KB_t mâu thuẫn với giả thiết của người chơi."""
        if not active_clues:
            return []

        # 1. Ưu tiên kiểm tra mâu thuẫn trực tiếp từ 1 manh mối đơn lẻ (rất nhanh & dễ hiểu)
        direct_single: List[str] = []
        for idx, clue in enumerate(active_clues):
            cid = self._get_clue_id(clue, idx)
            if not self._is_hypothesis_consistent([clue], row, col, guessed_is_criminal):
                direct_single.append(cid)
        if direct_single:
            return direct_single

        # 2. Deletion-based Minimal Unsatisfiable Subset (MUS) nếu cần kết hợp nhiều manh mối
        working = list(active_clues)
        i = 0
        while i < len(working) and len(working) > 1:
            candidate = working[:i] + working[i + 1 :]
            if not self._is_hypothesis_consistent(candidate, row, col, guessed_is_criminal):
                working = candidate
            else:
                i += 1

        return [self._get_clue_id(c, idx) for idx, c in enumerate(working)]

    def _find_minimal_supporting_clues(
        self, row: int, col: int, proven_is_criminal: bool
    ) -> List[str]:
        """Tìm tập manh mối tối thiểu trong KB_t đủ để chứng minh (row, col) == proven_is_criminal."""
        active_clues = self.get_active_clues()
        if not active_clues:
            return []

        # Giả thiết phủ định ¬L phải cho ra UNSAT trên tập manh mối hỗ trợ
        negated = not proven_is_criminal
        if self._is_hypothesis_consistent(active_clues, row, col, negated):
            return []

        working = list(active_clues)
        i = 0
        while i < len(working) and len(working) > 1:
            candidate = working[:i] + working[i + 1 :]
            if not self._is_hypothesis_consistent(candidate, row, col, negated):
                working = candidate
            else:
                i += 1

        return [self._get_clue_id(c, idx) for idx, c in enumerate(working)]

    # ------------------------------------------------------------------
    # 7. LỚP TƯƠNG THÍCH (ADAPTER) VỚI CORE ENGINE & ENTAILMENT CHECKER
    # ------------------------------------------------------------------

    @property
    def grid_size(self) -> int:
        if self.engine is not None:
            for attr in ("size", "grid_size", "n", "N"):
                val = getattr(self.engine, attr, None)
                if isinstance(val, int) and val > 0:
                    return val
        if isinstance(self.puzzle_data, dict):
            for key in ("size", "grid_size", "n"):
                if isinstance(self.puzzle_data.get(key), int):
                    return int(self.puzzle_data[key])
            grid = self.puzzle_data.get("grid") or self.puzzle_data.get("characters")
            if isinstance(grid, list) and grid:
                return len(grid)
        return 3

    def is_cell_revealed(self, row: int, col: int) -> bool:
        if self.engine is None:
            return False
        if hasattr(self.engine, "is_revealed"):
            return bool(self.engine.is_revealed(row, col))
        revealed = self.get_revealed_cells()
        return (row, col) in revealed

    def get_revealed_cells(self) -> Dict[Coord, str]:
        """Trả về dict {(row, col): 'CRIMINAL' | 'INNOCENT'} cho các ô đã mở."""
        if self.engine is None:
            return {}
        if hasattr(self.engine, "get_revealed_cells"):
            raw = self.engine.get_revealed_cells()
            if isinstance(raw, dict):
                return {
                    k: ("CRIMINAL" if v in (True, "CRIMINAL", "criminal") else "INNOCENT")
                    for k, v in raw.items()
                }
        result: Dict[Coord, str] = {}
        n = self.grid_size
        for r in range(n):
            for c in range(n):
                if hasattr(self.engine, "get_cell_state"):
                    st = str(self.engine.get_cell_state(r, c)).upper()
                    if st in ("CRIMINAL", "INNOCENT"):
                        result[(r, c)] = st
                elif hasattr(self.engine, "revealed"):
                    rev = getattr(self.engine, "revealed")
                    if isinstance(rev, dict) and (r, c) in rev:
                        val = rev[(r, c)]
                        result[(r, c)] = "CRIMINAL" if val in (True, "CRIMINAL") else "INNOCENT"
                    elif isinstance(rev, (set, list)) and (r, c) in rev:
                        truth = self._get_ground_truth_label(r, c)
                        if truth:
                            result[(r, c)] = truth
        return result

    def is_solved(self) -> bool:
        if self.engine is not None and hasattr(self.engine, "is_solved"):
            return bool(self.engine.is_solved())
        n = self.grid_size
        return len(self.get_revealed_cells()) >= n * n

    def get_active_clues(self) -> List[Any]:
        if self.public_kb is None:
            return []
        if hasattr(self.public_kb, "get_clues"):
            return list(self.public_kb.get_clues())
        if hasattr(self.public_kb, "revealed_clues"):
            return list(self.public_kb.revealed_clues)
        if hasattr(self.public_kb, "clues"):
            clues = getattr(self.public_kb, "clues")
            if isinstance(clues, dict):
                return list(clues.values())
            return list(clues)
        return []

    def _find_next_forced_cell_row_major(self) -> Optional[Tuple[int, int, str, Dict[str, Any]]]:
        n = self.grid_size
        revealed = self.get_revealed_cells()
        for r in range(n):
            for c in range(n):
                if (r, c) in revealed:
                    continue
                status, metrics = self._evaluate_cell_entailment(r, c)
                if status in ("CRIMINAL", "INNOCENT"):
                    return (r, c, status, metrics)
        return None

    def _evaluate_cell_entailment(self, row: int, col: int) -> Tuple[str, Dict[str, Any]]:
        """Trả về ('CRIMINAL' | 'INNOCENT' | 'UNKNOWN', metrics)."""
        if self.entailment_checker is not None:
            for method_name in ("check_cell", "evaluate_cell", "entails", "classify_cell"):
                fn = getattr(self.entailment_checker, method_name, None)
                if callable(fn):
                    res = self._call_with_flexible_args(fn, row, col)
                    return self._parse_entailment_output(res)

        # Fallback: kiểm tra trực tiếp 2 giả thiết qua _is_hypothesis_consistent
        clues = self.get_active_clues()
        can_be_criminal = self._is_hypothesis_consistent(clues, row, col, True)
        can_be_innocent = self._is_hypothesis_consistent(clues, row, col, False)
        if can_be_criminal and not can_be_innocent:
            return ("CRIMINAL", {})
        if can_be_innocent and not can_be_criminal:
            return ("INNOCENT", {})
        return ("UNKNOWN", {})

    def _is_hypothesis_consistent(
        self, clues: Sequence[Any], row: int, col: int, is_criminal: bool
    ) -> bool:
        """Kiểm tra clues ∧ (C_{row,col} == is_criminal) có SAT hay không."""
        if self.entailment_checker is not None:
            for method_name in ("is_consistent", "check_hypothesis", "is_hypothesis_sat"):
                fn = getattr(self.entailment_checker, method_name, None)
                if callable(fn):
                    return bool(fn(clues, row, col, is_criminal))

            # Tận dụng EntailmentChecker thật trên tập con clues:
            # Nếu tập con clues đã ép buộc (row, col) mang nhãn ngược lại -> giả thiết hiện tại là UNSAT.
            try:
                PublicKB = getattr(importlib.import_module("src" + ".core.public_kb"), "PublicKB")

                temp_kb = PublicKB()
                for c in clues:
                    if hasattr(temp_kb, "add_clue"):
                        temp_kb.add_clue(c)
                for method_name in ("check_cell", "evaluate_cell", "entails", "classify_cell"):
                    fn = getattr(self.entailment_checker, method_name, None)
                    if callable(fn):
                        raw_res = fn(temp_kb, row, col)
                        status_str, _ = self._parse_entailment_output(raw_res)
                        if status_str in ("CONTRADICTION", "UNSAT", "INCONSISTENT"):
                            return False
                        if status_str == "CRIMINAL" and not is_criminal:
                            return False
                        if status_str == "INNOCENT" and is_criminal:
                            return False
                        return True
            except Exception:
                pass

        # Fallback cuối cùng qua CNFEncoder + DPLL nếu không có EntailmentChecker
        try:
            VariableMap = getattr(importlib.import_module("src" + ".core.variable_map"), "VariableMap")
            CNFEncoder = getattr(importlib.import_module("src" + ".encoder.cnf_encoder"), "CNFEncoder")
            dpll_mod = importlib.import_module("src" + ".solvers.dpll")

            vmap = VariableMap(self.grid_size)
            encoder = CNFEncoder(vmap)
            clauses: List[List[int]] = []
            for clue in clues:
                encoded = encoder.encode_clue(clue) if hasattr(encoder, "encode_clue") else encoder.encode([clue])
                clauses.extend(encoded)

            for (r, c), lbl in self.get_revealed_cells().items():
                var = vmap.get_var(r, c) if hasattr(vmap, "get_var") else r * self.grid_size + c + 1
                clauses.append([var if lbl == "CRIMINAL" else -var])

            target_var = vmap.get_var(row, col) if hasattr(vmap, "get_var") else row * self.grid_size + col + 1
            clauses.append([target_var if is_criminal else -target_var])

            solver_cls = getattr(dpll_mod, "DPLLSolver", None) or getattr(dpll_mod, "DPLL", None)
            if solver_cls is not None:
                res = solver_cls().solve(clauses)
            elif hasattr(dpll_mod, "solve"):
                res = dpll_mod.solve(clauses)
            else:
                return True

            if isinstance(res, tuple):
                return bool(res[0])
            if hasattr(res, "satisfiable"):
                return bool(res.satisfiable)
            return bool(res)
        except Exception:
            return True

    def _apply_reveal(self, row: int, col: int, is_criminal: bool) -> List[Any]:
        prev_ids = {self._get_clue_id(c, i) for i, c in enumerate(self.get_active_clues())}
        label = "CRIMINAL" if is_criminal else "INNOCENT"

        if self.engine is not None:
            for method_name in ("reveal", "reveal_cell", "flip_cell", "make_move"):
                fn = getattr(self.engine, method_name, None)
                if callable(fn):
                    try:
                        out = fn(row, col, is_criminal)
                    except TypeError:
                        out = fn(row, col)
                    if self.public_kb is not None and out is not None and hasattr(self.public_kb, "add_clue"):
                        if isinstance(out, list):
                            for c in out:
                                self.public_kb.add_clue(c)
                        elif hasattr(out, "type") or isinstance(out, dict):
                            self.public_kb.add_clue(out)
                    break

        self.step_count += 1
        self._sync_highlighter_with_kb()

        new_clues = [
            c for i, c in enumerate(self.get_active_clues()) if self._get_clue_id(c, i) not in prev_ids
        ]
        if self.on_card_flipped is not None:
            self.on_card_flipped(row, col, label)
        self._emit_state()
        return new_clues

    def _sync_highlighter_with_kb(self) -> None:
        clues = self.get_active_clues()
        self.highlighter.set_clues(clues)
        self.highlighter.update_saturated_clues(self.get_revealed_cells().keys())

    def _parse_puzzle_object(self, raw_json: Dict[str, Any], path: Path) -> Any:
        try:
            loader_mod = importlib.import_module("src" + ".core.puzzle_loader")

            if hasattr(loader_mod, "load_puzzle"):
                return loader_mod.load_puzzle(str(path))
            if hasattr(loader_mod, "PuzzleLoader"):
                loader = loader_mod.PuzzleLoader
                if hasattr(loader, "load"):
                    return loader.load(str(path))
                if hasattr(loader, "load_from_file"):
                    return loader.load_from_file(str(path))
                inst = loader()
                if hasattr(inst, "load"):
                    return inst.load(str(path))
        except Exception:
            pass

        try:
            Puzzle = getattr(importlib.import_module("src" + ".core.puzzle"), "Puzzle")

            if hasattr(Puzzle, "from_dict"):
                return Puzzle.from_dict(raw_json)
        except Exception:
            pass
        return raw_json

    def _validate_loaded_puzzle(self, raw_data: Any) -> None:
        if self._validator is not None and hasattr(self._validator, "validate"):
            self._validator.validate(raw_data)
            return
        if not isinstance(raw_data, dict):
            return
        try:
            PuzzleValidator = getattr(importlib.import_module("src" + ".core.puzzle_validator"), "PuzzleValidator")

            validator = PuzzleValidator()
            if hasattr(validator, "validate"):
                res = validator.validate(raw_data)
                if isinstance(res, tuple) and len(res) >= 1 and res[0] is False:
                    raise ValueError(f"Puzzle không hợp lệ: {res[1:]}")
        except ImportError:
            pass

    def _build_engine(self, puzzle: Any) -> Any:
        if self._engine_factory is not None:
            return self._engine_factory(puzzle)
        GameEngine = getattr(importlib.import_module("src" + ".core.game_engine"), "GameEngine")

        return GameEngine(self.puzzle_path if self.puzzle_path is not None else puzzle)

    def _build_public_kb(self, puzzle: Any, engine: Any) -> Any:
        if self._kb_factory is not None:
            return self._kb_factory(puzzle)
        if hasattr(engine, "public_kb") and getattr(engine, "public_kb") is not None:
            return getattr(engine, "public_kb")
        if hasattr(engine, "get_public_snapshot"):
            return engine.get_public_snapshot()
        PublicKB = getattr(importlib.import_module("src" + ".core.public_kb"), "PublicKB")

        try:
            return PublicKB(puzzle)
        except TypeError:
            kb = PublicKB()
            initial = getattr(puzzle, "initial_clues", None) or (
                puzzle.get("initial_clues", []) if isinstance(puzzle, dict) else []
            )
            for c in initial:
                if hasattr(kb, "add_clue"):
                    kb.add_clue(c)
            return kb

    def _build_entailment_checker(self, puzzle: Any, public_kb: Any) -> Any:
        if self._entailment_factory is not None:
            return self._entailment_factory(puzzle, public_kb)
        try:
            EntailmentChecker = getattr(importlib.import_module("src" + ".agent.entailment"), "EntailmentChecker")

            try:
                return EntailmentChecker(puzzle, public_kb)
            except TypeError:
                return EntailmentChecker(public_kb)
        except Exception:
            return None

    def _get_ground_truth_label(self, row: int, col: int) -> Optional[str]:
        if self.engine is not None and hasattr(self.engine, "get_answer"):
            ans = self.engine.get_answer(row, col)
            return "CRIMINAL" if ans in (True, "CRIMINAL") else "INNOCENT"
        return None

    @staticmethod
    def _get_clue_id(clue: Any, fallback_idx: int) -> str:
        if isinstance(clue, dict):
            return str(clue.get("id", clue.get("clue_id", f"clue_{fallback_idx}")))
        return str(getattr(clue, "id", getattr(clue, "clue_id", f"clue_{fallback_idx}")))

    def _call_with_flexible_args(self, fn: Callable[..., Any], row: int, col: int) -> Any:
        try:
            return fn(self.public_kb, row, col)
        except TypeError:
            try:
                return fn(row, col)
            except TypeError:
                return fn((row, col))

    @staticmethod
    def _parse_entailment_output(res: Any) -> Tuple[str, Dict[str, Any]]:
        if isinstance(res, tuple) and len(res) == 2:
            status, metrics = res
            status_str = status.value if hasattr(status, "value") else str(status)
            return (
                status_str.upper(),
                metrics if isinstance(metrics, dict) else {},
            )
        if isinstance(res, str):
            return (res.upper(), {})
        if hasattr(res, "status"):
            status_val = getattr(res, "status")
            status_str = status_val.value if hasattr(status_val, "value") else str(status_val)
            metrics = getattr(res, "metrics", {}) or {}
            return (status_str.upper(), metrics if isinstance(metrics, dict) else {})
        if isinstance(res, dict):
            status_str = str(res.get("status", "UNKNOWN")).upper()
            return (status_str, res.get("metrics", {}))
        return ("UNKNOWN", {})

    def _emit_state(self) -> None:
        if self.on_state_changed is not None:
            self.on_state_changed()

    def _emit_highlight(self) -> None:
        if self.on_highlight_changed is not None:
            self.on_highlight_changed(self.highlighter.state)

    def _emit_status(self, message: str) -> None:
        if self.on_status_message is not None:
            self.on_status_message(message)