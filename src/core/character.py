"""Immutable character model used by the Griductive core."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Character:
    """A character occupying exactly one cell of the puzzle grid.

    ``row`` and ``col`` are zero-based internal coordinates. Presentation
    layers are responsible for displaying one-based row numbers and letters.
    """

    id: str
    name: str
    profession: str
    row: int
    col: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Character.id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"Character {self.id!r} must have a non-empty name")
        if not isinstance(self.profession, str) or not self.profession.strip():
            raise ValueError(f"Character {self.id!r} must have a non-empty profession")
        if type(self.row) is not int or type(self.col) is not int:
            raise TypeError("Character row and col must be integers (not booleans)")
        if self.row < 0 or self.col < 0:
            raise ValueError("Character row and col must be non-negative")
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "profession", self.profession.strip())

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(
            id=data["id"],
            name=data["name"],
            profession=data["profession"],
            row=data["row"],
            col=data["col"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "profession": self.profession,
            "row": self.row,
            "col": self.col,
        }
