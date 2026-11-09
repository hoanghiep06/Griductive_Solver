"""Compatibility import for the shared TV1 VariableMap.

Do not implement a second mapping here. The canonical class lives in
``src.core.variable_map`` and is shared by GameEngine and CNFEncoder.
"""

from src.core.variable_map import VariableMap

__all__ = ["VariableMap"]
