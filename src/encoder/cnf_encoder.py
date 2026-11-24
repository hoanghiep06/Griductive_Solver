"""Core CNF encoder for Griductive clues and public knowledge bases.

Converts the 6 core structured clue templates (FACT, SAME, DIFFERENT,
EXACTLY, AT_LEAST, AT_MOST) and proved verdicts into standard DIMACS-style
CNF clauses (list[list[int]]), using VariableMap for deterministic primary
variables C_i and separate auxiliary variables.

Region types for counting clues: ROW, COLUMN, NEIGHBORS, EXPLICIT, plus
ALL (whole board / global rule) and PROFESSION (explicit cell list that the
validator guarantees equals "every character with this profession").
Extended clue types (PARITY, COUNT_COMPARE, IMPLIES) are delegated to
``extended_clues``.
"""

from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Any, Mapping

from src.core.clue import _thaw
from .extended_clues import EXTENDED_TYPES, encode_extended

from .variable_map import VariableMap

SUPPORTED_CORE_TYPES = frozenset(
    {"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST", "NO"}
)
CARDINALITY_ENCODINGS = frozenset({"sequential", "binomial"})

_IGNORED_META_KEYS = frozenset(
    {
        "type",
        "clue_type",
        "kind",
        "params",
        "parameters",
        "owner_id",
        "revealed",
        "owner",
        "id",
        "clue_id",
        "text",
        "description",
    }
)


@dataclass(frozen=True)
class EncodedKB:
    """Encoded CNF knowledge base with variable and clause statistics."""

    clauses: list[list[int]]
    num_primary_vars: int
    num_auxiliary_vars: int
    num_total_vars: int
    num_clauses: int
    clue_count: int = 0
    verdict_count: int = 0

    def stats(self) -> dict[str, int]:
        """Return summary counts for primary vars, auxiliary vars, and clauses."""
        return {
            "primary_vars": self.num_primary_vars,
            "auxiliary_vars": self.num_auxiliary_vars,
            "total_vars": self.num_total_vars,
            "clauses": self.num_clauses,
            "clues": self.clue_count,
            "verdicts": self.verdict_count,
        }

    def to_dimacs(self) -> str:
        """Format the CNF knowledge base in standard DIMACS CNF format."""
        header = f"p cnf {self.num_total_vars} {self.num_clauses}"
        body = [" ".join(str(lit) for lit in clause) + " 0" for clause in self.clauses]
        return "\n".join([header, *body])


def _parse_status(status: Any) -> bool:
    """Parse a verdict/status into True (Criminal) or False (Innocent)."""
    if isinstance(status, bool):
        return status
    if isinstance(status, int) and status in (0, 1):
        return bool(status)
    if isinstance(status, str):
        cleaned = status.strip().upper()
        if cleaned in {"CRIMINAL", "C", "TRUE", "1", "GUILTY"}:
            return True
        if cleaned in {"INNOCENT", "I", "FALSE", "0", "NOT_GUILTY"}:
            return False
    raise ValueError(f"Invalid character status/verdict: {status!r}")


def _extract_clue_payload(clue: Any) -> tuple[str, dict[str, Any]]:
    """Normalize a clue dict or clue-like object into (CLUE_TYPE, params_dict)."""
    if hasattr(clue, "to_dict"):
        clue = clue.to_dict()
    if isinstance(clue, Mapping):
        if clue.get("revealed") is False:
            raise ValueError("Cannot encode an unrevealed clue into the knowledge base")
        raw_type = clue.get("type") or clue.get("clue_type") or clue.get("kind")
        params: dict[str, Any] = {}
        nested_params = clue.get("parameters", clue.get("params"))
        if nested_params is not None:
            if not isinstance(nested_params, dict):
                raise ValueError(f"Clue 'params' must be a dict, got {type(nested_params).__name__}")
            params.update(nested_params)
        for key, value in clue.items():
            if key not in _IGNORED_META_KEYS:
                params.setdefault(key, value)
    else:
        if getattr(clue, "revealed", True) is False:
            raise ValueError("Cannot encode an unrevealed clue into the knowledge base")
        raw_type = getattr(clue, "clue_type", None) or getattr(clue, "type", None)
        nested_params = getattr(clue, "params", None)
        if isinstance(nested_params, dict):
            params = dict(nested_params)
        else:
            params = {}
            for attr in (
                "target",
                "targets",
                "target1",
                "target2",
                "status",
                "k",
                "count",
                "region",
            ):
                if hasattr(clue, attr):
                    params[attr] = getattr(clue, attr)

    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ValueError(f"Clue is missing a valid 'type': {clue!r}")

    clue_type = raw_type.strip().upper()
    if clue_type not in SUPPORTED_CORE_TYPES | EXTENDED_TYPES:
        raise ValueError(f"Unsupported core clue type: {clue_type!r}")
    return clue_type, params


def _deduplicate_clauses(clauses: list[list[int]]) -> list[list[int]]:
    """Remove exact duplicate clauses while preserving deterministic order."""
    seen: set[tuple[int, ...]] = set()
    unique: list[list[int]] = []
    for clause in clauses:
        key = tuple(clause)
        if key not in seen:
            seen.add(key)
            unique.append(list(clause))
    return unique


class CNFEncoder:
    """Automatic logical encoder converting Griductive clues and verdicts to CNF."""

    def __init__(
        self,
        var_map: VariableMap,
        cardinality_encoding: str = "sequential",
    ) -> None:
        if not isinstance(var_map, VariableMap):
            raise TypeError(f"var_map must be a VariableMap, got {type(var_map).__name__}")
        encoding_norm = cardinality_encoding.strip().lower()
        if encoding_norm not in CARDINALITY_ENCODINGS:
            raise ValueError(
                f"cardinality_encoding must be one of {sorted(CARDINALITY_ENCODINGS)}, "
                f"got {cardinality_encoding!r}"
            )
        self.var_map = var_map
        self.cardinality_encoding = encoding_norm
        self._clue_seq = 0

    def _all_cell_keys(self) -> list[str]:
        """Canonical keys of every cell on the board (row-major) for global rules."""
        n = math.isqrt(self.var_map.num_primary)
        keys: list[str] = []
        for row in range(1, n + 1):
            keys.extend(self.var_map.cells_in_row(row))
        return keys

    def resolve_region(self, region: Any) -> list[str]:
        """Validate and resolve a clue region into canonical character keys."""
        if isinstance(region, (list, tuple)):
            return self._resolve_explicit_list(region)

        if isinstance(region, str):
            return self._resolve_region_string(region)

        if isinstance(region, dict):
            raw_kind = region.get("kind") or region.get("type") or region.get("region_type")
            if raw_kind is None:
                if "row" in region:
                    raw_kind = "row"
                elif "col" in region or "column" in region:
                    raw_kind = "column"
                elif "cell" in region or "center" in region:
                    raw_kind = "neighbors"
                elif "cells" in region or "targets" in region or "characters" in region:
                    raw_kind = "explicit"

            if not isinstance(raw_kind, str) or not raw_kind.strip():
                raise ValueError(f"Region dict is missing 'kind'/'type': {region!r}")

            kind = raw_kind.strip().lower()
            if kind == "row":
                row_val = region.get("row", region.get("value", region.get("index")))
                return self.var_map.cells_in_row(row_val)
            if kind in {"col", "column"}:
                col_val = region.get("column", region.get("col", region.get("value")))
                return self.var_map.cells_in_col(col_val)
            if kind in {"neighbors", "neighbor"}:
                center = region.get("cell", region.get("target", region.get("center", region.get("value"))))
                try:
                    return self.var_map.neighbors_of(center)
                except KeyError as exc:
                    raise ValueError(str(exc)) from exc
            if kind in {"explicit", "cells", "list"}:
                items = region.get("cells", region.get("targets", region.get("characters", region.get("value"))))
                return self._resolve_explicit_list(items)
            if kind in {"all", "global"}:
                return self._all_cell_keys()
            raise ValueError(f"Unsupported region kind: {raw_kind!r}")

        raise ValueError(f"Invalid region specification: {region!r}")

    def _resolve_primary(self, identifier: Any) -> int:
        """Resolve a character/cell identifier to its primary ID, raising ValueError if invalid."""
        try:
            return self.var_map.get_primary(identifier)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

    def _resolve_region_string(self, spec: str) -> list[str]:
        """Parse string region shorthands such as 'row:2', 'col:B', 'neighbors:B2' or 'all'."""
        if spec.strip().lower() in {"all", "global"}:
            return self._all_cell_keys()
        if ":" not in spec:
            raise ValueError(f"Invalid region string {spec!r}; expected 'kind:value'")
        prefix, raw_val = spec.split(":", 1)
        kind = prefix.strip().lower()
        val = raw_val.strip()
        if kind == "row":
            try:
                row_int = int(val)
            except ValueError as exc:
                raise ValueError(f"Invalid row number in region string {spec!r}") from exc
            return self.var_map.cells_in_row(row_int)
        if kind in {"col", "column"}:
            return self.var_map.cells_in_col(val)
        if kind in {"neighbors", "neighbor"}:
            try:
                return self.var_map.neighbors_of(val)
            except KeyError as exc:
                raise ValueError(str(exc)) from exc
        raise ValueError(f"Unsupported region string prefix in {spec!r}")

    def _resolve_explicit_list(self, items: Any) -> list[str]:
        """Validate an explicit list of distinct character/cell identifiers."""
        if not isinstance(items, (list, tuple)) or len(items) == 0:
            raise ValueError("Explicit region must be a non-empty list of cell/character identifiers")
        resolved: list[str] = []
        seen: set[str] = set()
        for item in items:
            try:
                canonical = self.var_map.resolve_canonical(item)
            except KeyError as exc:
                raise ValueError(str(exc)) from exc
            if canonical in seen:
                raise ValueError(f"Duplicate cell/character {item!r} in explicit region")
            seen.add(canonical)
            resolved.append(canonical)
        return resolved

    def _extract_single_target(self, params: dict[str, Any]) -> int:
        """Resolve a single target character to its primary variable ID."""
        for key in ("target", "character", "person", "cell", "subject"):
            if key in params and params[key] is not None:
                return self._resolve_primary(params[key])
        raise ValueError(f"Clue is missing target character: {params!r}")

    def _extract_two_targets(self, params: dict[str, Any]) -> tuple[int, int]:
        """Resolve two distinct target characters to primary variable IDs."""
        targets = params.get("targets") or params.get("characters")
        if targets is not None:
            if not isinstance(targets, (list, tuple)) or len(targets) != 2:
                raise ValueError(f"'targets' must contain exactly 2 characters, got {targets!r}")
            t1, t2 = targets[0], targets[1]
        else:
            t1 = params.get("target1", params.get("a", params.get("first", params.get("left"))))
            t2 = params.get("target2", params.get("b", params.get("second", params.get("right"))))
            if t1 is None or t2 is None:
                raise ValueError(f"Binary clue requires 2 targets, got {params!r}")

        v1 = self._resolve_primary(t1)
        v2 = self._resolve_primary(t2)
        if v1 == v2:
            raise ValueError(f"Binary clue targets must be two distinct characters, got {t1!r} and {t2!r}")
        return v1, v2

    def _extract_k_and_region(
        self, params: dict[str, Any], fixed_k: int | None = None
    ) -> tuple[int, list[int]]:
        """Validate counting parameter k and resolve region to primary variable IDs."""
        if "region" not in params or params["region"] is None:
            raise ValueError(f"Counting clue is missing 'region': {params!r}")
        keys = self.resolve_region(params["region"])
        var_ids = [self._resolve_primary(k_name) for k_name in keys]

        k = fixed_k if fixed_k is not None else params.get("k", params.get("count"))
        if isinstance(k, bool) or not isinstance(k, int):
            raise ValueError(f"Counting parameter 'k' must be an integer, got {k!r}")
        if k < 0 or k > len(var_ids):
            raise ValueError(f"Counting parameter k={k} out of valid range 0..{len(var_ids)}")
        return k, var_ids

    def encode_clue(self, clue: dict[str, Any] | Any) -> list[list[int]]:
        """Validate and convert one clue into CNF clauses."""
        clue_type, params = _extract_clue_payload(clue)
        params = _thaw(params)
        if clue_type in EXTENDED_TYPES:
            return encode_extended({"type": clue_type, "params": params}, self.var_map)
        if "region_type" in params and "region" not in params:
            kind = params["region_type"]
            if kind == "ROW":
                params["region"] = {"kind": "row", "row": params["index"] + 1}
            elif kind == "COLUMN":
                params["region"] = {"kind": "column", "column": chr(ord("A") + params["index"])}
            elif kind == "NEIGHBORS":
                params["region"] = {"kind": "neighbors", "cell": params["center"]}
            elif kind in {"EXPLICIT", "PROFESSION"}:
                # PROFESSION carries a pre-resolved cell list (checked by PuzzleValidator).
                if not params.get("cells"):
                    k = params.get("k", 0)
                    if type(k) is not int or k != 0:
                        raise ValueError("Empty regions require k=0")
                    return []
                params["region"] = params["cells"]
            elif kind == "ALL":
                params["region"] = self._all_cell_keys()
        self._clue_seq += 1
        tag_prefix = f"c{self._clue_seq}_{clue_type.lower()}"

        if clue_type == "FACT":
            var_id = self._extract_single_target(params)
            raw_status = params.get("status", params.get("verdict", params.get("is_criminal")))
            if raw_status is None:
                raise ValueError(f"FACT clue is missing 'status': {params!r}")
            is_criminal = _parse_status(raw_status)
            return [[var_id]] if is_criminal else [[-var_id]]

        if clue_type == "SAME":
            v1, v2 = self._extract_two_targets(params)
            return [[-v1, v2], [v1, -v2]]

        if clue_type == "DIFFERENT":
            v1, v2 = self._extract_two_targets(params)
            return [[-v1, -v2], [v1, v2]]

        if clue_type == "NO":
            k, vars_r = self._extract_k_and_region(params, fixed_k=0)
            return self._encode_exactly(k, vars_r, tag_prefix)

        k, vars_r = self._extract_k_and_region(params)
        if clue_type == "EXACTLY":
            return self._encode_exactly(k, vars_r, tag_prefix)
        if clue_type == "AT_LEAST":
            return self._encode_at_least(k, vars_r, tag_prefix)
        if clue_type == "AT_MOST":
            return self._encode_at_most(k, vars_r, tag_prefix)

        raise ValueError(f"Unsupported core clue type: {clue_type!r}")

    def _encode_at_most(self, k: int, lits: list[int], tag_prefix: str) -> list[list[int]]:
        """Encode sum_{l in lits} (l is True) <= k."""
        n = len(lits)
        if k == 0:
            return [[-lit] for lit in lits]
        if k == n:
            return []
        if self.cardinality_encoding == "binomial":
            return [[-lit for lit in comb] for comb in itertools.combinations(lits, k + 1)]
        clauses, counter = self._build_seq_counter(lits, k, include_final=False, tag_prefix=tag_prefix)
        for i in range(k, n):
            clauses.append([-lits[i], -counter[(i - 1, k)]])
        return clauses

    def _encode_at_least(self, k: int, lits: list[int], tag_prefix: str) -> list[list[int]]:
        """Encode sum_{l in lits} (l is True) >= k via dual AT_MOST(n - k, -lits)."""
        n = len(lits)
        if k == 0:
            return []
        if k == n:
            return [[lit] for lit in lits]
        neg_lits = [-lit for lit in lits]
        return self._encode_at_most(n - k, neg_lits, tag_prefix)

    def _encode_exactly(self, k: int, lits: list[int], tag_prefix: str) -> list[list[int]]:
        """Encode sum_{l in lits} (l is True) == k."""
        n = len(lits)
        if k == 0:
            return [[-lit] for lit in lits]
        if k == n:
            return [[lit] for lit in lits]
        if self.cardinality_encoding == "binomial":
            return (
                self._encode_at_most(k, lits, tag_prefix)
                + self._encode_at_least(k, lits, tag_prefix)
            )

        # Symmetry optimization: count the smaller of (k, n - k) using a single counter.
        if k <= n - k:
            target_lits = list(lits)
            target_k = k
        else:
            target_lits = [-lit for lit in lits]
            target_k = n - k

        clauses, counter = self._build_seq_counter(
            target_lits, target_k, include_final=True, tag_prefix=tag_prefix
        )
        for i in range(target_k, n):
            clauses.append([-target_lits[i], -counter[(i - 1, target_k)]])
        clauses.append([counter[(n - 1, target_k)]])
        return clauses

    def _build_seq_counter(
        self,
        lits: list[int],
        k: int,
        *,
        include_final: bool,
        tag_prefix: str,
    ) -> tuple[list[list[int]], dict[tuple[int, int], int]]:
        """Build a bidirectional sequential counter s[i, j] <-> (sum_{m=0..i} lits[m] >= j).

        Preconditions: n = len(lits) >= 2 and 1 <= k < n.
        """
        n = len(lits)
        max_i = n if include_final else n - 1
        clauses: list[list[int]] = []
        counter: dict[tuple[int, int], int] = {}

        s01 = self.var_map.allocate_aux(f"{tag_prefix}_s0_1")
        counter[(0, 1)] = s01
        clauses.append([-lits[0], s01])
        clauses.append([lits[0], -s01])

        for i in range(1, max_i):
            si1 = self.var_map.allocate_aux(f"{tag_prefix}_s{i}_1")
            counter[(i, 1)] = si1
            prev1 = counter[(i - 1, 1)]
            # si1 <-> (lits[i] OR prev1)
            clauses.append([-lits[i], si1])
            clauses.append([-prev1, si1])
            clauses.append([lits[i], prev1, -si1])

            upper_j = min(i + 1, k)
            for j in range(2, upper_j + 1):
                sij = self.var_map.allocate_aux(f"{tag_prefix}_s{i}_{j}")
                counter[(i, j)] = sij
                prev_diag = counter[(i - 1, j - 1)]
                if j == i + 1:
                    # s[i-1, j] is identically False, so sij <-> (lits[i] AND prev_diag)
                    clauses.append([-sij, lits[i]])
                    clauses.append([-sij, prev_diag])
                    clauses.append([-lits[i], -prev_diag, sij])
                else:
                    prev_same = counter[(i - 1, j)]
                    # sij <-> (prev_same OR (lits[i] AND prev_diag))
                    clauses.append([-prev_same, sij])
                    clauses.append([-lits[i], -prev_diag, sij])
                    clauses.append([-sij, prev_same, lits[i]])
                    clauses.append([-sij, prev_same, prev_diag])

        return clauses, counter

    def encode_verdict(self, target: str, status: str | bool | int) -> list[int]:
        """Encode a single proved verdict into a unit CNF clause."""
        var_id = self._resolve_primary(target)
        is_criminal = _parse_status(status)
        return [var_id] if is_criminal else [-var_id]

    def encode_verdicts(self, verdicts: dict[str, Any] | list[Any] | None) -> list[list[int]]:
        """Encode known proved verdicts as unit clauses, rejecting conflicting duplicates."""
        if not verdicts:
            return []

        items: list[tuple[str, Any]] = []
        if isinstance(verdicts, Mapping):
            items.extend(verdicts.items())
        elif isinstance(verdicts, list):
            for entry in verdicts:
                if isinstance(entry, tuple) and len(entry) == 2:
                    items.append((entry[0], entry[1]))
                elif isinstance(entry, dict):
                    target = entry.get("target") or entry.get("character") or entry.get("cell")
                    status = entry.get("status", entry.get("verdict", entry.get("is_criminal")))
                    if target is None or status is None:
                        raise ValueError(f"Verdict dict requires target and status: {entry!r}")
                    items.append((target, status))
                else:
                    raise ValueError(f"Invalid verdict list item: {entry!r}")
        else:
            raise TypeError(f"verdicts must be dict, list, or None, got {type(verdicts).__name__}")

        seen_status: dict[int, bool] = {}
        clauses: list[list[int]] = []
        for target, status in items:
            unit = self.encode_verdict(target, status)
            lit = unit[0]
            var_id = abs(lit)
            is_crim = lit > 0
            if var_id in seen_status:
                if seen_status[var_id] != is_crim:
                    raise ValueError(f"Conflicting verdicts provided for character {target!r}")
                continue
            seen_status[var_id] = is_crim
            clauses.append(unit)
        return clauses

    def encode_kb(
        self,
        revealed_clues: list[Any],
        proved_verdicts: dict[str, Any] | list[Any] | None = None,
        *,
        reset_aux: bool = False,
        deduplicate: bool = True,
    ) -> EncodedKB:
        """Build KB_t = CNF(revealed_clues) AND unit_clauses(proved_verdicts)."""
        if reset_aux:
            self.var_map.reset_auxiliary()
            self._clue_seq = 0

        clauses: list[list[int]] = []
        for clue in revealed_clues:
            clauses.extend(self.encode_clue(clue))

        verdict_clauses = self.encode_verdicts(proved_verdicts)
        clauses.extend(verdict_clauses)

        if deduplicate:
            clauses = _deduplicate_clauses(clauses)

        return EncodedKB(
            clauses=clauses,
            num_primary_vars=self.var_map.num_primary,
            num_auxiliary_vars=self.var_map.num_auxiliary,
            num_total_vars=self.var_map.total_vars,
            num_clauses=len(clauses),
            clue_count=len(revealed_clues),
            verdict_count=len(verdict_clauses),
        )

    def encode_public_kb(
        self,
        public_kb: dict[str, Any] | Any,
        *,
        reset_aux: bool = True,
        deduplicate: bool = True,
    ) -> EncodedKB:
        """Encode a PublicKB snapshot (ignoring any unrevealed clues or hidden fields)."""
        if isinstance(public_kb, dict):
            raw_clues = public_kb.get("revealed_clues", [])
            verdicts = public_kb.get(
                "proved_verdicts",
                public_kb.get("known_verdicts", public_kb.get("verdicts")),
            )
        else:
            raw_clues = getattr(public_kb, "revealed_clues", [])
            verdicts = getattr(
                public_kb,
                "proved_verdicts",
                getattr(public_kb, "known_verdicts", getattr(public_kb, "verdicts", None)),
            )

        revealed_only = [
            clue
            for clue in raw_clues
            if not (
                (isinstance(clue, dict) and clue.get("revealed") is False)
                or (not isinstance(clue, dict) and getattr(clue, "revealed", True) is False)
            )
        ]
        return self.encode_kb(
            revealed_clues=revealed_only,
            proved_verdicts=verdicts,
            reset_aux=reset_aux,
            deduplicate=deduplicate,
        )