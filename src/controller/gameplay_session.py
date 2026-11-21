"""Public-data adapter around the existing engine, encoder and SAT checker.

No solver algorithms live here. Each analysis uses a fresh variable map so a
background request cannot mutate the engine's primary/auxiliary mapping.

The reasoning itself (finding the first forced cell and its minimal evidence)
lives in ``src.agent.forced_move.analyze_public_kb``, the same function the
LogicAgent uses, so GUI and CLI can never disagree.
"""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.agent.entailment import ClassificationResult, EntailmentChecker
from src.agent.forced_move import analyze_public_kb
from src.core.game_engine import GameEngine
from src.core.variable_map import VariableMap
from src.encoder.cnf_encoder import CNFEncoder
from src.solvers.dpll import DPLLSolver
from src.gui.view_models import (
    CardVisibility, PublicBoardSnapshot, PublicCharacterView, PublicClueView,
)


@dataclass(frozen=True)
class Evidence:
    clue_ids: tuple[str, ...] = ()
    cell_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Analysis:
    version: int
    cell_id: str | None
    classification: ClassificationResult | None
    evidence: Evidence = Evidence()
    inconsistent: bool = False


class GameplaySession:
    def __init__(self, path: str | Path):
        self.engine = GameEngine(path)
        self.session_id = uuid4().hex

    def restart(self):
        self.engine.restart()
        self.session_id = uuid4().hex

    def _encoder(self):
        vm = VariableMap()
        vm.register_characters(self.engine.characters)
        vm.freeze_primary_variables()
        return CNFEncoder(vm)

    def board(self) -> PublicBoardSnapshot:
        snapshot = self.engine.get_public_snapshot()
        encoder = self._encoder()
        clues = tuple(self._project_clue(c, encoder) for c in snapshot.revealed_clues)
        owners = {c.owner_id for c in clues}
        characters = tuple(
            PublicCharacterView(
                c.id, c.name, c.profession, c.row, c.col,
                CardVisibility.REVEALED if c.id in snapshot.proved_verdicts else CardVisibility.HIDDEN,
                ("CRIMINAL" if snapshot.proved_verdicts[c.id] else "INNOCENT")
                if c.id in snapshot.proved_verdicts else None,
                c.id in owners,
            ) for c in self.engine.characters
        )
        return PublicBoardSnapshot(self.session_id, self.engine.puzzle_id,
                                   self.engine.grid_size, snapshot.version, characters, clues)

    def _project_clue(self, clue, encoder) -> PublicClueView:
        p = clue.to_dict()["parameters"]
        kind = clue.clue_type
        vm = encoder.var_map
        canonical = vm.resolve_canonical
        label = lambda cid: f"{self.engine.get_character(cid).name} ({cid})"
        refs: list[str] = []
        primary, secondary, badges = [], [], []
        if kind == "FACT":
            target = next(p[k] for k in ("target", "character", "person", "cell", "subject") if k in p)
            refs = [canonical(target)]
            raw = p.get("status", p.get("verdict", p.get("is_criminal")))
            status = "tội phạm" if raw is True or str(raw).upper() in {"CRIMINAL", "TRUE", "1", "GUILTY", "C"} else "vô tội"
            text = f"{label(refs[0])} là {status}."
        elif kind in {"SAME", "DIFFERENT"}:
            # Ask the existing encoder to resolve all accepted target aliases.
            a, b = encoder._extract_two_targets(p)
            refs = [vm.get_char_id(a), vm.get_char_id(b)]
            primary, secondary = refs[:1], refs[1:]
            relation = "cùng" if kind == "SAME" else "khác"
            text = f"{label(refs[0])} và {label(refs[1])} {relation} phe."
        elif kind == "COUNT_COMPARE":
            left = [canonical(c) for c in p["region_a"]]
            right = [canonical(c) for c in p["region_b"]]
            refs = left + right
            primary, secondary = left, right
            text = f"Số tội phạm nhóm {', '.join(left)} {p['op']} nhóm {', '.join(right)}."
        elif kind == "PARITY":
            refs = [canonical(c) for c in p["cells"]]
            parity = "chẵn" if str(p["parity"]).lower() in {"even", "0"} else "lẻ"
            text = f"Nhóm {', '.join(refs)} có số tội phạm {parity}."
        else:
            region = p.get("region")
            region_type = p.get("region_type")
            if region_type == "ROW":
                region = f"row:{p['index'] + 1}"
            elif region_type == "COLUMN":
                region = f"col:{chr(65 + p['index'])}"
            elif region_type == "NEIGHBORS":
                region = f"neighbors:{p['center']}"
            elif region_type == "EXPLICIT":
                region = p["cells"]
            refs = encoder.resolve_region(region) if region else []
            quantifier = {"EXACTLY": "đúng", "AT_LEAST": "ít nhất", "AT_MOST": "nhiều nhất", "NO": "đúng"}[kind]
            k = 0 if kind == "NO" else p.get("k", p.get("count"))
            region_label = ", ".join(refs) or "rỗng"
            text = f"Nhóm {region_label} có {quantifier} {k} tội phạm."
        if refs:
            characters = [self.engine.get_character(cid) for cid in refs]
            if len(refs) == self.engine.grid_size and len({c.row for c in characters}) == 1:
                badges.append(f"Hàng {characters[0].row + 1}")
            elif len(refs) == self.engine.grid_size and len({c.col for c in characters}) == 1:
                badges.append(f"Cột {chr(65 + characters[0].col)}")
        return PublicClueView(clue.clue_id, clue.owner_id, kind, text, tuple(dict.fromkeys(refs)),
                              tuple(primary or refs), tuple(secondary), tuple(badges))

    def analyze(self, cell_id: str | None = None) -> Analysis:
        """Classify a guess or find the next forced step using only the public KB.

        Delegates to the shared ``analyze_public_kb`` (same path as LogicAgent).
        A fresh encoder/checker/solver is created per call, so this is safe to
        run on a worker thread.
        """
        snapshot = self.engine.get_public_snapshot()
        encoder = self._encoder()
        solver = DPLLSolver()
        checker = EntailmentChecker(solver, variable_map=encoder.var_map)
        result = analyze_public_kb(
            snapshot,
            self.engine.get_unsolved_characters(),
            encoder,
            checker,
            solver=solver,
            target=cell_id,
        )
        return Analysis(
            result.version,
            result.cell_id,
            result.classification,
            Evidence(result.clue_ids, result.support_cell_ids),
            result.inconsistent,
        )