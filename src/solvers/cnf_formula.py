"""Shared CNF type aliases for the DPLL implementation (TV2).

The canonical contract lives in ``src.core.cnf_types``. Solver-specific
algorithms and data structures may be added here, but must remain compatible
with these list-based Literal/Clause/CNFFormula aliases.
"""

from src.core.cnf_types import CNFFormula, Clause, Literal, validate_cnf

__all__ = ["Literal", "Clause", "CNFFormula", "validate_cnf"]
