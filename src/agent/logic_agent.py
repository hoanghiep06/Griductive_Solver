"""Vòng lặp suy luận No-Guess của Logic Agent (TV5).

Thuật toán No-Guess Deduction Loop:
  Lặp cho đến khi không còn nhân vật nào có thể suy luận được:
    1. Lấy snapshot KB hiện tại (phiên bản + manh mối đã mở + phán quyết đã biết).
    2. Mã hóa KB thành CNF bằng CNFEncoder.
    3. Gọi EntailmentChecker.first_forced() để tìm nhân vật *bị ép buộc đầu tiên*
       theo thứ tự row-major.
    4. Nếu tìm thấy:
       a. Chuyển ClassificationResult → EntailmentResult.
       b. Gọi GameEngine.submit_verdict() để xác nhận và nhận Clue mới.
       c. Ghi vết vào DeductionTrace.
       d. Tiếp tục vòng lặp (KB đã được cập nhật tự động qua GameEngine).
    5. Nếu không tìm thấy → kết thúc vòng lặp (puzzle hết khả năng suy luận
       thuần túy, hoặc đã giải hoàn toàn).

Thiết kế:
  - Không nhìn vào hidden solution; chỉ dùng PublicKBSnapshot.
  - Mỗi lần submit thành công tăng KB version, nên vòng lặp luôn hội tụ
    (số nhân vật giảm dần hoặc không có bước nào được thực hiện).
  - hint_step() chạy đúng một bước suy luận.
  - iter_steps() là generator: mỗi lần next() chạy đúng MỘT bước, caller
    (QTimer / CLI) tự quyết định nghỉ bao lâu giữa hai bước.
  - auto_solve() chạy liên tục (dành cho CLI / benchmark).
"""

from __future__ import annotations

import time
from typing import Any, Callable, Iterator

from src.agent.deduction_trace import (
    DeductionStep,
    DeductionTrace,
    SATMetrics,
    build_step,
)
from src.agent.entailment import (
    ClassificationResult,
    EntailmentChecker,
    Verdict,
    row_major_key,
)
from src.core.entailment_result import EntailmentResult, EntailmentStatus
from src.core.game_engine import GameEngine, VerdictResponse
from src.encoder.cnf_encoder import CNFEncoder


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
    """

    def __init__(
        self,
        engine: GameEngine,
        encoder: CNFEncoder,
        checker: EntailmentChecker,
        trace: DeductionTrace | None = None,
        on_step: Callable[[DeductionStep, Any], None] | None = None,
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

    # ------------------------------------------------------------------
    # API công khai
    # ------------------------------------------------------------------

    @property
    def trace(self) -> DeductionTrace:
        """Truy cập vết suy luận đã tích lũy."""
        return self._trace

    def hint_step(self) -> DeductionStep | None:
        """Thực hiện đúng MỘT bước suy luận.

        Returns:
            DeductionStep nếu tìm thấy nhân vật bị ép buộc, hoặc
            None nếu không còn bước nào có thể suy luận được.

        Raises:
            LogicAgentError: Nếu KB mâu thuẫn hoặc lỗi nội bộ nghiêm trọng.
        """
        return self._run_one_step()

    def iter_steps(self, max_steps: int | None = None) -> Iterator[DeductionStep]:
        """Sinh từng bước suy luận một (generator).

        Mỗi lần next() chỉ chạy ĐÚNG một bước: chọn ô bị ép buộc đầu tiên
        (row-major), lật bài, cập nhật KB. Caller tự quyết định nghỉ bao lâu
        giữa hai bước (ví dụ QTimer trong GUI).

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
        if exhausted:
            self._trace.mark_finished()

    def auto_solve(self, max_steps: int | None = None) -> int:
        """Chạy vòng lặp suy luận liên tục cho đến khi không còn bước nào.

        Returns:
            Số bước suy luận thành công đã thực hiện.

        Raises:
            LogicAgentError: Nếu KB mâu thuẫn hoặc GameEngine từ chối verdict.
        """
        return sum(1 for _ in self.iter_steps(max_steps))

    # ------------------------------------------------------------------
    # Nội bộ: một bước suy luận
    # ------------------------------------------------------------------

    def _run_one_step(self) -> DeductionStep | None:
        """Tìm và thực hiện bước suy luận tiếp theo.

        Returns:
            DeductionStep nếu thành công, None nếu không có bước nào.
        """
        snapshot = self._engine.get_public_snapshot()

        # Danh sách nhân vật chưa giải (theo thứ tự row-major để xây unresolved)
        unresolved_char_ids = self._engine.get_unsolved_characters()
        if not unresolved_char_ids:
            return None  # Đã giải hết

        # Mã hóa KB hiện tại thành CNF
        encoded = self._encoder.encode_public_kb(snapshot, reset_aux=True)
        cnf = encoded.clauses

        # Xây dựng {char_id: var_id} cho các nhân vật chưa giải
        # (Thứ tự đã được đảm bảo row-major từ get_unsolved_characters)
        var_map = self._engine.var_map
        unresolved: dict[str, int] = {}
        for char_id in unresolved_char_ids:
            # Chuyển char_id sang định dạng cell_id mà row_major_key() chấp nhận
            cell_id = self._char_id_to_cell_id(char_id, var_map)
            var_id = var_map.get_var(char_id)
            unresolved[cell_id] = var_id

        if not unresolved:
            return None

        # Tìm nhân vật đầu tiên bị ép buộc theo thứ tự row-major
        t_start = time.perf_counter()
        forced = self._checker.first_forced(cnf, unresolved)
        t_elapsed = time.perf_counter() - t_start

        if forced is None:
            return None  # Không có nhân vật nào bị ép buộc (KB không đủ ràng buộc)

        cell_id, classification = forced

        # Xác định verdict và char_id thực
        verdict_enum = classification.verdict
        if verdict_enum is Verdict.INCONSISTENT:
            raise LogicAgentError(
                f"KB mâu thuẫn (INCONSISTENT) tại KB version={snapshot.version}. "
                "Puzzle có thể bị lỗi hoặc có manh mối xung đột."
            )
        if verdict_enum is Verdict.UNKNOWN:
            # first_forced() không nên trả về UNKNOWN — bảo vệ
            return None

        char_id = self._cell_id_to_char_id(cell_id, var_map)
        is_criminal: bool = verdict_enum is Verdict.CRIMINAL
        claimed_status = is_criminal
        verdict_str = "CRIMINAL" if is_criminal else "INNOCENT"

        # Chuyển ClassificationResult → EntailmentResult
        entailment_result = classification.to_engine_result(
            character_id=char_id,
            kb_version=snapshot.version,
        )

        # Gửi verdict lên GameEngine
        response, clue_dict = self._engine.submit_verdict(
            char_id=char_id,
            claimed_status=claimed_status,
            entailment=entailment_result,
        )

        if response is VerdictResponse.STALE_PROOF:
            raise StaleProofError(
                f"Bằng chứng cho {char_id!r} đã cũ (KB đã thay đổi). "
                "Thử lại bước suy luận."
            )
        if response is VerdictResponse.ALREADY_SOLVED:
            # Trường hợp hiếm gặp: nhân vật đã được giải từ trước
            return self._run_one_step()
        if response not in (VerdictResponse.ACCEPTED,):
            raise LogicAgentError(
                f"GameEngine từ chối verdict cho {char_id!r}: {response.value}"
            )

        # Tổng hợp metrics từ SAT queries
        sat_metrics_list = [dict(q.metrics) for q in classification.queries]

        # Ghi vết suy luận
        step = build_step(
            step_index=self._trace.step_count + 1,
            character_id=char_id,
            verdict=verdict_str,
            kb_version=snapshot.version,
            revealed_clues=list(snapshot.revealed_clues),
            sat_metrics_list=sat_metrics_list,
        )
        self._trace.record(step)

        # Gọi callback nếu có (ví dụ GUI cập nhật hiển thị)
        if self._on_step is not None:
            updated_snapshot = self._engine.get_public_snapshot()
            self._on_step(step, updated_snapshot)

        return step

    # ------------------------------------------------------------------
    # Tiện ích chuyển đổi định danh
    # ------------------------------------------------------------------

    def _char_id_to_cell_id(self, char_id: str, var_map: Any) -> str:
        """Chuyển char_id về dạng cell_id (ví dụ 'A1') mà row_major_key() chấp nhận.

        Nếu char_id đã có dạng 'A1', trả về ngay. Nếu không,
        tra cứu entry trong VariableMap để lấy coord.
        """
        # Thử parse trực tiếp như cell_id
        try:
            row_major_key(char_id)
            return char_id  # char_id đã là cell_id hợp lệ
        except (ValueError, TypeError):
            pass
        # Tra cứu qua VariableMap
        try:
            entry = var_map.get_entry(char_id)
            if entry.coord:
                # Chuyển coord (định dạng 'C2') thành row-major key
                # row_major_key() dùng định dạng '{col}{row}' (A1, B2, ...)
                return entry.coord
        except (KeyError, AttributeError):
            pass
        # Fallback: trả về char_id và hy vọng EntailmentChecker xử lý được
        return char_id

    def _cell_id_to_char_id(self, cell_id: str, var_map: Any) -> str:
        """Chuyển cell_id trở về char_id chính tắc trong VariableMap."""
        try:
            return var_map.resolve_canonical(cell_id)
        except (KeyError, ValueError):
            return cell_id  # Fallback


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
    )