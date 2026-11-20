"""Compatibility exports; core owns the shared variable namespace."""
from src.core.variable_map import (
    CharacterEntry, VariableMap, format_coord, normalize_coord, parse_coord,
)

__all__ = ["CharacterEntry", "VariableMap", "format_coord", "normalize_coord", "parse_coord"]
