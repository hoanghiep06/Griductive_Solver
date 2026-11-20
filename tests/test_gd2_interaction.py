from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.gui.clue_highlighter import ClueHighlighter, HighlightRole
from src.gui.controller import (
    AutoSolveStatus,
    ErrorDialogPayload,
    GuessErrorType,
    InteractionController,
)


@dataclass
class FakeClue:
    id: str
    type: str
    text: str
    source_cell: Optional[Tuple[int, int]] = None
    target_cells: Tuple[Tuple[int, int], ...] = ()
    region_a: Tuple[Tuple[int, int], ...] = ()
    region_b: Tuple[Tuple[int, int], ...] = ()


class FakeEngine:
    """Mock GameEngine chuẩn để test InteractionController & ClueHighlighter độc lập."""

    def __init__(self, size: int, ground_truth: Dict[Tuple[int, int], bool], reveal_clues: Dict[Tuple[int, int], FakeClue]) -> None:
        self.size = size
        self._truth = dict(ground_truth)
        self._reveal_clues = dict(reveal_clues)
        self._revealed: Dict[Tuple[int, int], bool] = {}
        self.public_kb = FakePublicKB()

    def is_revealed(self, row: int, col: int) -> bool:
        return (row, col) in self._revealed

    def get_revealed_cells(self) -> Dict[Tuple[int, int], bool]:
        return dict(self._revealed)

    def is_solved(self) -> bool:
        return len(self._revealed) == self.size * self.size

    def reveal(self, row: int, col: int, is_criminal: bool) -> Optional[FakeClue]:
        assert self._truth[(row, col)] == is_criminal
        self._revealed[(row, col)] = is_criminal
        new_clue = self._reveal_clues.get((row, col))
        if new_clue is not None:
            self.public_kb.add_clue(new_clue)
        return new_clue


class FakePublicKB:
    def __init__(self, initial: Optional[List[FakeClue]] = None) -> None:
        self.clues: List[FakeClue] = list(initial or [])

    def add_clue(self, clue: FakeClue) -> None:
        if all(c.id != clue.id for c in self.clues):
            self.clues.append(clue)

    def get_clues(self) -> List[FakeClue]:
        return list(self.clues)


class FakeEntailmentChecker:
    """
    Mô phỏng EntailmentChecker + kiểm tra tính nhất quán giả thiết (is_consistent):
    - C1: (0, 0) bắt buộc là CRIMINAL.
    - C2 (mở ra sau khi lật (0, 0)): (0, 1) bắt buộc là INNOCENT.
    - (1, 0) và (1, 1) chưa bị ép buộc (UNKNOWN) cho tới khi có thêm dữ kiện.
    """

    def check_cell(self, kb: FakePublicKB, row: int, col: int) -> Tuple[str, Dict[str, Any]]:
        clue_ids = {c.id for c in kb.get_clues()}
        if (row, col) == (0, 0) and "C1" in clue_ids:
            return ("CRIMINAL", {"decisions": 1, "propagations": 3})
        if (row, col) == (0, 1) and "C2" in clue_ids:
            return ("INNOCENT", {"decisions": 2, "propagations": 5})
        if (row, col) == (1, 0) and "C2" in clue_ids:
            return ("CRIMINAL", {"decisions": 1, "propagations": 4})
        if (row, col) == (1, 1) and "C2" in clue_ids:
            return ("INNOCENT", {"decisions": 1, "propagations": 2})
        return ("UNKNOWN", {"decisions": 4, "propagations": 8})

    def is_consistent(self, clues: List[FakeClue], row: int, col: int, is_criminal: bool) -> bool:
        clue_ids = {c.id for c in clues}
        # C1 khẳng định (0,0) là CRIMINAL -> giả thiết (0,0)==INNOCENT là mâu thuẫn (UNSAT)
        if (row, col) == (0, 0) and "C1" in clue_ids and not is_criminal:
            return False
        # C2 khẳng định (0,1) là INNOCENT -> giả thiết (0,1)==CRIMINAL là mâu thuẫn (UNSAT)
        if (row, col) == (0, 1) and "C2" in clue_ids and is_criminal:
            return False
        return True


def _build_test_controller() -> InteractionController:
    c1 = FakeClue(id="C1", type="FACT", text="(1,1) là tội phạm", source_cell=(0, 1), target_cells=((0, 0),))
    c2 = FakeClue(
        id="C2",
        type="COUNT_COMPARE",
        text="Số tội phạm vùng A > vùng B",
        source_cell=(0, 0),
        region_a=((1, 0),),
        region_b=((0, 1), (1, 1)),
    )
    truth = {(0, 0): True, (0, 1): False, (1, 0): True, (1, 1): False}

    def make_engine(_puzzle: Any) -> FakeEngine:
        eng = FakeEngine(size=2, ground_truth=truth, reveal_clues={(0, 0): c2})
        eng.public_kb.add_clue(c1)
        return eng

    ctrl = InteractionController(
        engine_factory=make_engine,
        entailment_factory=lambda _p, _kb: FakeEntailmentChecker(),
    )
    ctrl.load_puzzle({"size": 2}, validate=False)
    return ctrl


# ----------------------------------------------------------------------
# 1. TEST CLUE HIGHLIGHTER (2 CHIỀU, ĐA VAI TRÒ & BÃO HÒA)
# ----------------------------------------------------------------------


def test_clue_highlighter_roles_and_toggle() -> None:
    c1 = FakeClue(id="C1", type="FACT", text="Fact", source_cell=(0, 1), target_cells=((0, 0),))
    c2 = FakeClue(
        id="C2",
        type="COUNT_COMPARE",
        text="Compare",
        source_cell=(0, 0),
        region_a=((1, 0),),
        region_b=((1, 1),),
    )
    hl = ClueHighlighter([c1, c2])

    st = hl.select_clue("C1")
    assert st.cell_highlights[(0, 1)].role == HighlightRole.SOURCE
    assert st.cell_highlights[(0, 0)].role == HighlightRole.TARGET

    # Bấm lại chính manh mối đó -> tự động tắt highlight (toggle)
    st_toggled = hl.select_clue("C1")
    assert st_toggled.mode == "NONE"
    assert st_toggled.cell_highlights == {}

    # COUNT_COMPARE phân tách rõ SOURCE, REGION_A, REGION_B
    st_cmp = hl.select_clue("C2")
    assert st_cmp.cell_highlights[(0, 0)].role == HighlightRole.SOURCE
    assert st_cmp.cell_highlights[(1, 0)].role == HighlightRole.REGION_A
    assert st_cmp.cell_highlights[(1, 1)].role == HighlightRole.REGION_B


def test_clue_highlighter_reverse_inspect_and_saturation() -> None:
    c1 = FakeClue(id="C1", type="SAME", text="Same", target_cells=((0, 0), (0, 1)))
    c2 = FakeClue(id="C2", type="PARITY", text="Parity", target_cells=((0, 1), (1, 1)))
    hl = ClueHighlighter([c1, c2])

    # Inspect ngược từ ô (0, 1) -> tìm ra cả C1 và C2
    st = hl.inspect_cell(0, 1)
    assert st.related_clue_ids == ["C1", "C2"]

    # Khi (0, 0) và (0, 1) đã mở -> C1 bão hòa, C2 chưa bão hòa
    saturated = hl.update_saturated_clues([(0, 0), (0, 1)])
    assert saturated == {"C1"}


# ----------------------------------------------------------------------
# 2. TEST PHÂN BIỆT LỖI ĐOÁN SAI: CONTRADICTED vs NOT_PROVABLE
# ----------------------------------------------------------------------


def test_guess_contradicted_vs_not_provable() -> None:
    ctrl = _build_test_controller()
    captured_dialogs: List[ErrorDialogPayload] = []
    ctrl.on_error_dialog = captured_dialogs.append

    # 1. Đoán sai (0, 0) là INNOCENT trong khi C1 ép là CRIMINAL -> CONTRADICTED
    out_contra = ctrl.submit_guess(0, 0, guessed_is_criminal=False)
    assert not out_contra.accepted
    assert out_contra.error_dialog is not None
    assert out_contra.error_dialog.error_type == GuessErrorType.CONTRADICTED
    assert "C1" in out_contra.error_dialog.related_clue_ids
    assert ctrl.highlighter.state.mode == "CONTRADICTION"

    # 2. Đoán ô (1, 0) khi chưa mở C2 -> dù đoán trúng đáp án ẩn (True), vẫn bị chặn vì NOT_PROVABLE
    out_unprovable = ctrl.submit_guess(1, 0, guessed_is_criminal=True)
    assert not out_unprovable.accepted
    assert out_unprovable.error_dialog is not None
    assert out_unprovable.error_dialog.error_type == GuessErrorType.NOT_PROVABLE
    assert ctrl.mistake_count == 2
    assert len(captured_dialogs) == 2

    # 3. Đoán đúng ô bị ép buộc (0, 0) = CRIMINAL -> chấp nhận, mở thêm C2 vào KB_1
    out_ok = ctrl.submit_guess(0, 0, guessed_is_criminal=True)
    assert out_ok.accepted
    assert out_ok.assigned_label == "CRIMINAL"
    assert any(c.id == "C2" for c in out_ok.newly_revealed_clues)


# ----------------------------------------------------------------------
# 3. TEST 4 NÚT CHỨC NĂNG: HINT (2 TẦNG), RESTART, AUTO SOLVE
# ----------------------------------------------------------------------


def test_progressive_hint_and_restart() -> None:
    ctrl = _build_test_controller()

    # Hint lần 1 -> Tier 1 (Nudge): highlight (0, 0) và manh mối hỗ trợ C1, chưa lộ nhãn
    h1 = ctrl.hint()
    assert h1.available
    assert h1.tier == 1
    assert (h1.row, h1.col) == (0, 0)
    assert h1.inferred_label is None
    assert h1.supporting_clue_ids == ["C1"]

    # Hint lần 2 trên cùng ô -> Tier 2 (Reveal): công bố CRIMINAL + metrics
    h2 = ctrl.hint()
    assert h2.available
    assert h2.tier == 2
    assert h2.inferred_label == "CRIMINAL"
    assert h2.metrics["decisions"] == 1

    # Lật (0, 0) rồi gọi Restart -> reset toàn bộ về KB_0
    ctrl.submit_guess(0, 0, True)
    assert ctrl.step_count == 1
    ctrl.restart()
    assert ctrl.step_count == 0
    assert ctrl.mistake_count == 0
    assert ctrl.get_revealed_cells() == {}


def test_auto_solve_solves_board_without_guessing() -> None:
    ctrl = _build_test_controller()
    steps = ctrl.run_auto_solve()
    assert ctrl.is_solved()
    assert steps[-1].status == AutoSolveStatus.SOLVED
    assert ctrl.get_revealed_cells() == {
        (0, 0): "CRIMINAL",
        (0, 1): "INNOCENT",
        (1, 0): "CRIMINAL",
        (1, 1): "INNOCENT",
    }


def test_load_real_manifest_and_3x3_puzzle() -> None:
    from pathlib import Path

    sample_path = Path("puzzles/3x3_01.json")
    if not sample_path.exists():
        pytest.skip("Không tìm thấy puzzles/3x3_01.json")

    manifest_items = InteractionController.list_manifest_puzzles("puzzles/manifest.json")
    assert len(manifest_items) >= 15

    ctrl = InteractionController()
    ctrl.load_puzzle(sample_path)
    assert ctrl.grid_size == 3
    assert len(ctrl.get_active_clues()) > 0