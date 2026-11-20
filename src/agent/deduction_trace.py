"""Module ghi vết suy luận chi tiết cho Logic Agent (TV5).

Mỗi bước suy luận được ghi lại dưới dạng một ``DeductionStep`` bất biến.
``DeductionTrace`` thu thập toàn bộ vết suy luận của một ván chơi và cung
cấp các tiện ích xuất log / báo cáo.

Thiết kế:
  - Hoàn toàn tách biệt khỏi PublicKB, GameEngine và Encoder — trace chỉ
    nhận dữ liệu đã được chuẩn bị sẵn từ LogicAgent.
  - Mỗi ``DeductionStep`` ghi lại: nhân vật được lật, kết luận, phiên bản KB
    tại thời điểm suy luận, chỉ số SAT tích lũy, danh sách manh mối tham chiếu
    và chuỗi giải thích ngắn gọn bằng ngôn ngữ tự nhiên.
  - ``DeductionTrace`` không lưu trạng thái ẩn của puzzle (không có
    hidden_solution, chỉ có public information).
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Kiểu dữ liệu cho một bước suy luận
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SATMetrics:
    """Chỉ số đo lường tích lũy từ các lần gọi SAT solver trong một bước suy luận."""
    sat_calls: int = 0
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime_ms: float = 0.0

    def __add__(self, other: "SATMetrics") -> "SATMetrics":
        if not isinstance(other, SATMetrics):
            return NotImplemented
        return SATMetrics(
            sat_calls=self.sat_calls + other.sat_calls,
            decisions=self.decisions + other.decisions,
            propagations=self.propagations + other.propagations,
            backtracks=self.backtracks + other.backtracks,
            runtime_ms=self.runtime_ms + other.runtime_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sat_calls": self.sat_calls,
            "decisions": self.decisions,
            "propagations": self.propagations,
            "backtracks": self.backtracks,
            "runtime_ms": round(self.runtime_ms, 4),
        }

    @classmethod
    def from_solver_stats(cls, stats: Mapping[str, float], sat_calls: int = 1) -> "SATMetrics":
        """Chuyển dict từ DPLLSolver.get_stats() sang SATMetrics."""
        return cls(
            sat_calls=sat_calls,
            decisions=int(stats.get("decisions", 0)),
            propagations=int(stats.get("propagations", 0)),
            backtracks=int(stats.get("backtracks", 0)),
            runtime_ms=float(stats.get("runtime", 0.0)) * 1000.0,
        )


@dataclass(frozen=True, slots=True)
class DeductionStep:
    """Một bước suy luận đã được chứng minh bởi SAT.

    Attributes:
        step_index:     Thứ tự bước (bắt đầu từ 1) trong toàn ván.
        character_id:   ID nhân vật được lật/kết luận trong bước này.
        verdict:        'CRIMINAL' hoặc 'INNOCENT'.
        kb_version:     Phiên bản KB *tại thời điểm suy luận* (trước khi cập nhật).
        clue_ids:       Danh sách ID manh mối đã được dùng làm bằng chứng.
        explanation:    Chuỗi mô tả ngắn gọn tại sao kết luận này được rút ra.
        metrics:        Chỉ số SAT tích lũy cho bước này.
        timestamp:      Thời điểm ghi nhận bước (ISO 8601).
    """
    step_index: int
    character_id: str
    verdict: str            # 'CRIMINAL' | 'INNOCENT'
    kb_version: int
    clue_ids: tuple[str, ...]
    explanation: str
    metrics: SATMetrics
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def __post_init__(self) -> None:
        if not isinstance(self.step_index, int) or self.step_index < 1:
            raise ValueError("step_index phải là số nguyên dương")
        if not isinstance(self.character_id, str) or not self.character_id.strip():
            raise ValueError("character_id phải là chuỗi không rỗng")
        if self.verdict not in ("CRIMINAL", "INNOCENT"):
            raise ValueError(f"verdict phải là 'CRIMINAL' hoặc 'INNOCENT', nhận được {self.verdict!r}")
        if not isinstance(self.kb_version, int) or self.kb_version < 0:
            raise ValueError("kb_version phải là số nguyên không âm")
        if not isinstance(self.metrics, SATMetrics):
            raise TypeError("metrics phải là SATMetrics")
        # Đảm bảo clue_ids là tuple
        object.__setattr__(self, "clue_ids", tuple(self.clue_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "character_id": self.character_id,
            "verdict": self.verdict,
            "kb_version": self.kb_version,
            "clue_ids": list(self.clue_ids),
            "explanation": self.explanation,
            "metrics": self.metrics.to_dict(),
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Trả về dòng tóm tắt ngắn cho stdout / UI log."""
        clues_str = ", ".join(self.clue_ids) if self.clue_ids else "(không có manh mối mới)"
        return (
            f"[Bước {self.step_index:>3}] {self.character_id:<20} → {self.verdict:<9} "
            f"| KB v{self.kb_version} | Manh mối: {clues_str} | "
            f"SAT calls={self.metrics.sat_calls}, bt={self.metrics.backtracks}, "
            f"rt={self.metrics.runtime_ms:.2f}ms"
        )


# ---------------------------------------------------------------------------
# Bộ thu thập toàn bộ vết suy luận
# ---------------------------------------------------------------------------

class DeductionTrace:
    """Thu thập và quản lý toàn bộ vết suy luận của một ván chơi.

    Sử dụng:
        trace = DeductionTrace(puzzle_id="puzzle_3x3_easy")
        trace.record(step)      # LogicAgent gọi sau mỗi bước
        trace.print_summary()   # In toàn bộ bảng bước
        trace.to_json()         # Xuất JSON để lưu hoặc GUI đọc

    Không lưu trạng thái ẩn (hidden solution), chỉ lưu public information.
    """

    def __init__(self, puzzle_id: str = "", grid_size: int = 0) -> None:
        self._puzzle_id = puzzle_id
        self._grid_size = grid_size
        self._steps: list[DeductionStep] = []
        self._start_time: str = datetime.datetime.now().isoformat()
        self._end_time: str | None = None

    # ------------------------------------------------------------------
    # Ghi nhận bước suy luận
    # ------------------------------------------------------------------

    def record(self, step: DeductionStep) -> None:
        """Thêm một bước suy luận vào vết.

        Raises:
            TypeError:  Nếu step không phải DeductionStep.
            ValueError: Nếu step_index không khớp với số bước tiếp theo.
        """
        if not isinstance(step, DeductionStep):
            raise TypeError(f"record() nhận DeductionStep, nhận được {type(step).__name__}")
        expected_index = len(self._steps) + 1
        if step.step_index != expected_index:
            raise ValueError(
                f"step_index={step.step_index} không khớp với bước tiếp theo {expected_index}"
            )
        self._steps.append(step)

    def mark_finished(self) -> None:
        """Đánh dấu kết thúc ván chơi; ghi lại timestamp."""
        self._end_time = datetime.datetime.now().isoformat()

    # ------------------------------------------------------------------
    # Tiện ích truy vấn
    # ------------------------------------------------------------------

    @property
    def steps(self) -> tuple[DeductionStep, ...]:
        return tuple(self._steps)

    @property
    def step_count(self) -> int:
        return len(self._steps)

    @property
    def puzzle_id(self) -> str:
        return self._puzzle_id

    @property
    def is_finished(self) -> bool:
        return self._end_time is not None

    def total_metrics(self) -> SATMetrics:
        """Tổng hợp chỉ số SAT trên toàn bộ vết suy luận."""
        result = SATMetrics()
        for step in self._steps:
            result = result + step.metrics
        return result

    def get_step(self, step_index: int) -> DeductionStep:
        """Lấy bước theo step_index (bắt đầu từ 1)."""
        if step_index < 1 or step_index > len(self._steps):
            raise IndexError(
                f"step_index={step_index} nằm ngoài phạm vi 1..{len(self._steps)}"
            )
        return self._steps[step_index - 1]

    def verdicts_so_far(self) -> dict[str, str]:
        """Trả về mapping {char_id: verdict} từ tất cả bước đã ghi."""
        return {step.character_id: step.verdict for step in self._steps}

    def last_step(self) -> DeductionStep | None:
        """Trả về bước cuối cùng hoặc None nếu chưa có bước nào."""
        return self._steps[-1] if self._steps else None

    # ------------------------------------------------------------------
    # Xuất dữ liệu
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Chuyển toàn bộ trace sang dict Python (JSON-serializable)."""
        agg = self.total_metrics()
        return {
            "puzzle_id": self._puzzle_id,
            "grid_size": self._grid_size,
            "start_time": self._start_time,
            "end_time": self._end_time,
            "step_count": self.step_count,
            "total_metrics": agg.to_dict(),
            "steps": [step.to_dict() for step in self._steps],
        }

    def to_json(self, indent: int = 2) -> str:
        """Xuất trace dưới dạng chuỗi JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_json(self, filepath: str) -> None:
        """Lưu trace ra file JSON."""
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    def print_summary(self, *, show_header: bool = True) -> None:
        """In bảng tóm tắt toàn bộ bước suy luận ra stdout."""
        if show_header:
            puzzle_label = self._puzzle_id or "(unknown puzzle)"
            print(f"\n{'='*80}")
            print(f"  VẾT SUY LUẬN — {puzzle_label}  |  {self.step_count} bước")
            print(f"{'='*80}")
        for step in self._steps:
            print(step.format_summary())
        if show_header:
            agg = self.total_metrics()
            print(f"{'─'*80}")
            print(
                f"  TỔNG: {self.step_count} bước | "
                f"SAT calls={agg.sat_calls} | decisions={agg.decisions} | "
                f"propagations={agg.propagations} | backtracks={agg.backtracks} | "
                f"runtime={agg.runtime_ms:.2f}ms"
            )
            if self._end_time:
                print(f"  Hoàn thành lúc: {self._end_time}")
            print(f"{'='*80}\n")

    def __repr__(self) -> str:
        return (
            f"<DeductionTrace puzzle={self._puzzle_id!r} "
            f"steps={self.step_count} finished={self.is_finished}>"
        )


# ---------------------------------------------------------------------------
# Factory helper — xây dựng DeductionStep từ kết quả của EntailmentChecker
# ---------------------------------------------------------------------------

def build_step(
    *,
    step_index: int,
    character_id: str,
    verdict: str,
    kb_version: int,
    revealed_clues: Sequence[Any],
    sat_metrics_list: Sequence[Mapping[str, float]],
    extra_note: str = "",
) -> DeductionStep:
    """Tạo ``DeductionStep`` từ kết quả trả về của EntailmentChecker.

    Args:
        step_index:         Thứ tự bước.
        character_id:       ID nhân vật vừa được xác định.
        verdict:            'CRIMINAL' hoặc 'INNOCENT'.
        kb_version:         Phiên bản KB *trước* khi cập nhật.
        revealed_clues:     Các manh mối công khai đang có trong KB (Clue hoặc dict).
        sat_metrics_list:   Danh sách dict get_stats() từ DPLL, một dict mỗi lần gọi SAT.
        extra_note:         Ghi chú thêm vào explanation.

    Returns:
        DeductionStep bất biến sẵn sàng để trace.record().
    """
    # Thu thập clue_ids từ danh sách manh mối
    clue_ids: list[str] = []
    for clue in revealed_clues:
        if hasattr(clue, "clue_id"):
            clue_ids.append(clue.clue_id)
        elif isinstance(clue, dict) and "clue_id" in clue:
            clue_ids.append(clue["clue_id"])

    # Tổng hợp metrics từ nhiều lần gọi SAT
    agg = SATMetrics()
    for stats in sat_metrics_list:
        agg = agg + SATMetrics.from_solver_stats(stats, sat_calls=1)

    # Tạo explanation
    verdict_label = "phạm nhân (CRIMINAL)" if verdict == "CRIMINAL" else "vô tội (INNOCENT)"
    clues_label = ", ".join(clue_ids) if clue_ids else "các manh mối đã mở"
    explanation = (
        f"KB (v{kb_version}) với {len(clue_ids)} manh mối bắt buộc "
        f"{character_id} là {verdict_label}. "
        f"Dựa trên: {clues_label}."
    )
    if extra_note:
        explanation += f" {extra_note}"

    return DeductionStep(
        step_index=step_index,
        character_id=character_id,
        verdict=verdict,
        kb_version=kb_version,
        clue_ids=tuple(clue_ids),
        explanation=explanation,
        metrics=agg,
    )
