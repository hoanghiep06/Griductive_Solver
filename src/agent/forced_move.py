"""Đường suy luận dùng chung, KHÔNG đổi trạng thái game.

Trước đây có hai nơi tự suy luận riêng: ``LogicAgent`` (CLI/benchmark) và
``GameplaySession.analyze`` (GUI). Module này gom thành một hàm duy nhất,
``analyze_public_kb``; cả hai nơi cùng gọi nó nên không thể lệch kết quả.

Hàm này thuần túy (pure):
  - Chỉ đọc ``PublicKBSnapshot``; không gọi ``submit_verdict``, không lật thẻ.
  - Mọi đối tượng có trạng thái (encoder, checker, solver) do caller truyền vào
    và thuộc riêng caller. GUI tạo mới cho mỗi lần phân tích nên an toàn khi
    chạy ở thread nền.

Hai chế độ:
  - ``target=None``: duyệt ô chưa giải theo thứ tự row-major, trả về ô đầu tiên
    bị ép buộc (dùng cho Hint, Auto Solve, ``LogicAgent``).
  - ``target="B2"``: phân loại đúng một ô (dùng khi người chơi tự kết luận).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from src.agent.entailment import Verdict
from src.agent.evidence import EvidenceGroup, minimize_support

if TYPE_CHECKING:  # chỉ để chú thích kiểu
    from src.agent.entailment import ClassificationResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StepAnalysis:
    """Kết quả phân tích một ô trên KB công khai tại một phiên bản nhất định.

    Attributes:
        version:           Phiên bản KB đã dùng để phân tích.
        cell_id:           Ô được phân tích (None nếu không còn ô nào bị ép buộc).
        classification:    Kết quả phân loại SAT (None nếu không có ô nào).
        clue_ids:          Manh mối làm chứng cứ (rỗng nếu chưa bị ép buộc).
        support_cell_ids:  Các ô đã chứng minh nằm trong chứng cứ.
        minimal_evidence:  True nếu chứng cứ là tập tối tiểu.
        extra_metrics:     Stats DPLL của các lần giải dùng để tìm chứng cứ.
        inconsistent:      True nếu KB mâu thuẫn.
    """

    version: int
    cell_id: str | None
    classification: "ClassificationResult | None"
    clue_ids: tuple[str, ...] = ()
    support_cell_ids: tuple[str, ...] = ()
    minimal_evidence: bool = False
    extra_metrics: tuple[dict[str, float], ...] = ()
    inconsistent: bool = False

    @property
    def is_forced(self) -> bool:
        """True nếu ô này bị ép buộc là CRIMINAL hoặc INNOCENT."""
        return (
            not self.inconsistent
            and self.classification is not None
            and self.classification.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT)
        )

    @property
    def is_criminal(self) -> bool:
        """True nếu kết luận là CRIMINAL (chỉ có nghĩa khi ``is_forced``)."""
        return self.classification is not None and self.classification.verdict is Verdict.CRIMINAL


def build_evidence_groups(snapshot: Any, encoder: Any) -> list[EvidenceGroup]:
    """Mã hóa KB thành các nhóm mệnh đề: mỗi manh mối và mỗi ô đã chứng minh một nhóm."""
    groups: list[EvidenceGroup] = [
        ("clue", clue.clue_id, [list(cl) for cl in encoder.encode_clue(clue)])
        for clue in snapshot.revealed_clues
    ]
    groups += [
        ("cell", cid, [list(encoder.encode_verdict(cid, value))])
        for cid, value in snapshot.proved_verdicts.items()
    ]
    return groups


def analyze_public_kb(
    snapshot: Any,
    unsolved_ids: Sequence[str],
    encoder: Any,
    checker: Any,
    solver: Any = None,
    target: str | None = None,
) -> StepAnalysis:
    """Phân tích KB công khai và tìm ô bị ép buộc (không đổi trạng thái game).

    Args:
        snapshot:      PublicKBSnapshot hiện tại.
        unsolved_ids:  Các ô chưa giải, ĐÃ theo thứ tự row-major
                       (``GameEngine.get_unsolved_characters()``).
        encoder:       CNFEncoder (có ``var_map``, ``encode_clue``, ``encode_verdict``).
        checker:       EntailmentChecker (có ``classify(clauses, var_id)``).
        solver:        Solver có ``solve(cnf) -> bool`` để tìm chứng cứ tối tiểu.
                       Nếu None thì chứng cứ là toàn bộ KB (minimal_evidence=False).
        target:        Ô cần phân loại; None = tìm ô bị ép buộc đầu tiên.

    Returns:
        StepAnalysis. ``cell_id is None`` nghĩa là không có ô nào bị ép buộc.
    """
    groups = build_evidence_groups(snapshot, encoder)
    clauses = [list(c) for _, _, cs in groups for c in cs]
    targets = [target] if target else list(unsolved_ids)

    for cid in targets:
        var = encoder.var_map.get_var(cid)
        result = checker.classify(clauses, var)

        if result.verdict is Verdict.INCONSISTENT:
            return StepAnalysis(snapshot.version, cid, result, inconsistent=True)

        if result.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT):
            opposite = -var if result.verdict is Verdict.CRIMINAL else var
            clue_ids, cell_ids, minimal, extra = _support_for(groups, opposite, solver, cid)
            return StepAnalysis(
                snapshot.version,
                cid,
                result,
                clue_ids=clue_ids,
                support_cell_ids=cell_ids,
                minimal_evidence=minimal,
                extra_metrics=tuple(extra),
            )

        if target:
            # Người chơi hỏi đúng ô này nhưng chưa thể kết luận
            return StepAnalysis(snapshot.version, cid, result)

    return StepAnalysis(snapshot.version, None, None)


def _support_for(
    groups: Sequence[EvidenceGroup],
    opposite: int,
    solver: Any,
    cid: str,
) -> tuple[tuple[str, ...], tuple[str, ...], bool, list[dict[str, float]]]:
    """Tính tập chứng cứ; lùi về toàn bộ KB nếu không tối thiểu hoá được."""

    def everything() -> tuple[tuple[str, ...], tuple[str, ...]]:
        return (
            tuple(k for kind, k, _ in groups if kind == "clue"),
            tuple(k for kind, k, _ in groups if kind == "cell"),
        )

    if solver is None or not hasattr(solver, "solve"):
        clues, cells = everything()
        return clues, cells, False, []

    extra: list[dict[str, float]] = []

    def record() -> None:
        stats = solver.get_stats() if hasattr(solver, "get_stats") else {}
        extra.append(dict(stats))

    try:
        # An toàn: toàn bộ KB ∧ ¬C phải UNSAT thì mới thu nhỏ được.
        base = [list(c) for _, _, cs in groups for c in cs] + [[opposite]]
        satisfiable = solver.solve(base)
        record()
        if satisfiable:
            logger.warning("KB ∧ ¬C không UNSAT khi tính chứng cứ cho %r; dùng toàn bộ KB.", cid)
            clues, cells = everything()
            return clues, cells, False, extra

        support = minimize_support(groups, opposite, solver, on_solve=record)
        return (
            tuple(k for kind, k, _ in support if kind == "clue"),
            tuple(k for kind, k, _ in support if kind == "cell"),
            True,
            extra,
        )
    except Exception:  # noqa: BLE001 — chứng cứ chỉ là phần trình bày, không được làm hỏng suy luận
        logger.exception("Không tính được chứng cứ tối tiểu cho %r", cid)
        clues, cells = everything()
        return clues, cells, False, extra