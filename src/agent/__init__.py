"""Package src.agent — Tác tử suy luận Logic cho Griductive.

Exports chính:
  - LogicAgent, create_logic_agent  : Vòng lặp suy luận No-Guess (logic_agent)
  - DeductionTrace, DeductionStep   : Ghi vết suy luận chi tiết (deduction_trace)
  - SATMetrics, build_step          : Tiện ích metrics cho trace
  - UniquenessResult, UniquenessStatus,
    check_uniqueness,
    check_uniqueness_from_var_map   : Kiểm tra nghiệm duy nhất (uniqueness)
  - EntailmentChecker               : Kiểm tra hệ quả logic qua SAT (entailment)
"""

from src.agent.deduction_trace import (
    DeductionStep,
    DeductionTrace,
    SATMetrics,
    build_step,
)
from src.agent.entailment import EntailmentChecker
from src.agent.logic_agent import (
    LogicAgent,
    LogicAgentError,
    StaleProofError,
    create_logic_agent,
)
from src.agent.uniqueness import (
    UniquenessResult,
    UniquenessStatus,
    check_uniqueness,
    check_uniqueness_from_var_map,
)

__all__ = [
    # deduction_trace
    "DeductionStep",
    "DeductionTrace",
    "SATMetrics",
    "build_step",
    # entailment
    "EntailmentChecker",
    # logic_agent
    "LogicAgent",
    "LogicAgentError",
    "StaleProofError",
    "create_logic_agent",
    # uniqueness
    "UniquenessResult",
    "UniquenessStatus",
    "check_uniqueness",
    "check_uniqueness_from_var_map",
]
