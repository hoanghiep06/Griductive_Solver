import copy
import itertools
import json
import unittest
from pathlib import Path

from src.core.puzzle_loader import PuzzleLoader
from src.core.puzzle_validator import PuzzleValidationError, PuzzleValidator


PUZZLE_PATH = Path(__file__).resolve().parents[1] / "puzzles" / "sample_3x3.json"


class PuzzleValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with PUZZLE_PATH.open(encoding="utf-8") as file:
            cls.raw = json.load(file)
        cls.puzzle = PuzzleValidator().validate(cls.raw)

    def test_sample_loads_and_every_clue_matches_hidden_solution(self):
        loaded = PuzzleLoader().load(PUZZLE_PATH)
        self.assertEqual(loaded.puzzle_id, "griductive_3x3_01")
        self.assertEqual(len(loaded.characters), 9)
        self.assertEqual(len(loaded.clues), 9)

    def test_sample_has_exactly_one_complete_assignment(self):
        validator = PuzzleValidator()
        chars = self.puzzle.characters_by_id
        clue_count = 0
        ids = sorted(self.puzzle.hidden_solution)
        satisfying_assignments = []
        for values in itertools.product((False, True), repeat=len(ids)):
            assignment = dict(zip(ids, values))
            if all(
                validator.evaluate_clue(clue, assignment, chars, self.puzzle.grid_size)
                for clue in self.puzzle.clues
            ):
                satisfying_assignments.append(assignment)
                clue_count += 1
        self.assertEqual(clue_count, 1)
        self.assertEqual(satisfying_assignments[0], dict(self.puzzle.hidden_solution))

    def test_sample_is_sequentially_solvable_without_guessing(self):
        report = PuzzleValidator().analyze_sequential_solvability(self.puzzle)
        self.assertEqual(report.status.value, "SOLVED")
        self.assertTrue(report.is_solvable)
        self.assertEqual(
            [step.character_id for step in report.steps],
            ["B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"],
        )
        self.assertEqual(report.initial_model_count, 128)
        self.assertEqual(report.remaining_model_count, 1)
        self.assertEqual(report.unresolved_character_ids, ())

    def test_sequential_checker_detects_the_previous_stuck_sample(self):
        stuck_path = Path(__file__).resolve().parent / "fixtures" / "sample_3x3_sequential_stuck.json"
        stuck_puzzle = PuzzleLoader().load(stuck_path)
        report = PuzzleValidator().analyze_sequential_solvability(stuck_puzzle)
        self.assertEqual(report.status.value, "STUCK")
        self.assertEqual(
            [step.character_id for step in report.steps],
            ["A2", "B1", "B2"],
        )
        self.assertEqual(report.remaining_model_count, 26)
        self.assertEqual(
            report.unresolved_character_ids,
            ("C1", "C2", "A3", "B3", "C3"),
        )

    def test_sequential_checker_refuses_large_exhaustive_run_by_default(self):
        report = PuzzleValidator().analyze_sequential_solvability(
            self.puzzle, max_characters=8
        )
        self.assertEqual(report.status.value, "TOO_LARGE")
        self.assertIsNone(report.is_solvable)

    def test_legacy_clue_dictionary_format_remains_readable(self):
        legacy = copy.deepcopy(self.raw)
        legacy.pop("schema_version")
        legacy["clues"] = {
            clue["owner_id"]: {"type": clue["type"], **clue["parameters"]}
            for clue in legacy["clues"]
        }
        puzzle = PuzzleValidator().validate(legacy)
        self.assertEqual(len(puzzle.clues), 9)
        self.assertEqual(puzzle.clues_by_owner["A1"].clue_id, "CLUE_A1")

    def test_missing_character_is_rejected(self):
        data = copy.deepcopy(self.raw)
        data["characters"].pop()
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_duplicate_coordinate_is_rejected(self):
        data = copy.deepcopy(self.raw)
        data["characters"][1]["row"] = 0
        data["characters"][1]["col"] = 0
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_hidden_solution_must_be_boolean_and_complete(self):
        data = copy.deepcopy(self.raw)
        data["hidden_solution"]["A1"] = 1
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)
        data = copy.deepcopy(self.raw)
        del data["hidden_solution"]["A1"]
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_unknown_clue_reference_is_rejected(self):
        data = copy.deepcopy(self.raw)
        data["clues"][0]["parameters"]["target"] = "Z9"
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_count_outside_region_size_is_rejected(self):
        data = copy.deepcopy(self.raw)
        data["clues"][2]["parameters"]["k"] = 4
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_explicit_region_duplicate_is_rejected(self):
        data = copy.deepcopy(self.raw)
        data["clues"][8]["parameters"]["cells"] = ["C1", "C1", "C3"]
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_false_clue_under_hidden_solution_is_rejected(self):
        data = copy.deepcopy(self.raw)
        data["clues"][0]["parameters"]["status"] = "INNOCENT"
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

    def test_extension_clue_requires_and_uses_registered_evaluator(self):
        data = copy.deepcopy(self.raw)
        data["clues"][0] = {
            "clue_id": "CLUE_A1", "owner_id": "A1", "type": "EXTENSION_TEST",
            "parameters": {"target": "B1"},
        }
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)

        def evaluator(clue, characters, grid_size, assignment):
            return assignment[clue.parameters["target"]] is True

        puzzle = PuzzleValidator({"EXTENSION_TEST": evaluator}).validate(data)
        self.assertEqual(puzzle.clues_by_owner["A1"].clue_type, "EXTENSION_TEST")

    def test_unexpected_parameters_are_rejected(self):
        data = copy.deepcopy(self.raw)
        data["clues"][0]["parameters"]["typo"] = 123
        with self.assertRaises(PuzzleValidationError):
            PuzzleValidator().validate(data)


if __name__ == "__main__":
    unittest.main()
