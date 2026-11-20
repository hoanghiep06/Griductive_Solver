"""JSON file loader for validated Griductive puzzles."""

import json
from pathlib import Path
from typing import Optional

from src.core.puzzle import Puzzle
from src.core.puzzle_validator import PuzzleValidator, PuzzleValidationError


class PuzzleLoadError(RuntimeError):
    """Raised when a puzzle file cannot be read or parsed."""


class PuzzleLoader:
    def __init__(self, validator: Optional[PuzzleValidator] = None):
        self.validator = validator or PuzzleValidator()

    def load(self, path: str | Path) -> Puzzle:
        puzzle_path = Path(path)
        try:
            with puzzle_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError as exc:
            raise PuzzleLoadError(f"Puzzle file not found: {puzzle_path}") from exc
        except json.JSONDecodeError as exc:
            raise PuzzleLoadError(
                f"Invalid JSON in {puzzle_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        except OSError as exc:
            raise PuzzleLoadError(f"Cannot read puzzle file {puzzle_path}: {exc}") from exc

        try:
            return self.validator.validate(data)
        except PuzzleValidationError as exc:
            raise PuzzleLoadError(f"Invalid puzzle {puzzle_path}: {exc}") from exc
