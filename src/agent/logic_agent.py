"""Vòng lặp suy luận No-Guess của Logic Agent.

Thuật toán No-Guess Deduction Loop:
  Lặp cho đến khi không còn nhân vật nào có thể suy luận được:
    1. Lấy snapshot KB hiện tại (phiên bản + manh mối đã mở + phán quyết đã biết).
    2. ``find_next_forced`` (không đổi trạng thái): mã hóa KB, duyệt ô chưa giải
       theo thứ tự row-major, tìm ô *bị ép buộc đầu tiên* và tập chứng cứ tối tiểu.
       Đây cũng chính là hàm GUI dùng (xem ``forced_move.analyze_public_kb``).
    3. Nếu tìm thấy:
       a. Chuyển ClassificationResult → EntailmentResult.
       b. Gọi GameEngine.submit_verdict() để xác nhận và nhận Clue mới.
       c. Ghi vết vào DeductionTrace (chứng cứ, manh mối mới, thời gian).
       d. Tiếp tục vòng lặp (KB đã được cập nhật tự động qua GameEngine).
    4. Nếu không tìm thấy → kết thúc vòng lặp và ghi trạng thái SOLVED hoặc STUCK.

API:
  - find_next_forced(): chỉ PHÂN TÍCH, không lật thẻ, không ghi trace. Dùng cho Gợi ý.
  - step() / hint_step(): phân tích rồi lật ĐÚNG MỘT ô và ghi trace.
  - iter_steps(): generator, mỗi next() chạy đúng một step() (QTimer / CLI tự nghỉ giữa các bước).
  - auto_solve(): chạy liên tục (CLI / benchmark).

Thiết kế:
  - Không nhìn vào hidden solution; chỉ dùng PublicKBSnapshot.
  - Thứ tự row-major lấy từ GameEngine.get_unsolved_characters().
  - Encoder/checker được inject là đối tượng của riêng agent (không thread-safe);
    GUI không dùng LogicAgent mà tự tạo encoder/checker mới cho mỗi lần phân tích.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Iterator

from src.agent.deduction_trace import (
    DeductionStep,
    DeductionTrace,
    TraceStatus,
    build_step,
)
from src.agent.entailment import EntailmentChecker
from src.agent.forced_move import StepAnalysis, analyze_public_kb
from src.core.game_engine import GameEngine, VerdictResponse
from src.encoder.cnf_encoder import CNFEncoder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lỗi đặc thù của Logic Agent
# ---------------------------------------------------------------------------

class LogicAgentError(RuntimeError):
    """Lỗi không phục hồi trong quá trình suy luận (ví dụ: KB mâu thuẫn)."""


class StaleProofError(LogicAgentError):
    """GameEngine từ chối bằng chứng vì KB đã thay đổi kể từ khi suy luận."""


# ---------------------------------------------------------------------------
# Logic Agent
# ---------------------------------------------------------------------------

class LogicAgent:
    """Tác tử suy luận logic không đoán mò cho trò chơi Griductive.

    Args:
        engine:     Đối tượng GameEngine đang chạy ván chơi hiện tại.
        encoder:    CNFEncoder đã được khởi tạo với var_map của engine.
        checker:    EntailmentChecker được inject với DPLL solver.
        trace:      DeductionTrace để ghi vết (nếu None sẽ tự tạo mới).
        on_step:    Callback tuỳ chọn được gọi sau mỗi bước thành công.
                    Nhận (DeductionStep, PublicKBSnapshot) làm đối số.
        solver:     Solver có solve(cnf) -> bool dùng để tính chứng cứ tối tiểu.
                    Nếu None, thử lấy từ checker; nếu vẫn không có thì chứng cứ
                    của mỗi bước là toàn bộ KB (minimal_evidence=False).
    """

    def __init__(
        self,
        engine: GameEngine,
        encoder: CNFEncoder,
        checker: EntailmentChecker,
        trace: DeductionTrace | None = None,
        on_step: Callable[[DeductionStep, Any], None] | None = None,
        solver: Any = None,
    ) -> None:
        if not isinstance(engine, GameEngine):
            raise TypeError("engine phải là GameEngine")
        if not isinstance(encoder, CNFEncoder):
            raise TypeError("encoder phải là CNFEncoder")
        if not isinstance(checker, EntailmentChecker):
            raise TypeError("checker phải là EntailmentChecker")

        self._engine = engine
        self._encoder = encoder
        self._checker = checker
        self._trace = trace or DeductionTrace(
            puzzle_id=engine.puzzle_id,
            grid_size=engine.grid_size,
        )
        self._on_step = on_step
        if solver is None:
            solver = getattr(checker, "_solver", None) or getattr(checker, "solver", None)
        self._solver = solver if hasattr(solver, "solve") else None

    # ------------------------------------------------------------------
    # API công khai
    # ------------------------------------------------------------------

    @property
    def trace(self) -> DeductionTrace:
        """Truy cập vết suy luận đã tích lũy."""
        return self._trace

    def reset_trace(self) -> None:
        """Xóa vết suy luận. Gọi sau ``engine.restart()`` để vết khớp với ván mới."""
        self._trace.clear()

    def find_next_forced(self) -> StepAnalysis:
        """Tìm ô bị ép buộc đầu tiên (row-major) mà KHÔNG đổi trạng thái game.

        Không gọi ``submit_verdict``, không lật thẻ, không ghi trace. Phù hợp cho
        Gợi ý: kết quả cho biết ô nào, manh mối nào liên quan, nhưng caller tự
        quyết định có nêu kết luận hay không.

        Returns:
            StepAnalysis; ``cell_id is None`` nếu không còn ô nào bị ép buộc,
            ``inconsistent=True`` nếu KB mâu thuẫn.
        """
        return self._analyze(self._engine.get_public_snapshot())

    def step(self) -> DeductionStep | None:
        """Phân tích rồi lật ĐÚNG MỘT ô bị ép buộc và ghi vào trace.

        Returns:
            DeductionStep nếu thành công, None nếu không còn bước nào.

        Raises:
            LogicAgentError: Nếu KB mâu thuẫn hoặc GameEngine từ chối verdict.
        """
        return self._run_one_step()

    def hint_step(self) -> DeductionStep | None:
        """Tên cũ của :meth:`step`, giữ lại để không làm hỏng code gọi hiện có.

        Lưu ý: hàm này LẬT Ô THẬT. Nếu chỉ cần gợi ý không đổi trạng thái, dùng
        :meth:`find_next_forced`.
        """
        return self._run_one_step()

    def iter_steps(self, max_steps: int | None = None) -> Iterator[DeductionStep]:
        """Sinh từng bước suy luận một (generator).

        Mỗi lần next() chỉ chạy ĐÚNG một bước: chọn ô bị ép buộc đầu tiên
        (row-major), lật bài, cập nhật KB. Caller tự quyết định nghỉ bao lâu
        giữa hai bước (ví dụ QTimer trong GUI).

        Khi generator chạy hết, vết được đánh dấu SOLVED (đã giải xong) hoặc
        STUCK (còn ô chưa giải nhưng không còn bước ép buộc). Nếu dừng vì
        ``max_steps`` mà ván chưa xong thì vết vẫn ở trạng thái IN_PROGRESS.

        Args:
            max_steps: Số bước tối đa (None = không giới hạn).

        Yields:
            DeductionStep của từng bước thành công.
        """
        done = 0
        exhausted = False
        while max_steps is None or done < max_steps:
            step = self._run_one_step()
            if step is None:
                exhausted = True
                break
            done += 1
            yield step
        if exhausted or self._engine.is_solved():
            status = TraceStatus.SOLVED if self._engine.is_solved() else TraceStatus.STUCK
            self._trace.mark_finished(status)

    def auto_solve(self, max_steps: int | None = None) -> int:
        """Chạy vòng lặp suy luận liên tục cho đến khi không còn bước nào.

        Returns:
            Số bước suy luận thành công đã thực hiện.

        Raises:
            LogicAgentError: Nếu KB mâu thuẫn hoặc GameEngine từ chối verdict.
        """
        return sum(1 for _ in self.iter_steps(max_steps))

    # ------------------------------------------------------------------
    # Nội bộ
    # ------------------------------------------------------------------

    def _analyze(self, snapshot: Any) -> StepAnalysis:
        """Phân tích trên một snapshot cụ thể (đường suy luận dùng chung với GUI)."""
        unsolved = self._engine.get_unsolved_characters()  # đã row-major
        if not unsolved:
            return StepAnalysis(snapshot.version, None, None)
        return analyze_public_kb(
            snapshot,
            unsolved,
            self._encoder,
            self._checker,
            solver=self._solver,
        )

    def _run_one_step(self) -> DeductionStep | None:
        """Tìm và thực hiện bước suy luận tiếp theo.

        Returns:
            DeductionStep nếu thành công, None nếu không có bước nào.
        """
        t_start = time.perf_counter()

        while True:
            snapshot = self._engine.get_public_snapshot()
            analysis = self._analyze(snapshot)

            if analysis.inconsistent:
                self._trace.mark_finished(TraceStatus.INCONSISTENT)
                raise LogicAgentError(
                    f"KB mâu thuẫn (INCONSISTENT) tại KB version={snapshot.version}. "
                    "Puzzle có thể bị lỗi hoặc có manh mối xung đột."
                )
            if not analysis.is_forced:
                return None  # Đã giải hết, hoặc KB chưa đủ ràng buộc

            classification = analysis.classification
            char_id = analysis.cell_id
            assert classification is not None and char_id is not None
            is_criminal = analysis.is_criminal
            verdict_str = "CRIMINAL" if is_criminal else "INNOCENT"

            # Chuyển ClassificationResult → EntailmentResult rồi gửi lên GameEngine
            entailment_result = classification.to_engine_result(
                character_id=char_id,
                kb_version=analysis.version,
            )
            response, clue_dict = self._engine.submit_verdict(
                char_id=char_id,
                claimed_status=is_criminal,
                entailment=entailment_result,
            )

            if response is VerdictResponse.ALREADY_SOLVED:
                continue  # Hiếm gặp: ô đã được giải từ trước, phân tích lại
            if response is VerdictResponse.STALE_PROOF:
                raise StaleProofError(
                    f"Bằng chứng cho {char_id!r} đã cũ (KB đã thay đổi). "
                    "Thử lại bước suy luận."
                )
            if response is not VerdictResponse.ACCEPTED:
                raise LogicAgentError(
                    f"GameEngine từ chối verdict cho {char_id!r}: {response.value}"
                )
            break

        # Metrics: các truy vấn phân loại + các lần giải để tìm chứng cứ
        sat_metrics_list = [dict(q.metrics) for q in classification.queries]
        sat_metrics_list.extend(analysis.extra_metrics)

        new_clue_id = clue_dict.get("clue_id") if isinstance(clue_dict, dict) else None
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        step = build_step(
            step_index=self._trace.step_count + 1,
            character_id=char_id,
            verdict=verdict_str,
            kb_version=analysis.version,
            revealed_clues=list(snapshot.revealed_clues),
            sat_metrics_list=sat_metrics_list,
            evidence_clue_ids=analysis.clue_ids if analysis.minimal_evidence else None,
            support_cell_ids=analysis.support_cell_ids,
            newly_revealed_clue_id=new_clue_id,
            elapsed_ms=elapsed_ms,
        )
        self._trace.record(step)

        # Gọi callback nếu có (ví dụ GUI cập nhật hiển thị)
        if self._on_step is not None:
            updated_snapshot = self._engine.get_public_snapshot()
            self._on_step(step, updated_snapshot)

        return step


# ---------------------------------------------------------------------------
# Factory function tiện lợi
# ---------------------------------------------------------------------------

def create_logic_agent(
    engine: GameEngine,
    dpll_solver: Any,
    *,
    trace: DeductionTrace | None = None,
    on_step: Callable[[DeductionStep, Any], None] | None = None,
    cardinality_encoding: str = "sequential",
) -> LogicAgent:
    """Tạo LogicAgent đầy đủ từ GameEngine và một DPLL solver.

    Args:
        engine:                 GameEngine đã load puzzle.
        dpll_solver:            Instance DPLLSolver (hoặc bất kỳ solver tương thích).
        trace:                  DeductionTrace tuỳ chọn; nếu None sẽ tạo mới.
        on_step:                Callback sau mỗi bước (DeductionStep, snapshot).
        cardinality_encoding:   'sequential' hoặc 'binomial' cho CNFEncoder.

    Returns:
        LogicAgent sẵn sàng hoạt động.
    """
    var_map = engine.var_map
    encoder = CNFEncoder(var_map, cardinality_encoding=cardinality_encoding)
    checker = EntailmentChecker(solver=dpll_solver, variable_map=var_map)
    return LogicAgent(
        engine=engine,
        encoder=encoder,
        checker=checker,
        trace=trace,
        on_step=on_step,
        solver=dpll_solver,
    )