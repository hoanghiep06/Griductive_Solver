"""Immutable, normalized clue model.

The JSON representation uses ``type`` and ``parameters``. The model keeps
parameters separate from clue identity so clues can be traced independently
from their owner characters.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return frozenset(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw(v) for v in value]
    if isinstance(value, frozenset):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class Clue:
    clue_id: str
    owner_id: str
    clue_type: str
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("clue_id", "owner_id", "clue_type"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Clue.{field_name} must be a non-empty string")
        if not isinstance(self.parameters, Mapping):
            raise TypeError("Clue.parameters must be a mapping")
        object.__setattr__(self, "clue_id", self.clue_id.strip())
        object.__setattr__(self, "owner_id", self.owner_id.strip())
        object.__setattr__(self, "clue_type", self.clue_type.strip().upper())
        object.__setattr__(self, "parameters", _freeze(dict(self.parameters)))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Clue":
        allowed = {"clue_id", "owner_id", "type", "parameters"}
        unknown = set(data) - allowed
        missing = allowed - set(data)
        if unknown or missing:
            raise ValueError(
                f"clue fields mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        return cls(
            clue_id=data["clue_id"],
            owner_id=data["owner_id"],
            clue_type=data["type"],
            parameters=data["parameters"],
        )

    def to_dict(self) -> dict:
        return {
            "clue_id": self.clue_id,
            "owner_id": self.owner_id,
            "type": self.clue_type,
            "parameters": _thaw(self.parameters),
        }
