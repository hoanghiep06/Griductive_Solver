"""Shared CNF data contract for the Encoder and DPLL modules.

Literal: non-zero signed integer; positive means Criminal, negative means
Innocent. Clause is a disjunction of literals. CNFFormula is a conjunction
of clauses. The list-based representation is intentionally compatible with
simple DPLL implementations and DIMACS-style inputs.
"""

from typing import TypeAlias, Iterable

Literal: TypeAlias = int
Clause: TypeAlias = list[Literal]
CNFFormula: TypeAlias = list[Clause]


def validate_cnf(cnf: Iterable[Iterable[int]], variable_count: int | None = None) -> None:
    """Raise ValueError/TypeError when a CNF violates the shared contract.

    The empty CNF ([]) is TRUE. An empty clause ([]) is FALSE. Literal zero
    is never valid. When ``variable_count`` is supplied, every variable index
    must be within the allocated range.
    """
    if variable_count is not None:
        if type(variable_count) is not int or variable_count < 0:
            raise ValueError("variable_count must be a non-negative integer")

    for clause_index, clause in enumerate(cnf):
        if isinstance(clause, (str, bytes)):
            raise TypeError(f"Clause {clause_index} must be an iterable of integers")
        for literal_index, literal in enumerate(clause):
            if type(literal) is not int:
                raise TypeError(
                    f"Literal at clause {clause_index}, position {literal_index} must be an integer"
                )
            if literal == 0:
                raise ValueError("Literal 0 is invalid in the internal CNF representation")
            if variable_count is not None and abs(literal) > variable_count:
                raise ValueError(
                    f"Literal {literal} references variable {abs(literal)}, "
                    f"but only {variable_count} variables are allocated"
                )
