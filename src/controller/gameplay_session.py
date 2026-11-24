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
from src.core.regions import SPATIAL_REGIONS
from src.encoder.cnf_encoder import CNFEncoder
from src.solvers.dpll import DPLLSolver
from src.gui.view_models import (
    CardVisibility, PublicBoardSnapshot, PublicCharacterView, PublicClueView,
)
from src.gui.case_catalog import localize_profession

REGION_LABELS = {
    "ALL": "Toàn bộ bàn cờ", "CORNERS": "Bốn góc", "BORDER": "Viền ngoài", "CENTER": "Vùng trung tâm",
    "TOP_HALF": "Nửa trên", "BOTTOM_HALF": "Nửa dưới", "LEFT_HALF": "Nửa trái", "RIGHT_HALF": "Nửa phải",
}


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
    sat_calls: int = 0


class GameplaySession:
    def __init__(self, path: str | Path):
        self.engine = GameEngine(path)
        self.session_id = uuid4().hex
        self._clue_cache: dict[tuple[str, str, str], PublicClueView] = {}
        self._cached_encoder: CNFEncoder | None = None

    def restart(self):
        self.engine.restart()
        self.session_id = uuid4().hex
        self._clue_cache.clear()
        self._cached_encoder = None

    def _encoder(self):
        vm = VariableMap()
        vm.register_characters(self.engine.characters)
        vm.freeze_primary_variables()
        return CNFEncoder(vm)

    def board(self) -> PublicBoardSnapshot:
        snapshot = self.engine.get_public_snapshot()
        projected: list[PublicClueView] = []
        for c in snapshot.revealed_clues:
            key = (c.clue_id, c.owner_id, c.clue_type)
            cached = self._clue_cache.get(key)
            if cached is None:
                if self._cached_encoder is None:
                    self._cached_encoder = self._encoder()
                cached = self._project_clue(c, self._cached_encoder)
                self._clue_cache[key] = cached
            projected.append(cached)
        clues = tuple(projected)
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
        scope, scope_label = "", ""
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
            scope_label = {"==": "=", "!=": "≠", "<=": "≤", ">=": "≥"}.get(p["op"], p["op"])
            text = f"Số tội phạm ở {self._group_label(left)} {scope_label} ở {self._group_label(right)}."
        elif kind == "PARITY":
            refs = [canonical(c) for c in p["cells"]]
            parity = "chẵn" if str(p["parity"]).lower() in {"even", "0"} else "lẻ"
            scope_label = f"Số {parity}"
            group = self._group_label(refs)
            text = f"{group[0].upper() + group[1:]} có số tội phạm {parity}."
        elif kind == "IMPLIES":
            a, b = p["antecedent"], p["consequent"]
            primary, secondary = [canonical(a["target"])], [canonical(b["target"])]
            refs = primary + secondary
            status = lambda value: "tội phạm" if value == "CRIMINAL" else "vô tội"
            text = f"Nếu {label(primary[0])} là {status(a['status'])} thì {label(secondary[0])} là {status(b['status'])}."
        else:
            region = p.get("region")
            region_type = p.get("region_type")
            if region_type == "ROW":
                region = f"row:{p['index'] + 1}"
            elif region_type == "COLUMN":
                region = f"col:{chr(65 + p['index'])}"
            elif region_type == "NEIGHBORS":
                region = f"neighbors:{p['center']}"
            elif region_type in {"EXPLICIT", "PROFESSION"}:
                region = p["cells"]
            elif region_type == "ALL" or region_type in SPATIAL_REGIONS:
                region = region_type
            refs = encoder.resolve_region(region) if region else []
            quantifier = {"EXACTLY": "đúng", "AT_LEAST": "ít nhất", "AT_MOST": "nhiều nhất", "NO": "đúng"}[kind]
            k = 0 if kind == "NO" else p.get("k", p.get("count"))
            if region_type == "PROFESSION":
                scope_label = localize_profession(p["profession"])
                region_label = f"Nhóm nghề {scope_label}"
                scope = region_type
            elif region_type in REGION_LABELS:
                scope, scope_label = region_type, REGION_LABELS[region_type]
                region_label = scope_label
            else:
                group = self._group_label(refs)
                region_label = group[0].upper() + group[1:]
                if region_type == "NEIGHBORS":
                    region_label = f"Các ô xung quanh {p['center']} (kể cả đường chéo)"
            text = f"{region_label} có {quantifier} {k} tội phạm."
            if scope_label:
                badges.append(scope_label)
        if refs:
            characters = [self.engine.get_character(cid) for cid in refs]
            if len(refs) == self.engine.grid_size and len({c.row for c in characters}) == 1:
                badges.append(f"Hàng {characters[0].row + 1}")
            elif len(refs) == self.engine.grid_size and len({c.col for c in characters}) == 1:
                badges.append(f"Cột {chr(65 + characters[0].col)}")
        return PublicClueView(clue.clue_id, clue.owner_id, kind, text, tuple(dict.fromkeys(refs)),
                              tuple(primary or refs), tuple(secondary), tuple(badges), scope, scope_label)

    def _group_label(self, cells):
        if not cells:
            return "nhóm rỗng"
        characters = [self.engine.get_character(cid) for cid in cells]
        if len(cells) == self.engine.grid_size and len({c.row for c in characters}) == 1:
            return f"hàng {characters[0].row + 1}"
        if len(cells) == self.engine.grid_size and len({c.col for c in characters}) == 1:
            return f"cột {chr(65 + characters[0].col)}"
        if len(cells) == self.engine.grid_size ** 2:
            return "toàn bàn"
        return f"nhóm {{{', '.join(cells)}}}"

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
        sat_calls = (
            (result.classification.sat_calls if result.classification is not None else 0)
            + len(result.extra_metrics)
        )
        return Analysis(
            result.version,
            result.cell_id,
            result.classification,
            Evidence(result.clue_ids, result.support_cell_ids),
            result.inconsistent,
            sat_calls=sat_calls,
        )
