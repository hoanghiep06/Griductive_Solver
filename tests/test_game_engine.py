import unittest
from pathlib import Path

from src.core.entailment_result import EntailmentResult
from src.core.game_engine import GameEngine, GameEngineIntegrityError, VerdictResponse


PUZZLE = Path(__file__).resolve().parents[1] / "puzzles" / "sample_3x3.json"


def forced_result(engine, char_id, status):
    # status True => C_i forced; status False => NOT C_i forced.
    return EntailmentResult.from_sat_results(
        character_id=char_id,
        kb_version=engine.public_kb_version,
        kb_satisfiable=True,
        criminal_assumption_satisfiable=status,
        innocent_assumption_satisfiable=not status,
    )


class GameEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(PUZZLE)

    def test_initial_reveals_seed_public_kb_only(self):
        self.assertEqual(self.engine.get_proved_verdicts(), {"A1": False})
        self.assertEqual([c.clue_id for c in self.engine.get_revealed_clues()], ["CLUE_A1"])
        self.assertEqual(self.engine.public_kb_version, 1)
        self.assertIsNone(self.engine.get_clue_for_character("A2"))

    def test_unknown_is_not_provable_for_both_claimed_statuses(self):
        version = self.engine.public_kb_version
        for claimed_status in (True, False):
            result = EntailmentResult.from_sat_results(
                character_id="A3",
                kb_version=version,
                kb_satisfiable=True,
                criminal_assumption_satisfiable=True,
                innocent_assumption_satisfiable=True,
            )
            response, clue = self.engine.submit_verdict("A3", claimed_status, result)
            self.assertEqual(response, VerdictResponse.NOT_PROVABLE)
            self.assertIsNone(clue)
        self.assertEqual(self.engine.public_kb_version, version)
        self.assertNotIn("A3", self.engine.get_proved_verdicts())

    def test_forced_verdict_is_accepted_and_reveals_clue_atomically(self):
        result = forced_result(self.engine, "B1", True)
        response, clue = self.engine.submit_verdict("B1", True, result)
        self.assertEqual(response, VerdictResponse.ACCEPTED)
        self.assertEqual(clue["clue_id"], "CLUE_B1")
        self.assertTrue(self.engine.get_proved_verdicts()["B1"])
        self.assertEqual(self.engine.get_clue_for_character("B1")["clue_id"], "CLUE_B1")
        # One complete reveal (verdict + clue) is one KB transaction/version.
        self.assertEqual(self.engine.public_kb_version, 2)

    def test_opposite_forced_status_is_contradicted_without_state_change(self):
        result = forced_result(self.engine, "B1", True)
        before = self.engine.get_public_state()
        response, clue = self.engine.submit_verdict("B1", False, result)
        self.assertEqual(response, VerdictResponse.CONTRADICTED)
        self.assertIsNone(clue)
        self.assertEqual(self.engine.get_public_state(), before)

    def test_inconsistent_public_kb_has_explicit_response(self):
        result = EntailmentResult.from_sat_results(
            character_id="A2", kb_version=self.engine.public_kb_version,
            kb_satisfiable=False,
        )
        response, clue = self.engine.submit_verdict("A2", True, result)
        self.assertEqual(response, VerdictResponse.INCONSISTENT)
        self.assertIsNone(clue)

    def test_stale_entailment_result_is_rejected(self):
        stale = forced_result(self.engine, "C1", True)
        current = forced_result(self.engine, "B1", True)
        self.assertEqual(self.engine.submit_verdict("B1", True, current)[0], VerdictResponse.ACCEPTED)
        response, clue = self.engine.submit_verdict("C1", True, stale)
        self.assertEqual(response, VerdictResponse.STALE_PROOF)
        self.assertIsNone(clue)

    def test_integrity_guard_rejects_forced_status_conflicting_with_hidden_key(self):
        # A2 is Innocent in the validated puzzle, but fabricate SAT evidence
        # claiming Criminal is forced. The Engine must fail internally before
        # mutating the public state.
        result = forced_result(self.engine, "A2", True)
        before = self.engine.get_public_state()
        with self.assertRaises(GameEngineIntegrityError):
            self.engine.submit_verdict("A2", True, result)
        self.assertEqual(self.engine.get_public_state(), before)

    def test_already_solved_character_is_rejected(self):
        result = EntailmentResult.from_sat_results(
            character_id="A1", kb_version=self.engine.public_kb_version,
            kb_satisfiable=True, criminal_assumption_satisfiable=False,
            innocent_assumption_satisfiable=True,
        )
        self.assertEqual(self.engine.submit_verdict("A1", False, result)[0], VerdictResponse.ALREADY_SOLVED)

    def test_row_major_order_is_independent_of_json_order(self):
        self.assertEqual(
            self.engine.get_unsolved_characters(),
            ["B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"],
        )

    def test_sample_names_are_alphabetical_across_rows(self):
        self.assertEqual(
            [character.name for character in self.engine.characters],
            ["Abel", "Bea", "Clara", "Derek", "Eliza", "Franz", "Grant", "Hannah", "Ivy"],
        )
        self.assertEqual([self.engine.var_map.get_var(cid) for cid in
                          ("A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3")],
                         list(range(1, 10)))

    def test_public_state_does_not_expose_hidden_data_or_unrevealed_clues(self):
        state = self.engine.get_public_state()
        self.assertNotIn("hidden_solution", state)
        self.assertNotIn("clues", state)
        self.assertEqual([c["clue_id"] for c in state["revealed_clues"]], ["CLUE_A1"])

    def test_character_info_is_detached_and_character_is_immutable(self):
        info = self.engine.get_character_info("A1")
        info["name"] = "tampered"
        self.assertEqual(self.engine.get_character_info("A1")["name"], "Abel")
        with self.assertRaises(Exception):
            self.engine.get_character("A1").name = "tampered"

    def test_restart_restores_initial_state_and_keeps_variable_mapping(self):
        mapping_before = dict(self.engine.var_map.primary_mapping)
        stale_result = forced_result(self.engine, "B1", True)
        self.engine.submit_verdict("B1", True, stale_result)
        version_before_restart = self.engine.public_kb_version
        self.engine.restart()
        self.assertEqual(self.engine.get_proved_verdicts(), {"A1": False})
        self.assertIsNone(self.engine.get_clue_for_character("B1"))
        self.assertEqual(dict(self.engine.var_map.primary_mapping), mapping_before)
        self.assertGreater(self.engine.public_kb_version, version_before_restart)
        self.assertEqual(
            self.engine.submit_verdict("B1", True, stale_result)[0],
            VerdictResponse.STALE_PROOF,
        )

    def test_reload_makes_previous_entailment_result_stale(self):
        stale_result = forced_result(self.engine, "B1", True)
        previous_version = self.engine.public_kb_version
        self.engine.load_puzzle(PUZZLE)
        self.assertGreater(self.engine.public_kb_version, previous_version)
        self.assertEqual(
            self.engine.submit_verdict("B1", True, stale_result)[0],
            VerdictResponse.STALE_PROOF,
        )

    def test_entailment_result_requires_consistent_sat_evidence(self):
        from src.core.entailment_result import EntailmentStatus
        with self.assertRaises(ValueError):
            EntailmentResult(
                character_id="A2", status=EntailmentStatus.CRIMINAL,
                kb_version=self.engine.public_kb_version, kb_satisfiable=True,
            )

    def test_bad_input_and_wrong_proof_target_are_rejected(self):
        result = forced_result(self.engine, "A2", True)
        with self.assertRaises(TypeError):
            self.engine.submit_verdict("A2", 1, result)
        with self.assertRaises(ValueError):
            self.engine.submit_verdict("B1", True, result)
        with self.assertRaises(TypeError):
            self.engine.submit_verdict("A2", True, True)
        with self.assertRaises(KeyError):
            self.engine.submit_verdict("UNKNOWN", True, result)

    def test_load_failure_preserves_current_game(self):
        before = self.engine.get_public_state()
        with self.assertRaises(Exception):
            self.engine.load_puzzle(PUZZLE.parent / "does_not_exist.json")
        self.assertEqual(self.engine.get_public_state(), before)


if __name__ == "__main__":
    unittest.main()
