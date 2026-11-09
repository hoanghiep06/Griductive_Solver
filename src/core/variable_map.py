"""Deterministic mapping between Griductive characters and SAT variables."""

from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

from src.core.character import Character
from src.core.cnf_types import Literal


def _freeze_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_metadata(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_metadata(item) for item in value)
    return value


class VariableMap:
    """Map each character to one stable primary Boolean variable.

    Primary IDs are assigned in alphabetical display-name order (case-folded),
    with character ID as a deterministic tie-breaker. Auxiliary IDs are only
    allocated after the primary map has been frozen, so the two namespaces
    can never overlap or shift after an Encoder starts using them.
    """

    def __init__(self) -> None:
        self._char_to_var: dict[str, int] = {}
        self._var_to_char: dict[int, str] = {}
        self._auxiliary_metadata: dict[int, Mapping[str, Any]] = {}
        self._primary_count = 0
        self._total_vars = 0
        self._primary_frozen = False

    def register_character(self, char_id: str) -> int:
        """Register one primary variable.

        Prefer ``register_characters`` for deterministic bulk registration.
        Duplicate registration is rejected rather than silently hidden.
        """
        if self._primary_frozen:
            raise RuntimeError("Primary variables are frozen; no more characters can be registered")
        if not isinstance(char_id, str) or not char_id.strip():
            raise ValueError("char_id must be a non-empty string")
        if char_id != char_id.strip():
            raise ValueError("char_id cannot contain leading or trailing whitespace")
        if char_id in self._char_to_var:
            raise ValueError(f"Character {char_id!r} is already registered")

        self._primary_count += 1
        self._total_vars += 1
        var_id = self._total_vars
        self._char_to_var[char_id] = var_id
        self._var_to_char[var_id] = char_id
        return var_id

    def register_characters(self, characters: Iterable[Character | Mapping[str, Any]]) -> dict[str, int]:
        """Register a collection in deterministic alphabetical name order."""
        if self._primary_frozen:
            raise RuntimeError("Primary variables are frozen")

        normalized: list[tuple[str, str]] = []
        for character in characters:
            if isinstance(character, Character):
                char_id, name = character.id, character.name
            elif isinstance(character, Mapping):
                char_id, name = character.get("id"), character.get("name")
            else:
                raise TypeError("characters must contain Character objects or mappings")
            if not isinstance(char_id, str) or not char_id.strip():
                raise ValueError("Every character must have a non-empty id")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"Character {char_id!r} must have a non-empty display name")
            if char_id != char_id.strip():
                raise ValueError(f"Character ID {char_id!r} contains leading or trailing whitespace")
            normalized.append((char_id, name.strip()))

        ids = [char_id for char_id, _ in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate character IDs in registration batch")
        if set(ids).intersection(self._char_to_var):
            duplicates = sorted(set(ids).intersection(self._char_to_var))
            raise ValueError(f"Characters already registered: {duplicates}")

        for char_id, _ in sorted(normalized, key=lambda item: (item[1].casefold(), item[0].casefold(), item[0])):
            self.register_character(char_id)
        return dict(self._char_to_var)

    def freeze_primary_variables(self) -> None:
        """Finalize primary IDs before any auxiliary variable is allocated."""
        self._primary_frozen = True

    @property
    def is_frozen(self) -> bool:
        return self._primary_frozen

    def get_var(self, char_id: str) -> int:
        if not isinstance(char_id, str):
            raise TypeError("char_id must be a string")
        try:
            return self._char_to_var[char_id]
        except KeyError as exc:
            raise KeyError(f"[VariableMap] Character {char_id!r} has no primary variable") from exc

    def get_char_id(self, var_id: int) -> Optional[str]:
        """Return the character for a signed literal/variable, or None for aux vars."""
        if type(var_id) is not int or var_id == 0:
            raise ValueError("var_id must be a non-zero integer")
        if abs(var_id) > self._total_vars:
            raise KeyError(f"Variable {var_id} has not been allocated")
        return self._var_to_char.get(abs(var_id))

    def allocate_auxiliary_variable(self, metadata: Optional[Mapping[str, Any]] = None) -> int:
        """Allocate one auxiliary variable with optional debugging metadata."""
        if not self._primary_frozen:
            raise RuntimeError("Freeze primary variables before allocating auxiliary variables")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping or None")
        self._total_vars += 1
        var_id = self._total_vars
        self._auxiliary_metadata[var_id] = _freeze_metadata(dict(metadata or {}))
        return var_id

    def get_auxiliary_metadata(self, var_id: int) -> Optional[Mapping[str, Any]]:
        if type(var_id) is not int or var_id <= 0:
            raise ValueError("var_id must be a positive integer")
        return self._auxiliary_metadata.get(var_id)

    @property
    def primary_count(self) -> int:
        return self._primary_count

    @property
    def auxiliary_count(self) -> int:
        return self._total_vars - self._primary_count

    @property
    def total_variables(self) -> int:
        return self._total_vars

    @property
    def character_ids(self) -> tuple[str, ...]:
        return tuple(self._char_to_var.keys())

    @property
    def primary_mapping(self) -> Mapping[str, int]:
        return MappingProxyType(dict(self._char_to_var))

    @property
    def auxiliary_metadata(self) -> Mapping[int, Mapping[str, Any]]:
        return MappingProxyType(dict(self._auxiliary_metadata))

    def to_literal(self, char_id: str, is_criminal: bool) -> Literal:
        if type(is_criminal) is not bool:
            raise TypeError("is_criminal must be bool (True=CRIMINAL, False=INNOCENT)")
        var_id = self.get_var(char_id)
        return var_id if is_criminal else -var_id

    def __repr__(self) -> str:
        return (
            f"<VariableMap: {self._primary_count} primary, "
            f"{self.auxiliary_count} auxiliary, frozen={self._primary_frozen}>"
        )
