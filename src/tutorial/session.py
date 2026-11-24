"""Tutorial progression with real SAT proofs and no access to hidden answers."""

from src.agent.entailment import EntailmentChecker
from src.controller.gameplay_session import GameplaySession
from src.core.game_engine import VerdictResponse
from src.core.variable_map import VariableMap
from src.encoder.cnf_encoder import CNFEncoder
from src.solvers.dpll import DPLLSolver
from src.tutorial.data import LEVEL_PATH, TUTORIAL_STEPS


class TutorialSession:
    def __init__(self):
        self.game = GameplaySession(LEVEL_PATH)
        self.index = 0

    @property
    def step(self):
        return TUTORIAL_STEPS[self.index]

    @property
    def can_advance(self):
        return self.step.target is None or self.step.target in self.game.engine.get_proved_verdicts()

    def advance(self):
        if not self.can_advance or self.index == len(TUTORIAL_STEPS) - 1:
            return False
        self.index += 1
        return True

    def submit(self, cell_id: str, verdict: str):
        if cell_id != self.step.target or verdict not in {"CRIMINAL", "INNOCENT"}:
            return None
        engine = self.game.engine
        snapshot = engine.get_public_snapshot()
        if cell_id in snapshot.proved_verdicts:
            return VerdictResponse.ALREADY_SOLVED
        # Prove from exactly the clue being taught plus publicly known statuses.
        # This prevents an unrelated newly revealed clue masking a script error.
        clue = next(c for c in snapshot.revealed_clues if c.clue_id == self.step.clue_id)
        vm = VariableMap()
        vm.register_characters(engine.characters)
        vm.freeze_primary_variables()
        encoder = CNFEncoder(vm)
        cnf = encoder.encode_kb([clue], dict(snapshot.proved_verdicts)).clauses
        result = EntailmentChecker(DPLLSolver(), variable_map=vm).classify(cnf, vm.get_var(cell_id))
        response, _ = engine.submit_verdict(
            cell_id, verdict == "CRIMINAL", result.to_engine_result(cell_id, snapshot.version),
        )
        return response
