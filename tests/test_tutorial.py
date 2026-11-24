"""Authoring checks: every scripted deduction is forced without hidden clues."""

from itertools import product

from src.core.game_engine import VerdictResponse
from src.core.puzzle_loader import PuzzleLoader
from src.core.puzzle_validator import PuzzleValidator
from src.encoder.cnf_encoder import CNFEncoder
from src.core.variable_map import VariableMap
from src.tutorial.data import LEVEL_PATH, TUTORIAL_STEPS
from src.tutorial.session import TutorialSession


def test_tutorial_covers_all_playable_rules_and_region_forms():
    puzzle = PuzzleLoader().load(LEVEL_PATH)
    assert puzzle.grid_size == 4
    taught = {s.clue_id for s in TUTORIAL_STEPS if s.target}
    clues = [c for c in puzzle.clues if c.clue_id in taught]
    assert {c.clue_type for c in clues} == {
        "FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", "COUNT_COMPARE",
    }
    assert {c.parameters["region_type"] for c in clues if "region_type" in c.parameters} == {
        "ROW", "COLUMN", "NEIGHBORS", "EXPLICIT",
    }
    assert len([s for s in TUTORIAL_STEPS if s.target]) == 15


def test_each_scripted_move_is_forced_by_its_named_clue_semantically_and_by_sat():
    """Exhaust all remaining assignments independently of CNF at every step.

    Even other public clues are excluded: the displayed explanation itself
    must justify the move. Hidden keys are used only by GameEngine's normal
    initial reveal / integrity check.
    """
    session = TutorialSession()
    puzzle = PuzzleLoader().load(LEVEL_PATH)
    validator = PuzzleValidator()
    while True:
        step = session.step
        if step.target:
            snapshot = session.game.engine.get_public_snapshot()
            clue = next(c for c in snapshot.revealed_clues if c.clue_id == step.clue_id)
            known = dict(snapshot.proved_verdicts)
            unresolved = [c.id for c in puzzle.characters if c.id not in known]
            possibilities = set()
            for values in product((False, True), repeat=len(unresolved)):
                assignment = {**known, **dict(zip(unresolved, values))}
                if validator.evaluate_clue(clue, assignment, puzzle.characters_by_id, 4):
                    possibilities.add(assignment[step.target])
            assert possibilities == {step.verdict == "CRIMINAL"}, step.title
            assert not session.advance()
            assert session.submit("unrelated", step.verdict) is None
            opposite = "INNOCENT" if step.verdict == "CRIMINAL" else "CRIMINAL"
            assert session.submit(step.target, opposite) is VerdictResponse.CONTRADICTED
            assert session.game.engine.public_kb_version == snapshot.version
            assert session.submit(step.target, step.verdict) is VerdictResponse.ACCEPTED
            assert session.game.engine.public_kb_version == snapshot.version + 1
            assert session.submit(step.target, step.verdict) is VerdictResponse.ALREADY_SOLVED
            assert session.can_advance
        if not session.advance():
            break
    assert session.step.focus == "complete"
    assert session.game.engine.is_solved()


def test_no_encoder_alias_is_taught_with_schema_compatible_exactly_zero():
    puzzle = PuzzleLoader().load(LEVEL_PATH)
    vm = VariableMap()
    vm.register_characters(puzzle.characters)
    vm.freeze_primary_variables()
    encoder = CNFEncoder(vm)
    zero = next(c for c in puzzle.clues if c.clue_id == "t_B4")
    no = {"type": "NO", "parameters": {"region": ["C4", "D4"]}}
    assert encoder.encode_clue(zero) == encoder.encode_clue(no)


def test_tutorial_instances_do_not_share_progress_or_script_state():
    first, second = TutorialSession(), TutorialSession()
    first.advance()
    first.advance()
    first.submit(first.step.target, first.step.verdict)
    assert second.index == 0
    assert set(second.game.engine.get_proved_verdicts()) == {"A1"}
    assert first.game.session_id != second.game.session_id
