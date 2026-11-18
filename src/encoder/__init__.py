"""CNF encoding and variable mapping utilities for Griductive."""

from .cnf_encoder import CNFEncoder, EncodedKB
from .variable_map import (
    CharacterEntry,
    VariableMap,
    format_coord,
    normalize_coord,
    parse_coord,
)

__all__ = [
    "CNFEncoder",
    "CharacterEntry",
    "EncodedKB",
    "VariableMap",
    "format_coord",
    "normalize_coord",
    "parse_coord",
]
