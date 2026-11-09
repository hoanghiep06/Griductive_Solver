import unittest

from src.core.character import Character
from src.core.cnf_types import validate_cnf
from src.core.variable_map import VariableMap


class VariableMapTests(unittest.TestCase):
    def test_bulk_registration_is_deterministic_by_display_name(self):
        characters = [
            Character("X1", "Zoe", "Pilot", 0, 0),
            Character("X2", "abel", "Cook", 0, 1),
            Character("X3", "Abel", "Guard", 0, 2),
        ]
        first = VariableMap()
        second = VariableMap()
        first.register_characters(characters)
        second.register_characters(reversed(characters))
        self.assertEqual(dict(first.primary_mapping), dict(second.primary_mapping))
        self.assertEqual(first.get_var("X2"), 1)
        self.assertEqual(first.get_var("X3"), 2)
        self.assertEqual(first.get_var("X1"), 3)

    def test_freeze_and_auxiliary_variable_lifecycle(self):
        variable_map = VariableMap()
        variable_map.register_character("A1")
        with self.assertRaises(RuntimeError):
            variable_map.allocate_auxiliary_variable()
        variable_map.freeze_primary_variables()
        with self.assertRaises(RuntimeError):
            variable_map.register_character("A2")
        aux_id = variable_map.allocate_auxiliary_variable({"purpose": "cardinality"})
        self.assertEqual(aux_id, 2)
        self.assertIsNone(variable_map.get_char_id(aux_id))
        self.assertEqual(variable_map.get_auxiliary_metadata(aux_id)["purpose"], "cardinality")
        with self.assertRaises(KeyError):
            variable_map.get_char_id(aux_id + 1)
        self.assertEqual(variable_map.auxiliary_count, 1)

    def test_literals_follow_criminal_innocent_convention(self):
        variable_map = VariableMap()
        variable_map.register_character("A1")
        variable_map.freeze_primary_variables()
        self.assertEqual(variable_map.to_literal("A1", True), 1)
        self.assertEqual(variable_map.to_literal("A1", False), -1)
        with self.assertRaises(TypeError):
            variable_map.to_literal("A1", 1)

    def test_duplicate_and_invalid_registration_are_rejected(self):
        variable_map = VariableMap()
        variable_map.register_character("A1")
        with self.assertRaises(ValueError):
            variable_map.register_character("A1")
        with self.assertRaises(ValueError):
            variable_map.register_character("")

    def test_assigned_module_paths_reuse_the_canonical_contract(self):
        from src.core.variable_map import VariableMap as CoreVariableMap
        from src.encoder.variable_map import VariableMap as EncoderVariableMap
        from src.core.cnf_types import CNFFormula as CoreCNF
        from src.solvers.cnf_formula import CNFFormula as SolverCNF
        self.assertIs(CoreVariableMap, EncoderVariableMap)
        self.assertIs(CoreCNF, SolverCNF)

    def test_cnf_contract(self):
        validate_cnf([[1, -2], []], variable_count=2)
        validate_cnf([], variable_count=0)
        with self.assertRaises(ValueError):
            validate_cnf([[0]])
        with self.assertRaises(ValueError):
            validate_cnf([[3]], variable_count=2)
        with self.assertRaises(TypeError):
            validate_cnf([[True]])


if __name__ == "__main__":
    unittest.main()
