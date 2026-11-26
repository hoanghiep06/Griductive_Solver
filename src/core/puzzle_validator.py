"""Validation and normalization for Griductive puzzle JSON schema v1.0."""

from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional

from src.core.character import Character
from src.core.clue import Clue
from src.core.puzzle import Puzzle
from src.core.regions import SPATIAL_REGIONS, in_spatial_region

if TYPE_CHECKING:
    from src.core.sequential_solvability import SequentialSolvabilityReport


class PuzzleValidationError(ValueError):
    """Raised when puzzle data violates the documented schema or semantics."""


ExtensionEvaluator = Callable[[Clue, Mapping[str, Character], int, Mapping[str, bool]], bool]


class PuzzleValidator:
    """Validate a puzzle before it is allowed into GameEngine.

    The six required core clue templates are validated and semantically
    evaluated here. Counting clues accept ROW / COLUMN / NEIGHBORS / EXPLICIT
    plus ALL (global rule over the whole board) and PROFESSION (an explicit
    ``cells`` list that must equal exactly the characters of that profession).
    PARITY, COUNT_COMPARE and IMPLIES are built-in extensions; further types
    can be registered by passing ``extension_evaluators``.
    """

    CORE_CLUE_TYPES = {"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST"}
    SUPPORTED_REGION_TYPES = {"ROW", "COLUMN", "NEIGHBORS", "EXPLICIT", "ALL", "PROFESSION"} | SPATIAL_REGIONS
    SUPPORTED_GRID_SIZES = {3, 4, 5}

    def __init__(self, extension_evaluators: Optional[Mapping[str, ExtensionEvaluator]] = None):
        self._extension_evaluators = {
            "PARITY": self._evaluate_extended,
            "COUNT_COMPARE": self._evaluate_extended,
            "IMPLIES": self._evaluate_extended,
        }
        for key, evaluator in (extension_evaluators or {}).items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Extension clue type names must be non-empty strings")
            if not callable(evaluator):
                raise TypeError(f"Extension evaluator for {key!r} must be callable")
            self._extension_evaluators[key.strip().upper()] = evaluator

    def validate(self, data: Mapping[str, Any]) -> Puzzle:
        if not isinstance(data, Mapping):
            raise PuzzleValidationError("$: puzzle root must be a JSON object")

        schema_version = data.get("schema_version", "1.0")
        if schema_version != "1.0":
            raise PuzzleValidationError(
                f"schema_version: unsupported version {schema_version!r}; expected '1.0'"
            )

        puzzle_id = self._require_non_empty_string(data, "puzzle_id", "$")
        grid_size = data.get("grid_size")
        if type(grid_size) is not int or grid_size not in self.SUPPORTED_GRID_SIZES:
            raise PuzzleValidationError("grid_size: expected integer 3, 4, or 5")

        raw_characters = data.get("characters")
        if not isinstance(raw_characters, list):
            raise PuzzleValidationError("characters: expected a JSON array")
        expected_count = grid_size * grid_size
        if len(raw_characters) != expected_count:
            raise PuzzleValidationError(
                f"characters: expected exactly {expected_count} entries for a {grid_size}x{grid_size} grid; "
                f"got {len(raw_characters)}"
            )

        characters: list[Character] = []
        character_ids: set[str] = set()
        occupied_cells: set[tuple[int, int]] = set()
        for index, raw_character in enumerate(raw_characters):
            path = f"characters[{index}]"
            if not isinstance(raw_character, Mapping):
                raise PuzzleValidationError(f"{path}: expected an object")
            expected_character_fields = {"id", "name", "profession", "row", "col"}
            if set(raw_character) != expected_character_fields:
                raise PuzzleValidationError(
                    f"{path}: expected fields {sorted(expected_character_fields)}; "
                    f"got {sorted(raw_character)}"
                )
            try:
                character = Character.from_dict(dict(raw_character))
            except (KeyError, TypeError, ValueError) as exc:
                raise PuzzleValidationError(f"{path}: invalid character: {exc}") from exc
            if character.id in character_ids:
                raise PuzzleValidationError(f"{path}.id: duplicate character ID {character.id!r}")
            character_ids.add(character.id)
            if character.row >= grid_size or character.col >= grid_size:
                raise PuzzleValidationError(
                    f"{path}: coordinates ({character.row}, {character.col}) are outside the grid"
                )
            cell = (character.row, character.col)
            if cell in occupied_cells:
                raise PuzzleValidationError(f"{path}: more than one character occupies cell {cell}")
            occupied_cells.add(cell)
            characters.append(character)

        if len(occupied_cells) != expected_count:
            raise PuzzleValidationError("characters: every grid cell must contain exactly one character")
        characters_by_id = {character.id: character for character in characters}

        raw_solution = data.get("hidden_solution")
        if not isinstance(raw_solution, Mapping):
            raise PuzzleValidationError("hidden_solution: expected a JSON object")
        solution_ids = set(raw_solution.keys())
        if solution_ids != character_ids:
            missing = sorted(character_ids - solution_ids)
            unknown = sorted(solution_ids - character_ids)
            details = []
            if missing:
                details.append(f"missing IDs: {missing}")
            if unknown:
                details.append(f"unknown IDs: {unknown}")
            raise PuzzleValidationError("hidden_solution: must contain exactly one entry per character (" + "; ".join(details) + ")")
        hidden_solution: dict[str, bool] = {}
        for char_id, status in raw_solution.items():
            if type(status) is not bool:
                raise PuzzleValidationError(
                    f"hidden_solution.{char_id}: expected JSON boolean true/false"
                )
            hidden_solution[str(char_id)] = status

        clues = self._parse_clues(data.get("clues"), character_ids)
        if len(clues) != expected_count:
            raise PuzzleValidationError(
                f"clues: expected exactly one clue per character ({expected_count}); got {len(clues)}"
            )
        clue_ids: set[str] = set()
        clue_owners: set[str] = set()
        for index, clue in enumerate(clues):
            path = f"clues[{index}]"
            if clue.clue_id in clue_ids:
                raise PuzzleValidationError(f"{path}: duplicate clue_id {clue.clue_id!r}")
            clue_ids.add(clue.clue_id)
            if clue.owner_id not in character_ids:
                raise PuzzleValidationError(f"{path}.owner_id: unknown character {clue.owner_id!r}")
            if clue.owner_id in clue_owners:
                raise PuzzleValidationError(f"{path}: character {clue.owner_id!r} owns more than one clue")
            clue_owners.add(clue.owner_id)
            self._validate_clue(clue, characters_by_id, grid_size, path)

        missing_clues = sorted(character_ids - clue_owners)
        if missing_clues:
            raise PuzzleValidationError(f"clues: missing clue for characters {missing_clues}")

        raw_initial = data.get("initial_revealed", [])
        if not isinstance(raw_initial, list):
            raise PuzzleValidationError("initial_revealed: expected a JSON array")
        initial_revealed: list[str] = []
        seen_initial: set[str] = set()
        for index, char_id in enumerate(raw_initial):
            if not isinstance(char_id, str) or char_id not in character_ids:
                raise PuzzleValidationError(f"initial_revealed[{index}]: unknown character ID {char_id!r}")
            if char_id in seen_initial:
                raise PuzzleValidationError(f"initial_revealed[{index}]: duplicate character ID {char_id!r}")
            seen_initial.add(char_id)
            initial_revealed.append(char_id)

        # Hidden labels are private runtime data, but puzzle files must be
        # internally coherent: every clue must be true under the supplied key.
        for clue in clues:
            try:
                is_true = self.evaluate_clue(clue, hidden_solution, characters_by_id, grid_size)
            except Exception as exc:
                raise PuzzleValidationError(
                    f"clue {clue.clue_id!r}: semantic evaluation failed: {exc}"
                ) from exc
            if not is_true:
                raise PuzzleValidationError(
                    f"clue {clue.clue_id!r} (owner {clue.owner_id!r}) is false under hidden_solution"
                )

        return Puzzle(
            puzzle_id=puzzle_id,
            grid_size=grid_size,
            characters=tuple(characters),
            hidden_solution=hidden_solution,
            initial_revealed=tuple(initial_revealed),
            clues=tuple(clues),
            schema_version=schema_version,
        )

    def _parse_clues(self, raw_clues: Any, character_ids: set[str]) -> list[Clue]:
        if isinstance(raw_clues, list):
            entries = raw_clues
            parsed: list[Clue] = []
            for index, item in enumerate(entries):
                if not isinstance(item, Mapping):
                    raise PuzzleValidationError(f"clues[{index}]: expected an object")
                try:
                    parsed.append(Clue.from_dict(item))
                except (KeyError, TypeError, ValueError) as exc:
                    raise PuzzleValidationError(f"clues[{index}]: invalid clue: {exc}") from exc
            return parsed

        # Backward-compatible reader for the original TV1 dictionary format.
        # New puzzle files should use the explicit list format with clue_id.
        if isinstance(raw_clues, Mapping):
            parsed = []
            for owner_id, item in raw_clues.items():
                if not isinstance(owner_id, str) or not isinstance(item, Mapping):
                    raise PuzzleValidationError("clues: legacy format must map owner IDs to clue objects")
                if owner_id not in character_ids:
                    raise PuzzleValidationError(f"clues.{owner_id}: unknown clue owner")
                clue_type = item.get("type")
                parameters = {key: value for key, value in item.items() if key != "type"}
                try:
                    parsed.append(
                        Clue(
                            clue_id=f"CLUE_{owner_id}",
                            owner_id=owner_id,
                            clue_type=clue_type,
                            parameters=parameters,
                        )
                    )
                except (TypeError, ValueError) as exc:
                    raise PuzzleValidationError(f"clues.{owner_id}: invalid clue: {exc}") from exc
            return parsed

        raise PuzzleValidationError("clues: expected an array (schema v1.0) or legacy object")

    def _validate_clue(
        self,
        clue: Clue,
        characters: Mapping[str, Character],
        grid_size: int,
        path: str,
    ) -> None:
        clue_type = clue.clue_type
        params = clue.parameters
        if clue_type in self.CORE_CLUE_TYPES:
            if clue_type == "FACT":
                self._require_exact_parameter_keys(params, {"target", "status"}, path)
                self._require_reference(params, "target", characters, path)
                status = params.get("status")
                if status not in ("CRIMINAL", "INNOCENT"):
                    raise PuzzleValidationError(f"{path}.parameters.status: expected CRIMINAL or INNOCENT")
                return

            if clue_type in {"SAME", "DIFFERENT"}:
                self._require_exact_parameter_keys(params, {"target1", "target2"}, path)
                self._require_reference(params, "target1", characters, path)
                self._require_reference(params, "target2", characters, path)
                return

            if clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
                k = params.get("k")
                if type(k) is not int or k < 0:
                    raise PuzzleValidationError(f"{path}.parameters.k: expected a non-negative integer")
                region_type = params.get("region_type")
                if not isinstance(region_type, str):
                    raise PuzzleValidationError(f"{path}.parameters.region_type: expected a string")
                if region_type != region_type.upper():
                    raise PuzzleValidationError(
                        f"{path}.parameters.region_type: use uppercase canonical values"
                    )
                if region_type not in self.SUPPORTED_REGION_TYPES:
                    raise PuzzleValidationError(
                        f"{path}.parameters.region_type: unsupported region {region_type!r}"
                    )

                required_region_keys = {
                    "ROW": {"index"},
                    "COLUMN": {"index"},
                    "NEIGHBORS": {"center"},
                    "EXPLICIT": {"cells"},
                    "ALL": set(),
                    "PROFESSION": {"profession", "cells"},
                    **{kind: set() for kind in SPATIAL_REGIONS},
                }[region_type]
                self._require_exact_parameter_keys(
                    params, {"k", "region_type"} | required_region_keys, path
                )
                region_ids = self._resolve_region_ids(
                    region_type, params, characters, grid_size, path
                )
                if k > len(region_ids):
                    raise PuzzleValidationError(
                        f"{path}.parameters.k: {k} exceeds region size {len(region_ids)}"
                    )
                return

        extension_evaluator = self._extension_evaluators.get(clue_type)
        if extension_evaluator is None:
            raise PuzzleValidationError(
                f"{path}.type: unsupported clue type {clue_type!r}; "
                "register an extension evaluator before loading this puzzle"
            )
        # Extension evaluators are called on the complete hidden assignment
        # below and are responsible for validating their own parameter schema.
        if not isinstance(params, Mapping):
            raise PuzzleValidationError(f"{path}.parameters: expected an object")

    @staticmethod
    def _require_exact_parameter_keys(
        params: Mapping[str, Any], expected: set[str], path: str
    ) -> None:
        actual = set(params)
        missing = expected - actual
        unknown = actual - expected
        if missing or unknown:
            raise PuzzleValidationError(
                f"{path}.parameters: expected keys {sorted(expected)}; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )

    @staticmethod
    def _require_non_empty_string(data: Mapping[str, Any], key: str, path: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PuzzleValidationError(f"{path}.{key}: expected a non-empty string")
        return value.strip()

    @staticmethod
    def _require_reference(
        params: Mapping[str, Any], key: str, characters: Mapping[str, Character], path: str
    ) -> str:
        value = params.get(key)
        if not isinstance(value, str) or value not in characters:
            raise PuzzleValidationError(f"{path}.parameters.{key}: unknown character ID {value!r}")
        return value

    def _resolve_region_ids(
        self,
        region_type: str,
        params: Mapping[str, Any],
        characters: Mapping[str, Character],
        grid_size: int,
        path: str,
    ) -> tuple[str, ...]:
        if region_type == "ALL":
            return tuple(characters)

        if region_type in SPATIAL_REGIONS:
            return tuple(c.id for c in characters.values()
                         if in_spatial_region(region_type, c.row, c.col, grid_size))

        if region_type == "PROFESSION":
            profession = params.get("profession")
            if not isinstance(profession, str) or not profession.strip():
                raise PuzzleValidationError(
                    f"{path}.parameters.profession: expected a non-empty string"
                )
            cells = params.get("cells")
            if not isinstance(cells, (list, tuple)):
                raise PuzzleValidationError(f"{path}.parameters.cells: expected an array of character IDs")
            if any(not isinstance(cell_id, str) or cell_id not in characters for cell_id in cells):
                raise PuzzleValidationError(f"{path}.parameters.cells: contains an unknown character ID")
            if len(set(cells)) != len(cells):
                raise PuzzleValidationError(f"{path}.parameters.cells: must contain distinct IDs")
            wanted = profession.strip().casefold()
            expected_ids = {
                c.id for c in characters.values() if c.profession.strip().casefold() == wanted
            }
            if not expected_ids:
                raise PuzzleValidationError(
                    f"{path}.parameters.profession: no character has profession {profession!r}"
                )
            if set(cells) != expected_ids:
                raise PuzzleValidationError(
                    f"{path}.parameters.cells: must list exactly the characters with profession "
                    f"{profession!r} ({sorted(expected_ids)}); got {sorted(cells)}"
                )
            return tuple(cells)

        if region_type in {"ROW", "COLUMN"}:
            index = params.get("index")
            if type(index) is not int or not 0 <= index < grid_size:
                raise PuzzleValidationError(
                    f"{path}.parameters.index: expected a zero-based index from 0 to {grid_size - 1}"
                )
            if region_type == "ROW":
                return tuple(c.id for c in characters.values() if c.row == index)
            return tuple(c.id for c in characters.values() if c.col == index)

        if region_type == "NEIGHBORS":
            center_id = self._require_reference(params, "center", characters, path)
            center = characters[center_id]
            return tuple(
                c.id
                for c in characters.values()
                if c.id != center_id
                and abs(c.row - center.row) <= 1
                and abs(c.col - center.col) <= 1
            )

        cells = params.get("cells")
        if not isinstance(cells, (list, tuple)):
            raise PuzzleValidationError(f"{path}.parameters.cells: expected an array of character IDs")
        if any(not isinstance(cell_id, str) or cell_id not in characters for cell_id in cells):
            raise PuzzleValidationError(f"{path}.parameters.cells: contains an unknown character ID")
        if len(set(cells)) != len(cells):
            raise PuzzleValidationError(f"{path}.parameters.cells: explicit regions must contain distinct IDs")
        return tuple(cells)

    def analyze_sequential_solvability(
        self, puzzle: Puzzle, *, max_characters: int = 9
    ) -> "SequentialSolvabilityReport":
        """Exhaustively analyze no-guess card-by-card solvability for small puzzles.

        This is an authoring/test utility, not the production Logic Agent. By
        default it enumerates at most 2**9 assignments; larger puzzles return
        TOO_LARGE unless the caller explicitly raises the limit.
        """
        from src.core.sequential_solvability import SequentialSolvabilityChecker

        if not isinstance(puzzle, Puzzle):
            raise TypeError("puzzle must be a validated Puzzle instance")
        return SequentialSolvabilityChecker(self).analyze(
            puzzle, max_characters=max_characters
        )

    def evaluate_clue(
        self,
        clue: Clue,
        assignment: Mapping[str, bool],
        characters: Mapping[str, Character],
        grid_size: int,
    ) -> bool:
        """Direct semantic evaluator; deliberately does not call a CNF encoder."""
        clue_type = clue.clue_type
        params = clue.parameters
        if clue_type == "FACT":
            expected = params["status"] == "CRIMINAL"
            return assignment[params["target"]] is expected
        if clue_type == "SAME":
            return assignment[params["target1"]] == assignment[params["target2"]]
        if clue_type == "DIFFERENT":
            return assignment[params["target1"]] != assignment[params["target2"]]

        if clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
            region_type = str(params["region_type"]).upper()
            region_ids = self._resolve_region_ids(region_type, params, characters, grid_size, clue.clue_id)
            count = sum(1 for char_id in region_ids if assignment[char_id])
            k = params["k"]
            if clue_type == "EXACTLY":
                return count == k
            if clue_type == "AT_LEAST":
                return count >= k
            return count <= k

        evaluator = self._extension_evaluators[clue_type]
        result = evaluator(clue, characters, grid_size, assignment)
        if type(result) is not bool:
            raise TypeError(f"Extension evaluator for {clue_type} must return bool")
        return result

    @staticmethod
    def _evaluate_extended(clue, characters, grid_size, assignment):
        from src.encoder.semantic_eval import evaluate_clue, normalize_cells
        from src.core.clue import _thaw
        params = _thaw(clue.parameters)
        board = {(c.row, c.col): assignment[c.id] for c in characters.values() if c.id in assignment}

        if clue.clue_type == "IMPLIES":
            if set(params) != {"antecedent", "consequent"}:
                raise ValueError(f"{clue.clue_id}: expected parameters ['antecedent', 'consequent']")
            resolved = {}
            for field in ("antecedent", "consequent"):
                spec = params[field]
                if not isinstance(spec, dict) or set(spec) != {"target", "status"}:
                    raise ValueError(f"{clue.clue_id}: {field} must have exactly 'target' and 'status'")
                target = spec["target"]
                if not isinstance(target, str) or target not in characters:
                    raise ValueError(f"{clue.clue_id}: {field}.target unknown character {target!r}")
                if spec["status"] not in ("CRIMINAL", "INNOCENT"):
                    raise ValueError(f"{clue.clue_id}: {field}.status must be CRIMINAL or INNOCENT")
                ch = characters[target]
                resolved[field] = {"target": (ch.row, ch.col), "status": spec["status"]}
            if params["antecedent"]["target"] == params["consequent"]["target"]:
                raise ValueError(f"{clue.clue_id}: IMPLIES needs two distinct cells")
            return evaluate_clue({"type": "IMPLIES", "params": resolved}, board)

        expected = {"cells", "parity"} if clue.clue_type == "PARITY" else {"region_a", "region_b", "op"}
        if set(params) != expected:
            raise ValueError(f"{clue.clue_id}: expected parameters {sorted(expected)}")
        fields = ("cells",) if clue.clue_type == "PARITY" else ("region_a", "region_b")
        for field in fields:
            params[field] = [
                (characters[cell].row, characters[cell].col) if isinstance(cell, str) and cell in characters else cell
                for cell in params[field]
            ]
            for row, col in normalize_cells(params[field]):
                if row >= grid_size or col >= grid_size:
                    raise ValueError(f"{clue.clue_id}: cell outside grid")
        return evaluate_clue({"type": clue.clue_type, "params": params}, board)
