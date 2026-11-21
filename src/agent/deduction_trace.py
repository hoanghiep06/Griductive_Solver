"""Module ghi vết suy luận chi tiết cho Logic Agent .

Mỗi bước suy luận được ghi lại dưới dạng một ``DeductionStep`` bất biến.
``DeductionTrace`` thu thập toàn bộ vết suy luận của một ván chơi và cung
cấp các tiện ích xuất log / báo cáo.

Thiết kế:
  - Hoàn toàn tách biệt khỏi PublicKB, GameEngine và Encoder — trace chỉ
    nhận dữ liệu đã được chuẩn bị sẵn từ LogicAgent.
  - Mỗi ``DeductionStep`` ghi lại: nhân vật được lật, kết luận, phiên bản KB
    tại thời điểm suy luận, chỉ số SAT, tập chứng cứ (manh mối và các ô đã
    chứng minh), manh mối mới được mở, thời gian thực của cả bước và chuỗi
    giải thích ngắn gọn bằng ngôn ngữ tự nhiên.
  - ``DeductionTrace`` có trạng thái kết thúc (``TraceStatus``): đã giải xong,
    bế tắc, hay KB mâu thuẫn; có thể ``clear()`` khi Restart và nạp lại từ JSON
    bằng ``from_dict`` / ``load_json``.
  - ``DeductionTrace`` không lưu trạng thái ẩn của puzzle (không có
    hidden_solution, chỉ có public information).
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Trạng thái kết thúc của vết suy luận
# ---------------------------------------------------------------------------

class TraceStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"     # Đang suy luận (chưa kết thúc)
    SOLVED = "SOLVED"               # Mọi ô đã được chứng minh
    STUCK = "STUCK"                 # Còn ô chưa giải nhưng không còn ô nào bị ép buộc
    INCONSISTENT = "INCONSISTENT"   # KB mâu thuẫn


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
    def from_dict(cls, data: Mapping[str, Any]) -> "SATMetrics":
        """Dựng lại từ dict do ``to_dict`` tạo ra."""
        return cls(
            sat_calls=int(data.get("sat_calls", 0)),
            decisions=int(data.get("decisions", 0)),
            propagations=int(data.get("propagations", 0)),
            backtracks=int(data.get("backtracks", 0)),
            runtime_ms=float(data.get("runtime_ms", 0.0)),
        )

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
        step_index:             Thứ tự bước (bắt đầu từ 1) trong toàn ván.
        character_id:           ID nhân vật được lật/kết luận trong bước này.
        verdict:                'CRIMINAL' hoặc 'INNOCENT'.
        kb_version:             Phiên bản KB *tại thời điểm suy luận* (trước khi cập nhật).
        clue_ids:               ID manh mối làm chứng cứ (tối tiểu nếu minimal_evidence=True).
        explanation:            Chuỗi mô tả ngắn gọn tại sao kết luận này được rút ra.
        metrics:                Chỉ số SAT cho bước này.
        timestamp:              Thời điểm ghi nhận bước (ISO 8601).
        support_cell_ids:       Các ô đã chứng minh trước đó mà chứng cứ cần dùng.
        minimal_evidence:       True nếu clue_ids / support_cell_ids là tập tối tiểu.
        newly_revealed_clue_id: Manh mối của ô vừa lật (None nếu không có).
        elapsed_ms:             Thời gian thực của cả bước (mã hóa + SAT + tìm chứng cứ + lật).
    """
    step_index: int
    character_id: str
    verdict: str            # 'CRIMINAL' | 'INNOCENT'
    kb_version: int
    clue_ids: tuple[str, ...]
    explanation: str
    metrics: SATMetrics
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    support_cell_ids: tuple[str, ...] = ()
    minimal_evidence: bool = False
    newly_revealed_clue_id: str | None = None
    elapsed_ms: float = 0.0

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
        if isinstance(self.elapsed_ms, bool) or not isinstance(self.elapsed_ms, (int, float)) or self.elapsed_ms < 0:
            raise ValueError("elapsed_ms phải là số không âm")
        # Đảm bảo kiểu
        object.__setattr__(self, "clue_ids", tuple(self.clue_ids))
        object.__setattr__(self, "support_cell_ids", tuple(self.support_cell_ids))
        object.__setattr__(self, "minimal_evidence", bool(self.minimal_evidence))
        object.__setattr__(self, "elapsed_ms", float(self.elapsed_ms))

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "character_id": self.character_id,
            "verdict": self.verdict,
            "kb_version": self.kb_version,
            "clue_ids": list(self.clue_ids),
            "support_cell_ids": list(self.support_cell_ids),
            "minimal_evidence": self.minimal_evidence,
            "newly_revealed_clue_id": self.newly_revealed_clue_id,
            "explanation": self.explanation,
            "metrics": self.metrics.to_dict(),
            "elapsed_ms": round(self.elapsed_ms, 4),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeductionStep":
        """Dựng lại từ dict do ``to_dict`` tạo ra (chấp nhận file cũ thiếu trường mới)."""
        kwargs: dict[str, Any] = {}
        if data.get("timestamp"):
            kwargs["timestamp"] = data["timestamp"]
        return cls(
            step_index=int(data["step_index"]),
            character_id=data["character_id"],
            verdict=data["verdict"],
            kb_version=int(data["kb_version"]),
            clue_ids=tuple(data.get("clue_ids", ())),
            explanation=data.get("explanation", ""),
            metrics=SATMetrics.from_dict(data.get("metrics", {})),
            support_cell_ids=tuple(data.get("support_cell_ids", ())),
            minimal_evidence=bool(data.get("minimal_evidence", False)),
            newly_revealed_clue_id=data.get("newly_revealed_clue_id"),
            elapsed_ms=float(data.get("elapsed_ms", 0.0)),
            **kwargs,
        )

    def format_summary(self) -> str:
        """Trả về dòng tóm tắt ngắn cho stdout / UI log."""
        clues_str = ", ".join(self.clue_ids) if self.clue_ids else "(không cần manh mối)"
        cells_str = f" + ô {', '.join(self.support_cell_ids)}" if self.support_cell_ids else ""
        tag = "tối tiểu" if self.minimal_evidence else "toàn KB"
        opened = f" | Mở: {self.newly_revealed_clue_id}" if self.newly_revealed_clue_id else ""
        return (
            f"[Bước {self.step_index:>3}] {self.character_id:<20} → {self.verdict:<9} "
            f"| KB v{self.kb_version} | Chứng cứ ({tag}): {clues_str}{cells_str}{opened} | "
            f"SAT calls={self.metrics.sat_calls}, bt={self.metrics.backtracks}, "
            f"sat={self.metrics.runtime_ms:.2f}ms, bước={self.elapsed_ms:.2f}ms"
        )


# ---------------------------------------------------------------------------
# Bộ thu thập toàn bộ vết suy luận
# ---------------------------------------------------------------------------

class DeductionTrace:
    """Thu thập và quản lý toàn bộ vết suy luận của một ván chơi.

    Sử dụng:
        trace = DeductionTrace(puzzle_id="puzzle_3x3_easy")
        trace.record(step)                       # LogicAgent gọi sau mỗi bước
        trace.mark_finished(TraceStatus.SOLVED)  # kết thúc, ghi trạng thái
        trace.print_summary()                    # In toàn bộ bảng bước
        trace.save_json("trace.json")            # Xuất JSON
        trace = DeductionTrace.load_json("trace.json")
        trace.clear()                            # Khi Restart

    Không lưu trạng thái ẩn (hidden solution), chỉ lưu public information.
    """

    def __init__(self, puzzle_id: str = "", grid_size: int = 0) -> None:
        self._puzzle_id = puzzle_id
        self._grid_size = grid_size
        self._steps: list[DeductionStep] = []
        self._start_time: str = datetime.datetime.now().isoformat()
        self._end_time: str | None = None
        self._status: TraceStatus = TraceStatus.IN_PROGRESS

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

    def mark_finished(self, status: TraceStatus | str | None = None) -> None:
        """Đánh dấu kết thúc; ghi lại timestamp và (tuỳ chọn) trạng thái kết thúc.

        Args:
            status: SOLVED / STUCK / INCONSISTENT. Nếu None, giữ trạng thái hiện tại.
        """
        if status is not None:
            self._status = TraceStatus(status)
        self._end_time = datetime.datetime.now().isoformat()

    def clear(self) -> None:
        """Xóa toàn bộ vết (dùng khi Restart / nạp ván mới); giữ puzzle_id và grid_size."""
        self._steps.clear()
        self._start_time = datetime.datetime.now().isoformat()
        self._end_time = None
        self._status = TraceStatus.IN_PROGRESS

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
    def status(self) -> TraceStatus:
        return self._status

    @property
    def is_finished(self) -> bool:
        return self._end_time is not None

    @property
    def is_solved(self) -> bool:
        return self._status is TraceStatus.SOLVED

    def total_metrics(self) -> SATMetrics:
        """Tổng hợp chỉ số SAT trên toàn bộ vết suy luận."""
        result = SATMetrics()
        for step in self._steps:
            result = result + step.metrics
        return result

    def total_elapsed_ms(self) -> float:
        """Tổng thời gian thực của mọi bước (ms)."""
        return sum(step.elapsed_ms for step in self._steps)

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
    # Xuất / nạp dữ liệu
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Chuyển toàn bộ trace sang dict Python (JSON-serializable)."""
        agg = self.total_metrics()
        return {
            "puzzle_id": self._puzzle_id,
            "grid_size": self._grid_size,
            "status": self._status.value,
            "start_time": self._start_time,
            "end_time": self._end_time,
            "step_count": self.step_count,
            "total_metrics": agg.to_dict(),
            "total_elapsed_ms": round(self.total_elapsed_ms(), 4),
            "steps": [step.to_dict() for step in self._steps],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeductionTrace":
        """Dựng lại trace từ dict do ``to_dict`` tạo ra (chấp nhận file cũ thiếu trường mới)."""
        trace = cls(
            puzzle_id=data.get("puzzle_id", ""),
            grid_size=int(data.get("grid_size", 0)),
        )
        if data.get("start_time"):
            trace._start_time = data["start_time"]
        trace._end_time = data.get("end_time")
        trace._status = TraceStatus(data.get("status", TraceStatus.IN_PROGRESS.value))
        for raw in data.get("steps", ()):
            trace.record(DeductionStep.from_dict(raw))
        return trace

    def to_json(self, indent: int = 2) -> str:
        """Xuất trace dưới dạng chuỗi JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_json(self, filepath: str) -> None:
        """Lưu trace ra file JSON."""
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def load_json(cls, filepath: str) -> "DeductionTrace":
        """Nạp trace từ file JSON do ``save_json`` tạo ra."""
        with open(filepath, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def print_summary(self, *, show_header: bool = True) -> None:
        """In bảng tóm tắt toàn bộ bước suy luận ra stdout."""
        if show_header:
            puzzle_label = self._puzzle_id or "(unknown puzzle)"
            print(f"\n{'='*80}")
            print(f"  VẾT SUY LUẬN — {puzzle_label}  |  {self.step_count} bước  |  {self._status.value}")
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
                f"sat={agg.runtime_ms:.2f}ms | thời gian thực={self.total_elapsed_ms():.2f}ms"
            )
            if self._end_time:
                print(f"  Hoàn thành lúc: {self._end_time}")
            print(f"{'='*80}\n")

    def __repr__(self) -> str:
        return (
            f"<DeductionTrace puzzle={self._puzzle_id!r} "
            f"steps={self.step_count} status={self._status.value}>"
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
    evidence_clue_ids: Sequence[str] | None = None,
    support_cell_ids: Sequence[str] = (),
    newly_revealed_clue_id: str | None = None,
    elapsed_ms: float = 0.0,
) -> DeductionStep:
    """Tạo ``DeductionStep`` từ kết quả trả về của EntailmentChecker.

    Args:
        step_index:              Thứ tự bước.
        character_id:            ID nhân vật vừa được xác định.
        verdict:                 'CRIMINAL' hoặc 'INNOCENT'.
        kb_version:              Phiên bản KB *trước* khi cập nhật.
        revealed_clues:          Các manh mối công khai đang có trong KB (Clue hoặc dict).
                                 Chỉ dùng khi ``evidence_clue_ids`` là None.
        sat_metrics_list:        Danh sách dict get_stats() từ DPLL, một dict mỗi lần gọi SAT.
        extra_note:              Ghi chú thêm vào explanation.
        evidence_clue_ids:       Tập manh mối tối tiểu do LogicAgent tính được. Nếu None,
                                 dùng toàn bộ ``revealed_clues`` (minimal_evidence=False).
        support_cell_ids:        Các ô đã chứng minh nằm trong tập chứng cứ tối tiểu.
        newly_revealed_clue_id:  Manh mối của ô vừa lật.
        elapsed_ms:              Thời gian thực của cả bước.

    Returns:
        DeductionStep bất biến sẵn sàng để trace.record().
    """
    minimal = evidence_clue_ids is not None
    clue_ids: list[str] = []
    if minimal:
        clue_ids = [str(cid) for cid in evidence_clue_ids]  # type: ignore[union-attr]
    else:
        for clue in revealed_clues:
            if hasattr(clue, "clue_id"):
                clue_ids.append(clue.clue_id)
            elif isinstance(clue, dict) and "clue_id" in clue:
                clue_ids.append(clue["clue_id"])
    cell_ids = [str(c) for c in support_cell_ids] if minimal else []

    # Tổng hợp metrics từ nhiều lần gọi SAT
    agg = SATMetrics()
    for stats in sat_metrics_list:
        agg = agg + SATMetrics.from_solver_stats(stats, sat_calls=1)

    # Tạo explanation
    verdict_label = "phạm nhân (CRIMINAL)" if verdict == "CRIMINAL" else "vô tội (INNOCENT)"
    clues_label = ", ".join(clue_ids) if clue_ids else "không cần manh mối nào"
    if minimal:
        explanation = f"Từ {len(clue_ids)} manh mối cần thiết ({clues_label})"
        if cell_ids:
            explanation += f" cùng các ô đã chứng minh ({', '.join(cell_ids)})"
        explanation += (
            f", giả thiết ngược lại dẫn tới mâu thuẫn nên {character_id} "
            f"bắt buộc là {verdict_label}. [KB v{kb_version}]"
        )
    else:
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
        support_cell_ids=tuple(cell_ids),
        minimal_evidence=minimal,
        newly_revealed_clue_id=newly_revealed_clue_id,
        elapsed_ms=elapsed_ms,
    )