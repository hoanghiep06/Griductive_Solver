import unittest
from pathlib import Path

from src.core.clue import Clue
from src.core.game_engine import GameEngine
from src.core.public_kb import KnowledgeBaseConflictError, PublicKB


PUZZLE = Path(__file__).resolve().parents[1] / "puzzles" / "sample_3x3.json"


class PublicKBTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(PUZZLE)
        self.kb = PublicKB(self.engine.var_map)

    def test_verdicts_become_correct_unit_clauses(self):
        self.kb.add_proved_verdict("A1", True)
        self.kb.add_proved_verdict("B1", False)
        self.assertEqual(self.kb.get_unit_clauses_for_verdicts(), [[1], [-2]])

    def test_conflicting_verdict_is_rejected_and_identical_is_idempotent(self):
        self.assertTrue(self.kb.add_proved_verdict("A1", True))
        self.assertFalse(self.kb.add_proved_verdict("A1", True))
        with self.assertRaises(KnowledgeBaseConflictError):
            self.kb.add_proved_verdict("A1", False)
        self.assertEqual(self.kb.get_status("A1"), True)

    def test_duplicate_clue_is_idempotent_but_conflicting_id_is_rejected(self):
        self.kb.add_proved_verdict("A1", False)
        clue = Clue("CLUE_A1", "A1", "FACT", {"target": "A2", "status": "CRIMINAL"})
        self.assertTrue(self.kb.add_revealed_clue(clue))
        self.assertFalse(self.kb.add_revealed_clue(clue))
        conflicting = Clue("CLUE_A1", "A1", "FACT", {"target": "A3", "status": "CRIMINAL"})
        with self.assertRaises(KnowledgeBaseConflictError):
            self.kb.add_revealed_clue(conflicting)

    def test_exposed_collections_are_detached(self):
        self.kb.add_proved_verdict("A1", False)
        self.kb.add_revealed_clue(
            Clue("CLUE_A1", "A1", "FACT", {"target": "A2", "status": "CRIMINAL"})
        )
        verdicts = self.kb.proved_verdicts
        verdicts["A1"] = True
        clues = self.kb.revealed_clues
        self.assertIsInstance(clues, tuple)
        self.assertEqual(len(clues), 1)
        self.assertFalse(self.kb.get_status("A1"))
        self.assertEqual(len(self.kb.revealed_clues), 1)

    def test_record_reveal_is_atomic_and_increments_version_once(self):
        clue = Clue("CLUE_A1", "A1", "FACT", {"target": "B1", "status": "CRIMINAL"})
        self.assertEqual(self.kb.version, 0)
        self.assertTrue(self.kb.record_reveal("A1", False, clue))
        self.assertEqual(self.kb.version, 1)
        self.assertEqual(self.kb.get_status("A1"), False)
        self.assertEqual(self.kb.get_revealed_clue("CLUE_A1"), clue)
        self.assertFalse(self.kb.record_reveal("A1", False, clue))
        self.assertEqual(self.kb.version, 1)

    def test_record_reveal_rejects_bad_owner_without_partial_update(self):
        clue = Clue("CLUE_B1", "B1", "FACT", {"target": "C1", "status": "CRIMINAL"})
        with self.assertRaises(ValueError):
            self.kb.record_reveal("A1", False, clue)
        self.assertEqual(self.kb.version, 0)
        self.assertFalse(self.kb.is_proved("A1"))

    def test_snapshot_is_read_only_and_clone_preserves_version(self):
        self.kb.add_proved_verdict("A1", False)
        self.kb.add_revealed_clue(
            Clue("CLUE_A1", "A1", "FACT", {"target": "A2", "status": "CRIMINAL"})
        )
        snapshot = self.kb.get_snapshot()
        with self.assertRaises(TypeError):
            snapshot.proved_verdicts["A1"] = True
        with self.assertRaises(TypeError):
            snapshot.revealed_clues[0].parameters["target"] = "A3"
        self.kb.add_proved_verdict("A1", False)
        clone = self.kb.clone()
        self.assertEqual(clone.version, self.kb.version)
        self.assertEqual(clone.proved_verdicts, self.kb.proved_verdicts)

    def test_clue_cannot_be_revealed_before_its_owner_is_proved(self):
        clue = Clue("CLUE_A1", "A1", "FACT", {"target": "A2", "status": "CRIMINAL"})
        with self.assertRaises(ValueError):
            self.kb.add_revealed_clue(clue)

    def test_snapshot_contains_unit_clauses(self):
        self.kb.add_proved_verdict("A1", True)
        self.kb.add_proved_verdict("B1", False)
        self.assertEqual(self.kb.get_snapshot().get_unit_clauses_for_verdicts(), [[1], [-2]])

    def test_unknown_character_is_rejected(self):
        with self.assertRaises(KeyError):
            self.kb.add_proved_verdict("NOT_A_CHARACTER", True)


if __name__ == "__main__":
    unittest.main()
