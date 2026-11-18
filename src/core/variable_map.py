"""Deterministic mapping between Griductive characters and SAT variables."""

from dataclasses import dataclass
import re
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


_COORD_RE = re.compile(r"^\s*([A-Za-z])\s*([1-9][0-9]*)\s*$")


def parse_coord(coord: str) -> tuple[int, int]:
    """Parse a grid coordinate like 'C2' into 1-based (col_index, row_index)."""
    if not isinstance(coord, str):
        raise ValueError(f"Coordinate must be a string, got {type(coord).__name__}")
    match = _COORD_RE.match(coord)
    if not match:
        raise ValueError(f"Invalid grid coordinate: {coord!r}")
    col_letter = match.group(1).upper()
    row_index = int(match.group(2))
    col_index = ord(col_letter) - ord("A") + 1
    return col_index, row_index


def format_coord(col_index: int, row_index: int) -> str:
    """Format 1-based (col_index, row_index) into a coordinate like 'C2'."""
    if col_index < 1 or col_index > 26 or row_index < 1:
        raise ValueError(f"Coordinate indices out of range: ({col_index}, {row_index})")
    return f"{chr(ord('A') + col_index - 1)}{row_index}"


def normalize_coord(coord: str) -> str:
    """Normalize a grid coordinate string such as 'c2' to 'C2'."""
    col_index, row_index = parse_coord(coord)
    return format_coord(col_index, row_index)


@dataclass(frozen=True)
class CharacterEntry:
    """Normalized metadata for a single character/cell in a puzzle."""

    key: str
    name: str
    coord: str | None = None
    profession: str | None = None
    row: int | None = None
    col: str | None = None
    col_index: int | None = None


def _coerce_character_entry(item: Any, fallback_coord: str | None = None) -> CharacterEntry:
    """Convert a string, dict, or character-like object into CharacterEntry."""
    raw_name: str | None = None
    raw_coord: str | None = fallback_coord
    raw_profession: str | None = None

    if isinstance(item, CharacterEntry):
        return item
    if isinstance(item, str):
        stripped = item.strip()
        if not stripped:
            raise ValueError("Character identifier cannot be empty")
        if raw_coord is None and _COORD_RE.match(stripped):
            raw_coord = stripped
        raw_name = stripped
    elif isinstance(item, dict):
        raw_coord = item.get("coord") or item.get("cell") or item.get("coordinate") or raw_coord
        raw_name = item.get("name") or item.get("id") or item.get("character")
        raw_profession = item.get("profession") or item.get("occupation")
        if raw_name is None and raw_coord is not None:
            raw_name = str(raw_coord)
    else:
        raw_coord = getattr(item, "coord", None) or getattr(item, "cell", None) or raw_coord
        raw_name = getattr(item, "name", None) or getattr(item, "id", None)
        raw_profession = getattr(item, "profession", None) or getattr(item, "occupation", None)
        if raw_name is None and raw_coord is not None:
            raw_name = str(raw_coord)

    if not raw_name or not isinstance(raw_name, str) or not raw_name.strip():
        raise ValueError(f"Character entry is missing a valid name/identifier: {item!r}")

    name = raw_name.strip()
    norm_coord: str | None = None
    row: int | None = None
    col: str | None = None
    col_index: int | None = None

    if raw_coord is not None:
        col_index, row = parse_coord(str(raw_coord))
        norm_coord = format_coord(col_index, row)
        col = norm_coord[0]
        if _COORD_RE.match(name) and normalize_coord(name) == norm_coord:
            name = norm_coord

    key = name
    return CharacterEntry(
        key=key,
        name=name,
        coord=norm_coord,
        profession=str(raw_profession).strip() if raw_profession is not None else None,
        row=row,
        col=col,
        col_index=col_index,
    )


def _parse_grid_size(grid_size: Any) -> tuple[int, int] | None:
    """Normalize grid_size input into (rows, cols)."""
    if grid_size is None:
        return None
    if isinstance(grid_size, int) and not isinstance(grid_size, bool):
        if grid_size < 1 or grid_size > 26:
            raise ValueError(f"grid_size must be between 1 and 26, got {grid_size}")
        return (grid_size, grid_size)
    if isinstance(grid_size, (tuple, list)) and len(grid_size) == 2:
        rows, cols = grid_size
        if (
            isinstance(rows, int)
            and isinstance(cols, int)
            and not isinstance(rows, bool)
            and not isinstance(cols, bool)
            and 1 <= rows <= 26
            and 1 <= cols <= 26
        ):
            return (rows, cols)
    raise ValueError(f"Invalid grid_size: {grid_size!r}")



class VariableMap:
    """Map each character to one stable primary Boolean variable.

    Primary IDs are assigned in alphabetical display-name order (case-folded),
    with character ID as a deterministic tie-breaker. Auxiliary IDs are only
    allocated after the primary map has been frozen, so the two namespaces
    can never overlap or shift after an Encoder starts using them.
    """

    def __init__(self, characters=None, grid_size=None) -> None:
        self._char_to_var: dict[str, int] = {}
        self._var_to_char: dict[int, str] = {}
        self._auxiliary_metadata: dict[int, Mapping[str, Any]] = {}
        self._primary_count = 0
        self._total_vars = 0
        self._primary_frozen = False
        self._grid_size = _parse_grid_size(grid_size)
        self._entries = {}
        self._coord_to_key = {}
        self._aliases = {}
        if characters is not None:
            self.register_characters(characters)
            if not self._primary_count:
                raise ValueError("At least one character is required")

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

        if isinstance(characters, dict):
            return self._register_encoder_characters(characters)
        characters = list(characters)
        if characters and not all(isinstance(c, Character) or (isinstance(c, Mapping) and "id" in c) for c in characters):
            return self._register_encoder_characters(characters)
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
        for character in characters:
            get = (lambda key: getattr(character, key)) if isinstance(character, Character) else character.get
            row, col = get("row"), get("col")
            coord = format_coord(col + 1, row + 1) if row is not None and col is not None else None
            entry = _coerce_character_entry({"name": get("name"), "coord": coord})
            self._record_entry(get("id"), entry)
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

    @classmethod
    def from_characters(
        cls,
        characters: Iterable[Any] | dict[str, Any],
        grid_size: int | tuple[int, int] | None = None,
    ) -> "VariableMap":
        """Build a deterministic VariableMap from an iterable or mapping of characters."""
        return cls(characters=characters, grid_size=grid_size)

    @classmethod
    def from_puzzle(cls, puzzle: dict[str, Any]) -> "VariableMap":
        """Build a deterministic VariableMap from a puzzle dictionary."""
        if not isinstance(puzzle, dict):
            raise TypeError(f"puzzle must be a dict, got {type(puzzle).__name__}")

        raw_size = puzzle.get("grid_size", puzzle.get("size"))
        if raw_size is None and "rows" in puzzle and "cols" in puzzle:
            raw_size = (puzzle["rows"], puzzle["cols"])
        parsed_size = _parse_grid_size(raw_size)

        characters = puzzle.get("characters")
        if characters is None:
            if parsed_size is None:
                raise ValueError("Puzzle dict must include 'characters' or 'size'/'grid_size'")
            rows, cols = parsed_size
            characters = [
                format_coord(col_idx, row_idx)
                for row_idx in range(1, rows + 1)
                for col_idx in range(1, cols + 1)
            ]

        return cls(characters=characters, grid_size=parsed_size)

    def _register_encoder_characters(self, characters: Iterable[Any] | dict[str, Any]) -> dict[str, int]:
        """Register characters deterministically before any auxiliary variables exist."""
        if self._primary_frozen:
            raise RuntimeError("Cannot add primary variables after auxiliary variables are allocated")

        raw_entries: list[CharacterEntry] = []
        if isinstance(characters, dict):
            for key, value in characters.items():
                fallback_coord = str(key) if _COORD_RE.match(str(key)) else None
                if isinstance(value, dict):
                    merged = dict(value)
                    if fallback_coord is not None and "coord" not in merged and "cell" not in merged:
                        merged["coord"] = fallback_coord
                    elif fallback_coord is None and "name" not in merged and "id" not in merged:
                        merged["name"] = str(key)
                    raw_entries.append(_coerce_character_entry(merged, fallback_coord=fallback_coord))
                elif isinstance(value, str):
                    if fallback_coord is not None:
                        raw_entries.append(_coerce_character_entry({"name": value, "coord": fallback_coord}))
                    else:
                        raw_entries.append(_coerce_character_entry(value))
                else:
                    raw_entries.append(_coerce_character_entry(value, fallback_coord=fallback_coord))
        else:
            for item in characters:
                raw_entries.append(_coerce_character_entry(item))

        if not raw_entries:
            raise ValueError("At least one character is required")

        # Validate grid bounds and infer grid_size if coordinates are present.
        coords_present = [entry for entry in raw_entries if entry.coord is not None]
        if coords_present:
            max_row = max(e.row for e in coords_present if e.row is not None)
            max_col = max(e.col_index for e in coords_present if e.col_index is not None)
            if self._grid_size is None:
                side = max(max_row, max_col)
                self._grid_size = (side, side)
            else:
                g_rows, g_cols = self._grid_size
                if max_row > g_rows or max_col > g_cols:
                    raise ValueError(
                        f"Coordinate exceeds declared grid size {self._grid_size}: "
                        f"max_row={max_row}, max_col={max_col}"
                    )

        # Deterministic sorting:
        # Alphabetical by display name when characters have names beyond coordinates;
        # row-major when identifiers are purely coordinates.
        has_display_names = any(
            entry.coord is None or entry.name != entry.coord for entry in raw_entries
        )
        if has_display_names:
            sorted_entries = sorted(
                raw_entries,
                key=lambda e: (e.name.casefold(), e.name, e.coord or ""),
            )
        else:
            sorted_entries = sorted(
                raw_entries,
                key=lambda e: (e.row or 0, e.col_index or 0, e.name),
            )

        for entry in sorted_entries:
            if entry.key in self._char_to_var or entry.name.casefold() in self._aliases:
                raise ValueError(f"Duplicate character name/key: {entry.key!r}")
            if entry.coord is not None and entry.coord in self._coord_to_key:
                raise ValueError(f"Duplicate grid coordinate: {entry.coord!r}")
            self.register_character(entry.key)
            self._record_entry(entry.key, entry)
        return dict(self._char_to_var)


    def _record_entry(self, key, entry):
        self._entries[key] = CharacterEntry(key, entry.name, entry.coord, entry.profession, entry.row, entry.col, entry.col_index)
        self._aliases.setdefault(entry.name.casefold(), key)
        if entry.coord:
            self._coord_to_key[entry.coord] = key
            if self._grid_size is None:
                self._grid_size = (entry.row, entry.col_index)
            else:
                self._grid_size = (max(self._grid_size[0], entry.row), max(self._grid_size[1], entry.col_index))

    def resolve_canonical(self, identifier: str) -> str:
        """Resolve a character name or grid coordinate to its canonical key."""
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"Character identifier must be a non-empty string, got {identifier!r}")
        cleaned = identifier.strip()
        if cleaned in self._char_to_var:
            return cleaned
        if cleaned in self._coord_to_key:
            return self._coord_to_key[cleaned]
        lowered = cleaned.casefold()
        if lowered in self._aliases:
            return self._aliases[lowered]
        if _COORD_RE.match(cleaned):
            norm = normalize_coord(cleaned)
            if norm in self._coord_to_key:
                return self._coord_to_key[norm]
        raise KeyError(f"Unknown character or cell identifier: {identifier!r}")

    def has_primary(self, identifier: str) -> bool:
        """Return True if the identifier maps to a registered primary variable."""
        try:
            self.resolve_canonical(identifier)
            return True
        except (KeyError, ValueError):
            return False

    def get_primary(self, identifier: str) -> int:
        """Return the positive primary variable ID C_i for the given character/cell."""
        canonical = self.resolve_canonical(identifier)
        return self._char_to_var[canonical]

    def get_entry(self, identifier: str) -> CharacterEntry:
        """Return the CharacterEntry metadata for the given character/cell."""
        canonical = self.resolve_canonical(identifier)
        return self._entries[canonical]

    def allocate_aux(self, tag=""):
        self.freeze_primary_variables()
        return self.allocate_auxiliary_variable({"tag": tag.strip() if tag else ""})

    new_aux = allocate_aux

    def cell_var(self, row, col):
        if type(row) is not int or type(col) is not int or row < 0 or col < 0:
            raise ValueError("Cell indices must be non-negative integers")
        return self.get_primary(format_coord(col + 1, row + 1))

    def reset_auxiliary(self):
        self._auxiliary_metadata.clear()
        self._total_vars = self._primary_count

    @property
    def _aux_by_id(self):
        return {v: m.get("tag") or f"aux_{v}" for v, m in self._auxiliary_metadata.items()}

    def is_primary(self, literal_or_var: int) -> bool:
        """Return True iff abs(literal_or_var) is a primary variable."""
        return abs(literal_or_var) in self._var_to_char

    def is_auxiliary(self, literal_or_var: int) -> bool:
        """Return True iff abs(literal_or_var) is an auxiliary variable."""
        return abs(literal_or_var) in self._aux_by_id

    def label_of(self, literal_or_var: int) -> str:
        """Return a human-readable label for a variable ID or signed literal."""
        if literal_or_var == 0:
            raise ValueError("DIMACS variable/literal ID cannot be 0")
        sign = "~" if literal_or_var < 0 else ""
        var_id = abs(literal_or_var)
        if var_id in self._var_to_char:
            return f"{sign}C[{self._var_to_char[var_id]}]"
        if var_id in self._aux_by_id:
            return f"{sign}AUX[{var_id}:{self._aux_by_id[var_id]}]"
        raise KeyError(f"Unknown variable ID: {var_id}")

    @property
    def num_primary(self) -> int:
        return len(self._char_to_var)

    @property
    def num_auxiliary(self) -> int:
        return len(self._aux_by_id)

    @property
    def total_vars(self) -> int:
        return self.num_primary + self.num_auxiliary

    @property
    def primary_ids(self) -> list[int]:
        return sorted(self._var_to_char.keys())

    @property
    def auxiliary_ids(self) -> list[int]:
        return sorted(self._aux_by_id.keys())

    @property
    def primary_map(self) -> dict[str, int]:
        return dict(self._char_to_var)

    @property
    def auxiliary_map(self) -> dict[int, str]:
        return dict(self._aux_by_id)

    @property
    def grid_size(self) -> tuple[int, int] | None:
        return self._grid_size

    def cells_in_row(self, row: int) -> list[str]:
        """Return canonical character keys in the specified 1-based row in column order."""
        if self._grid_size is None:
            raise ValueError("Grid coordinates are required to resolve a row region")
        if isinstance(row, bool) or not isinstance(row, int):
            raise ValueError(f"Row index must be an integer, got {row!r}")
        rows, _ = self._grid_size
        if row < 1 or row > rows:
            raise ValueError(f"Row index {row} out of range 1..{rows}")
        matched = [e for e in self._entries.values() if e.row == row]
        if not matched:
            raise ValueError(f"No characters registered in row {row}")
        matched.sort(key=lambda e: (e.col_index or 0, e.key))
        return [e.key for e in matched]

    def cells_in_col(self, col: str) -> list[str]:
        """Return canonical character keys in the specified column letter in row order."""
        if self._grid_size is None:
            raise ValueError("Grid coordinates are required to resolve a column region")
        if not isinstance(col, str) or len(col.strip()) != 1 or not col.strip().isalpha():
            raise ValueError(f"Column must be a single letter, got {col!r}")
        col_upper = col.strip().upper()
        col_index = ord(col_upper) - ord("A") + 1
        _, cols = self._grid_size
        if col_index < 1 or col_index > cols:
            raise ValueError(f"Column {col_upper!r} out of range A..{chr(ord('A') + cols - 1)}")
        matched = [e for e in self._entries.values() if e.col == col_upper]
        if not matched:
            raise ValueError(f"No characters registered in column {col_upper}")
        matched.sort(key=lambda e: (e.row or 0, e.key))
        return [e.key for e in matched]

    def neighbors_of(self, identifier: str) -> list[str]:
        """Return canonical character keys adjacent (8-neighborhood, excluding self) to a cell."""
        if self._grid_size is None:
            raise ValueError("Grid coordinates are required to resolve a neighbors region")
        entry = self.get_entry(identifier)
        if entry.coord is None or entry.row is None or entry.col_index is None:
            raise ValueError(f"Character {identifier!r} has no grid coordinate")

        result: list[CharacterEntry] = []
        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                if d_row == 0 and d_col == 0:
                    continue
                n_row = entry.row + d_row
                n_col = entry.col_index + d_col
                if n_row < 1 or n_col < 1:
                    continue
                if n_col > 26:
                    continue
                coord = format_coord(n_col, n_row)
                if coord in self._coord_to_key:
                    result.append(self._entries[self._coord_to_key[coord]])

        if not result:
            raise ValueError(f"Cell {entry.coord} has no registered neighbors")
        result.sort(key=lambda e: (e.row or 0, e.col_index or 0, e.key))
        return [e.key for e in result]

    def decode_model(self, model: dict[int, bool]) -> dict[str, str]:
        """Extract only primary character verdicts ('CRIMINAL'/'INNOCENT') from a SAT model."""
        verdicts: dict[str, str] = {}
        for key, var_id in self._char_to_var.items():
            if var_id not in model:
                raise KeyError(f"Primary variable {var_id} ({key}) missing from model")
            verdicts[key] = "CRIMINAL" if bool(model[var_id]) else "INNOCENT"
        return verdicts
