"""Deterministic mapping between Griductive characters and SAT variables.

Primary variables C_i are assigned consecutive positive integers starting at 1
(1 .. num_primary), ordered deterministically (alphabetically by display name
when names are present, or in row-major coordinate order otherwise).

Auxiliary variables used by CNF encodings (such as sequential cardinality
counters) are allocated strictly after all primary variables so primary and
auxiliary namespaces never collide.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

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
    """Deterministic bijection for primary variables C_i and separate auxiliary variables."""

    def __init__(
        self,
        characters: Iterable[Any] | dict[str, Any] | None = None,
        grid_size: int | tuple[int, int] | None = None,
    ) -> None:
        self._grid_size: tuple[int, int] | None = _parse_grid_size(grid_size)
        self._primary_by_key: dict[str, int] = {}
        self._entries: dict[str, CharacterEntry] = {}
        self._aliases: dict[str, str] = {}
        self._id_to_primary: dict[int, str] = {}
        self._coord_to_key: dict[str, str] = {}
        self._aux_by_id: dict[int, str] = {}
        self._aux_locked_primary: bool = False
        self._next_id: int = 1

        if characters is not None:
            self.register_characters(characters)

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

    def register_characters(self, characters: Iterable[Any] | dict[str, Any]) -> None:
        """Register characters deterministically before any auxiliary variables exist."""
        if self._aux_locked_primary:
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
            self._register_single_entry(entry)

    def _register_single_entry(self, entry: CharacterEntry) -> None:
        """Add one primary variable entry and register lookup aliases."""
        if entry.key in self._primary_by_key or entry.name.casefold() in self._aliases:
            raise ValueError(f"Duplicate character name/key: {entry.key!r}")
        if entry.coord is not None and entry.coord in self._coord_to_key:
            raise ValueError(f"Duplicate grid coordinate: {entry.coord!r}")

        var_id = self._next_id
        self._next_id += 1
        self._primary_by_key[entry.key] = var_id
        self._entries[entry.key] = entry
        self._id_to_primary[var_id] = entry.key
        self._aliases[entry.key.casefold()] = entry.key
        if entry.coord is not None:
            self._coord_to_key[entry.coord] = entry.key
            self._aliases[entry.coord.casefold()] = entry.key

    def resolve_canonical(self, identifier: str) -> str:
        """Resolve a character name or grid coordinate to its canonical key."""
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"Character identifier must be a non-empty string, got {identifier!r}")
        cleaned = identifier.strip()
        if cleaned in self._primary_by_key:
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
        return self._primary_by_key[canonical]

    def get_entry(self, identifier: str) -> CharacterEntry:
        """Return the CharacterEntry metadata for the given character/cell."""
        canonical = self.resolve_canonical(identifier)
        return self._entries[canonical]

    def allocate_aux(self, tag: str = "") -> int:
        """Allocate a fresh auxiliary variable ID strictly separate from primary variables."""
        self._aux_locked_primary = True
        var_id = self._next_id
        self._next_id += 1
        self._aux_by_id[var_id] = tag.strip() if tag and tag.strip() else f"aux_{var_id}"
        return var_id

    def reset_auxiliary(self) -> None:
        """Remove all allocated auxiliary variables while keeping primary variables intact."""
        self._aux_by_id.clear()
        self._aux_locked_primary = False
        self._next_id = len(self._primary_by_key) + 1

    def is_primary(self, literal_or_var: int) -> bool:
        """Return True iff abs(literal_or_var) is a primary variable."""
        return abs(literal_or_var) in self._id_to_primary

    def is_auxiliary(self, literal_or_var: int) -> bool:
        """Return True iff abs(literal_or_var) is an auxiliary variable."""
        return abs(literal_or_var) in self._aux_by_id

    def label_of(self, literal_or_var: int) -> str:
        """Return a human-readable label for a variable ID or signed literal."""
        if literal_or_var == 0:
            raise ValueError("DIMACS variable/literal ID cannot be 0")
        sign = "~" if literal_or_var < 0 else ""
        var_id = abs(literal_or_var)
        if var_id in self._id_to_primary:
            return f"{sign}C[{self._id_to_primary[var_id]}]"
        if var_id in self._aux_by_id:
            return f"{sign}AUX[{var_id}:{self._aux_by_id[var_id]}]"
        raise KeyError(f"Unknown variable ID: {var_id}")

    @property
    def num_primary(self) -> int:
        return len(self._primary_by_key)

    @property
    def num_auxiliary(self) -> int:
        return len(self._aux_by_id)

    @property
    def total_vars(self) -> int:
        return self.num_primary + self.num_auxiliary

    @property
    def primary_ids(self) -> list[int]:
        return sorted(self._id_to_primary.keys())

    @property
    def auxiliary_ids(self) -> list[int]:
        return sorted(self._aux_by_id.keys())

    @property
    def primary_map(self) -> dict[str, int]:
        return dict(self._primary_by_key)

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
        for key, var_id in self._primary_by_key.items():
            if var_id not in model:
                raise KeyError(f"Primary variable {var_id} ({key}) missing from model")
            verdicts[key] = "CRIMINAL" if bool(model[var_id]) else "INNOCENT"
        return verdicts
