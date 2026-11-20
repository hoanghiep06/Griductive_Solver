"""Validated puzzle aggregate used internally by GameEngine."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from src.core.character import Character
from src.core.clue import Clue


@dataclass(frozen=True, slots=True)
class Puzzle:
    puzzle_id: str
    grid_size: int
    characters: tuple[Character, ...]
    hidden_solution: Mapping[str, bool]
    initial_revealed: tuple[str, ...]
    clues: tuple[Clue, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "characters", tuple(self.characters))
        object.__setattr__(self, "hidden_solution", MappingProxyType(dict(self.hidden_solution)))
        object.__setattr__(self, "initial_revealed", tuple(self.initial_revealed))
        object.__setattr__(self, "clues", tuple(self.clues))

    @property
    def characters_by_id(self) -> Mapping[str, Character]:
        return MappingProxyType({character.id: character for character in self.characters})

    @property
    def clues_by_owner(self) -> Mapping[str, Clue]:
        return MappingProxyType({clue.owner_id: clue for clue in self.clues})
