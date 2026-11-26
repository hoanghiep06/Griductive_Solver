"""Pure-Python public presentation view-models & validation adapters (PROPOSED).

Why this module exists:
    ``src/shared/dto.py`` (owned by Hiệp per ``docs/STAGE2_SHARED_BASELINE.md``)
    has not been materialized yet in the repository. These frozen dataclasses
    mirror ``docs/STAGE2_API_CONTRACT.md`` §B2 field-for-field and are marked
    PROPOSED. Every ``normalize_*`` helper uses duck-typing so all GUI widgets
    accept future ``src/shared/dto.py`` objects directly with zero breaking
    changes and ZERO imports from ``src.core``, ``src.solvers``, ``src.encoder``,
    ``src.agent``, or ``src.controller``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Iterable, Optional


class CardVisibility(str, Enum):
    """Public card presentation state (aligned with STAGE2_API_CONTRACT §B)."""

    HIDDEN = "HIDDEN"
    REVEALED = "REVEALED"


class GameState(str, Enum):
    """Public UI interaction lifecycle state (aligned with STAGE2_API_CONTRACT §B)."""

    NO_PUZZLE = "NO_PUZZLE"
    READY = "READY"
    PROCESSING = "PROCESSING"
    ANIMATING = "ANIMATING"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    ERROR = "ERROR"


class ActionCode(str, Enum):
    """Controller → GUI action outcome codes (aligned with STAGE2_API_CONTRACT §B2)."""

    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"
    ALREADY_SOLVED = "ALREADY_SOLVED"
    STALE_PROOF = "STALE_PROOF"
    INVALID_REQUEST = "INVALID_REQUEST"
    BUSY = "BUSY"
    LOAD_FAILED = "LOAD_FAILED"
    CANCELLED = "CANCELLED"
    SOLVER_FAILED = "SOLVER_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class NotificationSeverity(str, Enum):
    """Visual severity tier for NotificationBanner / NotificationDialog."""

    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


VALID_PUBLIC_VERDICTS = frozenset({"CRIMINAL", "INNOCENT"})
VALID_TRACE_VERDICTS = frozenset({"CRIMINAL", "INNOCENT", "UNKNOWN"})
VALID_SUPPORT_KINDS = frozenset({"PUBLIC_KB", "VERIFIED_SUBSET"})
VALID_HINT_OUTCOMES = frozenset({"FORCED", "NO_FORCED"})
VALID_CLUE_SCOPES = frozenset({"", "ALL", "PROFESSION", "CORNERS", "BORDER", "CENTER",
                               "TOP_HALF", "BOTTOM_HALF", "LEFT_HALF", "RIGHT_HALF"})
SUPPORTED_GRID_SIZES = frozenset({3, 4, 5})
CORE_CLUE_TYPES = frozenset({"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST"})


def _is_strict_int(value: Any) -> bool:
    return type(value) is int


def _coerce_non_empty_str(raw: Any, field_name: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return raw.strip()


def _coerce_verdict(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    val = getattr(raw, "value", raw)
    if not isinstance(val, str):
        raise ValueError(f"Invalid verdict type: {type(raw).__name__}")
    cleaned = val.strip().upper()
    if cleaned not in VALID_PUBLIC_VERDICTS:
        raise ValueError(
            f"Public revealed verdict must be CRIMINAL or INNOCENT, got {raw!r}"
        )
    return cleaned


def _coerce_trace_verdict(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    val = getattr(raw, "value", raw)
    if not isinstance(val, str):
        raise ValueError(f"Invalid trace verdict type: {type(raw).__name__}")
    cleaned = val.strip().upper()
    if not cleaned or cleaned == "UNKNOWN":
        return None
    if cleaned not in VALID_PUBLIC_VERDICTS:
        raise ValueError(
            f"Trace verdict must be CRIMINAL, INNOCENT, UNKNOWN, or None; got {raw!r}"
        )
    return cleaned


def _coerce_visibility(raw: Any) -> CardVisibility:
    if isinstance(raw, CardVisibility):
        return raw
    val = getattr(raw, "value", raw)
    if isinstance(val, str):
        try:
            return CardVisibility(val.strip().upper())
        except ValueError as exc:
            raise ValueError(f"Invalid CardVisibility: {raw!r}") from exc
    if isinstance(raw, bool):
        return CardVisibility.REVEALED if raw else CardVisibility.HIDDEN
    raise ValueError(f"Invalid visibility value: {raw!r}")


def coerce_game_state(raw: Any) -> GameState:
    """Normalize a ``GameState`` enum or string value safely."""
    if isinstance(raw, GameState):
        return raw
    val = getattr(raw, "value", raw)
    if isinstance(val, str):
        try:
            return GameState(val.strip().upper())
        except ValueError as exc:
            raise ValueError(f"Invalid GameState: {raw!r}") from exc
    raise ValueError(f"Invalid GameState: {raw!r}")


def coerce_action_code(raw: Any) -> ActionCode:
    """Normalize an ``ActionCode`` enum or string value safely."""
    if isinstance(raw, ActionCode):
        return raw
    val = getattr(raw, "value", raw)
    if isinstance(val, str):
        try:
            return ActionCode(val.strip().upper())
        except ValueError as exc:
            raise ValueError(f"Invalid ActionCode: {raw!r}") from exc
    raise ValueError(f"Invalid ActionCode: {raw!r}")


def coerce_severity(raw: Any) -> NotificationSeverity:
    """Normalize a ``NotificationSeverity`` enum or string value."""
    if isinstance(raw, NotificationSeverity):
        return raw
    val = getattr(raw, "value", raw)
    if isinstance(val, str):
        try:
            return NotificationSeverity(val.strip().upper())
        except ValueError as exc:
            raise ValueError(f"Invalid NotificationSeverity: {raw!r}") from exc
    raise ValueError(f"Invalid NotificationSeverity: {raw!r}")


def action_code_to_severity(code: ActionCode) -> NotificationSeverity:
    """Map a Controller ``ActionCode`` to a consistent UI severity tier."""
    if code is ActionCode.ACCEPTED:
        return NotificationSeverity.SUCCESS
    if code in (
        ActionCode.NOT_PROVABLE,
        ActionCode.BUSY,
        ActionCode.STALE_PROOF,
        ActionCode.INVALID_REQUEST,
    ):
        return NotificationSeverity.WARNING
    if code in (
        ActionCode.CONTRADICTED,
        ActionCode.INCONSISTENT,
        ActionCode.LOAD_FAILED,
        ActionCode.SOLVER_FAILED,
        ActionCode.INTERNAL_ERROR,
    ):
        return NotificationSeverity.ERROR
    # ALREADY_SOLVED, CANCELLED -> informational feedback
    return NotificationSeverity.INFO


def _coerce_str_tuple(raw: Any, field_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raise TypeError(f"{field_name} must be an iterable of strings, not a single str")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings, got {item!r}")
        result.append(item.strip())
    return tuple(result)


@dataclass(frozen=True, slots=True)
class AnimationToken:
    """PROPOSED immutable reveal-animation handshake token (STAGE2_API_CONTRACT §B1)."""

    session_id: str
    request_id: int
    kb_version: int
    cell_id: str

    def __post_init__(self) -> None:
        sid = _coerce_non_empty_str(self.session_id, "session_id")
        if not _is_strict_int(self.request_id) or self.request_id < 0:
            raise ValueError("request_id must be a non-negative int")
        if not _is_strict_int(self.kb_version) or self.kb_version < 0:
            raise ValueError("kb_version must be a non-negative int")
        cid = _coerce_non_empty_str(self.cell_id, "cell_id")
        object.__setattr__(self, "session_id", sid)
        object.__setattr__(self, "cell_id", cid)


@dataclass(frozen=True, slots=True)
class PublicCharacterView:
    """PROPOSED immutable public presentation view for one suspect card."""

    cell_id: str
    name: str
    profession: str
    row: int
    col: int
    visibility: CardVisibility = CardVisibility.HIDDEN
    verdict: Optional[str] = None
    has_public_clue: bool = False

    def __post_init__(self) -> None:
        cid = _coerce_non_empty_str(self.cell_id, "cell_id")
        name = _coerce_non_empty_str(self.name, "name")
        prof = _coerce_non_empty_str(self.profession, "profession")
        if not _is_strict_int(self.row) or not _is_strict_int(self.col):
            raise TypeError("row and col must be int (not bool)")
        if self.row < 0 or self.col < 0:
            raise ValueError(f"Negative coordinates ({self.row}, {self.col}) for {cid!r}")

        vis = _coerce_visibility(self.visibility)
        object.__setattr__(self, "cell_id", cid)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "profession", prof)
        object.__setattr__(self, "visibility", vis)
        object.__setattr__(self, "has_public_clue", bool(self.has_public_clue))

        if vis is CardVisibility.HIDDEN:
            if self.verdict is not None:
                raise ValueError(
                    f"HIDDEN character {cid!r} must not carry a verdict ({self.verdict!r})"
                )
            if self.has_public_clue:
                raise ValueError(
                    f"HIDDEN character {cid!r} must not advertise a public clue"
                )
            object.__setattr__(self, "verdict", None)
        else:
            coerced = _coerce_verdict(self.verdict)
            if coerced is None:
                raise ValueError(
                    f"REVEALED character {cid!r} requires verdict CRIMINAL or INNOCENT"
                )
            object.__setattr__(self, "verdict", coerced)

    @property
    def is_revealed(self) -> bool:
        return self.visibility is CardVisibility.REVEALED


@dataclass(frozen=True, slots=True)
class PublicClueView:
    """PROPOSED immutable public clue view (aligned with STAGE2_API_CONTRACT §B2).

    Contains ONLY already-revealed public clue information rendered as plain text.
    Never stores raw private JSON ``parameters`` or hidden-character clues.

    ``scope`` / ``scope_label`` are optional presentation hints used by the
    rule-effects layer:
        - ``scope="ALL"``        : global rule over the whole board
        - ``scope="PROFESSION"`` : rule over all characters of one profession
          (``scope_label`` holds the profession display name, e.g. "Bác sĩ")
    """

    clue_id: str
    owner_id: str
    clue_type: str
    text: str
    referenced_cells: tuple[str, ...] = ()
    primary_cells: tuple[str, ...] = ()
    secondary_cells: tuple[str, ...] = ()
    reference_labels: tuple[str, ...] = ()
    scope: str = ""
    scope_label: str = ""

    def __post_init__(self) -> None:
        cid = _coerce_non_empty_str(self.clue_id, "clue_id")
        oid = _coerce_non_empty_str(self.owner_id, "owner_id")
        ctype = _coerce_non_empty_str(self.clue_type, "clue_type").upper()
        txt = _coerce_non_empty_str(self.text, "text")
        refs = _coerce_str_tuple(self.referenced_cells, "referenced_cells")
        object.__setattr__(self, "clue_id", cid)
        object.__setattr__(self, "owner_id", oid)
        object.__setattr__(self, "clue_type", ctype)
        object.__setattr__(self, "text", txt)
        object.__setattr__(self, "referenced_cells", refs)
        for key in ("primary_cells", "secondary_cells", "reference_labels"):
            object.__setattr__(self, key, _coerce_str_tuple(getattr(self, key), key))

        scope = (self.scope or "").strip().upper()
        if scope not in VALID_CLUE_SCOPES:
            raise ValueError(f"Unsupported clue scope {self.scope!r}")
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "scope_label", (self.scope_label or "").strip())

    @property
    def display_text(self) -> str:
        """Alias matching conceptual naming in Phase 4 prompt §6.3."""
        return self.text


@dataclass(frozen=True, slots=True)
class PublicBoardSnapshot:
    """PROPOSED immutable public board snapshot (aligned with STAGE2_API_CONTRACT §B2)."""

    session_id: str
    puzzle_id: str
    grid_size: int
    kb_version: int
    characters: tuple[PublicCharacterView, ...]
    clues: tuple[PublicClueView, ...] = ()

    def __post_init__(self) -> None:
        sid = _coerce_non_empty_str(self.session_id, "session_id")
        pid = _coerce_non_empty_str(self.puzzle_id, "puzzle_id")
        if not _is_strict_int(self.grid_size) or self.grid_size not in SUPPORTED_GRID_SIZES:
            raise ValueError(f"Unsupported grid_size {self.grid_size!r}; expected 3, 4, or 5")
        if not _is_strict_int(self.kb_version) or self.kb_version < 0:
            raise ValueError("kb_version must be a non-negative integer")
        clues_tuple = tuple(normalize_clue_view(cl) for cl in self.clues)
        clue_owners = {cl.owner_id for cl in clues_tuple}
        chars = tuple(normalize_character_view(c, clue_owner_ids=clue_owners) for c in self.characters)
        chars = validate_characters_for_grid(chars, self.grid_size)

        # Privacy invariant: a public clue must belong to a revealed character on this board
        char_by_id = {c.cell_id: c for c in chars}
        for cl in clues_tuple:
            owner = char_by_id.get(cl.owner_id)
            if owner is None:
                raise ValueError(
                    f"Public clue {cl.clue_id!r} references unknown owner {cl.owner_id!r}"
                )
            if owner.visibility is CardVisibility.HIDDEN:
                raise ValueError(
                    f"Privacy violation: clue {cl.clue_id!r} belongs to HIDDEN character {cl.owner_id!r}"
                )

        object.__setattr__(self, "session_id", sid)
        object.__setattr__(self, "puzzle_id", pid)
        object.__setattr__(self, "characters", chars)
        object.__setattr__(self, "clues", clues_tuple)


@dataclass(frozen=True, slots=True)
class DeductionStepView:
    """PROPOSED immutable accepted deduction step (aligned with STAGE2_API_CONTRACT §B2)."""

    session_id: str
    request_id: int
    kb_version: int
    cell_id: str
    verdict: Optional[str]
    explanation: str
    source_clue_ids: tuple[str, ...] = ()
    support_kind: str = "PUBLIC_KB"
    sat_calls: Optional[int] = None
    elapsed_ms: Optional[float] = None
    step: Optional[int] = None
    newly_revealed_clue_id: Optional[str] = None

    def __post_init__(self) -> None:
        sid = _coerce_non_empty_str(self.session_id, "session_id")
        if not _is_strict_int(self.request_id) or self.request_id < 0:
            raise ValueError("request_id must be a non-negative int")
        if not _is_strict_int(self.kb_version) or self.kb_version < 0:
            raise ValueError("kb_version must be a non-negative int")
        cid = _coerce_non_empty_str(self.cell_id, "cell_id")
        verdict = _coerce_trace_verdict(self.verdict)
        expl = _coerce_non_empty_str(self.explanation, "explanation")
        clue_ids = _coerce_str_tuple(self.source_clue_ids, "source_clue_ids")
        sk = _coerce_non_empty_str(self.support_kind, "support_kind").upper()
        if sk not in VALID_SUPPORT_KINDS:
            raise ValueError(f"Unsupported support_kind {sk!r}; expected {sorted(VALID_SUPPORT_KINDS)}")

        if self.sat_calls is not None:
            if not _is_strict_int(self.sat_calls) or self.sat_calls < 0:
                raise ValueError("sat_calls must be None or a non-negative int")
        if self.elapsed_ms is not None:
            if isinstance(self.elapsed_ms, bool) or not isinstance(self.elapsed_ms, (int, float)):
                raise TypeError("elapsed_ms must be None or a finite non-negative number")
            if not math.isfinite(self.elapsed_ms) or self.elapsed_ms < 0:
                raise ValueError("elapsed_ms must be finite and non-negative")
        if self.step is not None:
            if not _is_strict_int(self.step) or self.step < 1:
                raise ValueError("step must be None or a positive int")
        newly = None
        if self.newly_revealed_clue_id is not None:
            newly = _coerce_non_empty_str(self.newly_revealed_clue_id, "newly_revealed_clue_id")

        object.__setattr__(self, "session_id", sid)
        object.__setattr__(self, "cell_id", cid)
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "explanation", expl)
        object.__setattr__(self, "source_clue_ids", clue_ids)
        object.__setattr__(self, "support_kind", sk)
        object.__setattr__(self, "elapsed_ms", float(self.elapsed_ms) if self.elapsed_ms is not None else None)
        object.__setattr__(self, "newly_revealed_clue_id", newly)

    @property
    def dedup_key(self) -> tuple[str, int, str]:
        """Idempotency key mandated by STAGE2_API_CONTRACT §D."""
        return (self.session_id, self.request_id, self.cell_id)


@dataclass(frozen=True, slots=True)
class HintView:
    """PROPOSED immutable non-mutating Hint view (aligned with STAGE2_API_CONTRACT §B2).

    ``FORCED`` hints may omit ``verdict``: the Hint button only points at the
    cell and the supporting clues without revealing the conclusion.
    """

    session_id: str
    kb_version: int
    outcome: str
    cell_id: Optional[str]
    verdict: Optional[str]
    text: str
    source_clue_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        sid = _coerce_non_empty_str(self.session_id, "session_id")
        if not _is_strict_int(self.kb_version) or self.kb_version < 0:
            raise ValueError("kb_version must be a non-negative int")
        outcome = _coerce_non_empty_str(self.outcome, "outcome").upper()
        if outcome not in VALID_HINT_OUTCOMES:
            raise ValueError(f"HintView outcome must be FORCED or NO_FORCED, got {outcome!r}")
        txt = _coerce_non_empty_str(self.text, "text")
        clue_ids = _coerce_str_tuple(self.source_clue_ids, "source_clue_ids")

        if outcome == "FORCED":
            cid = _coerce_non_empty_str(self.cell_id, "cell_id")
            verdict = _coerce_verdict(self.verdict) if self.verdict is not None else None
        else:
            cid = None
            verdict = None
            clue_ids = ()

        object.__setattr__(self, "session_id", sid)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "cell_id", cid)
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "text", txt)
        object.__setattr__(self, "source_clue_ids", clue_ids)


@dataclass(frozen=True, slots=True)
class ActionResult:
    """PROPOSED immutable safe notification payload (aligned with STAGE2_API_CONTRACT §B2)."""

    code: ActionCode
    message: str
    session_id: Optional[str] = None
    kb_version: Optional[int] = None
    cell_id: Optional[str] = None
    severity: Optional[NotificationSeverity] = None

    def __post_init__(self) -> None:
        code = coerce_action_code(self.code)
        msg = _coerce_non_empty_str(self.message, "message")
        sid = _coerce_non_empty_str(self.session_id, "session_id") if self.session_id is not None else None
        if self.kb_version is not None:
            if not _is_strict_int(self.kb_version) or self.kb_version < 0:
                raise ValueError("kb_version must be None or a non-negative int")
        cid = _coerce_non_empty_str(self.cell_id, "cell_id") if self.cell_id is not None else None
        sev = coerce_severity(self.severity) if self.severity is not None else action_code_to_severity(code)

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", msg)
        object.__setattr__(self, "session_id", sid)
        object.__setattr__(self, "cell_id", cid)
        object.__setattr__(self, "severity", sev)


@dataclass(frozen=True, slots=True)
class LevelSummary:
    """PROPOSED immutable public case-catalog entry (aligned with STAGE2_API_CONTRACT §B2)."""

    puzzle_id: str
    title: str
    grid_size: int
    difficulty_label: Optional[str] = None
    archetype_label: str = ""

    def __post_init__(self) -> None:
        pid = _coerce_non_empty_str(self.puzzle_id, "puzzle_id")
        title = _coerce_non_empty_str(self.title, "title")
        if not _is_strict_int(self.grid_size) or self.grid_size not in SUPPORTED_GRID_SIZES:
            raise ValueError(f"Unsupported grid_size {self.grid_size!r}; expected 3, 4, or 5")
        diff = (
            _coerce_non_empty_str(self.difficulty_label, "difficulty_label")
            if self.difficulty_label is not None
            else None
        )
        object.__setattr__(self, "puzzle_id", pid)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "difficulty_label", diff)
        object.__setattr__(self, "archetype_label", (self.archetype_label or "").strip())


@dataclass(frozen=True, slots=True)
class ResultsView:
    """PROPOSED immutable case-closed summary view (aligned with STAGE2_API_CONTRACT §B2)."""

    session_id: str
    puzzle_id: str
    revealed: int
    total: int
    accepted_steps: int
    hint_requests: int
    elapsed_ms: Optional[float] = None
    sat_calls: Optional[int] = None
    next_puzzle_id: Optional[str] = None
    grid_size: Optional[int] = None
    is_demo_preview: bool = False

    def __post_init__(self) -> None:
        sid = _coerce_non_empty_str(self.session_id, "session_id")
        pid = _coerce_non_empty_str(self.puzzle_id, "puzzle_id")
        for fname, val in (
            ("revealed", self.revealed),
            ("total", self.total),
            ("accepted_steps", self.accepted_steps),
            ("hint_requests", self.hint_requests),
        ):
            if not _is_strict_int(val) or val < 0:
                raise ValueError(f"{fname} must be a non-negative int")
        if self.total == 0 or self.revealed > self.total:
            raise ValueError(f"Invalid revealed/total counts: {self.revealed}/{self.total}")
        if self.elapsed_ms is not None:
            if isinstance(self.elapsed_ms, bool) or not isinstance(self.elapsed_ms, (int, float)):
                raise TypeError("elapsed_ms must be None or a finite non-negative number")
            if not math.isfinite(self.elapsed_ms) or self.elapsed_ms < 0:
                raise ValueError("elapsed_ms must be finite and non-negative")
        if self.sat_calls is not None:
            if not _is_strict_int(self.sat_calls) or self.sat_calls < 0:
                raise ValueError("sat_calls must be None or a non-negative int")
        next_pid = (
            _coerce_non_empty_str(self.next_puzzle_id, "next_puzzle_id")
            if self.next_puzzle_id is not None
            else None
        )
        inferred_size = self.grid_size
        if inferred_size is None:
            root = math.isqrt(self.total)
            if root * root == self.total and root in SUPPORTED_GRID_SIZES:
                inferred_size = root
        elif not _is_strict_int(inferred_size) or inferred_size not in SUPPORTED_GRID_SIZES:
            raise ValueError(f"Unsupported grid_size {inferred_size!r}; expected 3, 4, or 5")

        object.__setattr__(self, "session_id", sid)
        object.__setattr__(self, "puzzle_id", pid)
        object.__setattr__(self, "elapsed_ms", float(self.elapsed_ms) if self.elapsed_ms is not None else None)
        object.__setattr__(self, "next_puzzle_id", next_pid)
        object.__setattr__(self, "grid_size", inferred_size)
        object.__setattr__(self, "is_demo_preview", bool(self.is_demo_preview))


# ---------------------------------------------------------------------------
# Duck-typed Normalization Helpers (for future src/shared/dto.py interop)
# ---------------------------------------------------------------------------


def normalize_character_view(
    obj: Any,
    *,
    clue_owner_ids: Optional[set[str]] = None,
) -> PublicCharacterView:
    """Normalize a shared DTO or local PublicCharacterView into a validated view."""
    if isinstance(obj, PublicCharacterView):
        if clue_owner_ids is not None and obj.is_revealed and not obj.has_public_clue:
            if obj.cell_id in clue_owner_ids:
                return PublicCharacterView(
                    cell_id=obj.cell_id,
                    name=obj.name,
                    profession=obj.profession,
                    row=obj.row,
                    col=obj.col,
                    visibility=obj.visibility,
                    verdict=obj.verdict,
                    has_public_clue=True,
                )
        return obj

    cell_id = getattr(obj, "cell_id", None)
    name = getattr(obj, "name", None)
    profession = getattr(obj, "profession", None)
    row = getattr(obj, "row", None)
    col = getattr(obj, "col", None)

    if hasattr(obj, "visibility"):
        visibility = _coerce_visibility(getattr(obj, "visibility"))
    elif hasattr(obj, "is_revealed"):
        visibility = _coerce_visibility(bool(getattr(obj, "is_revealed")))
    else:
        raise ValueError("Character view missing 'visibility' or 'is_revealed'")

    raw_verdict = getattr(obj, "verdict", getattr(obj, "known_verdict", None))
    has_clue = bool(
        getattr(obj, "has_public_clue", False)
        or (getattr(obj, "public_clue_id", None) is not None)
        or (clue_owner_ids is not None and cell_id in clue_owner_ids)
    )
    if visibility is CardVisibility.HIDDEN:
        has_clue = False

    return PublicCharacterView(
        cell_id=cell_id,
        name=name,
        profession=profession,
        row=row,
        col=col,
        visibility=visibility,
        verdict=raw_verdict,
        has_public_clue=has_clue,
    )


def normalize_clue_view(obj: Any) -> PublicClueView:
    """Normalize a shared DTO or duck-typed clue object into ``PublicClueView``.

    Explicitly rejects objects that expose ``is_revealed=False`` / ``revealed=False``
    or carry raw private fields like ``hidden_solution`` or ``parameters``.
    """
    if isinstance(obj, PublicClueView):
        return obj

    if hasattr(obj, "is_revealed") and getattr(obj, "is_revealed") is False:
        raise ValueError("Refusing to display unrevealed private clue")
    if hasattr(obj, "revealed") and getattr(obj, "revealed") is False:
        raise ValueError("Refusing to display unrevealed private clue")
    if hasattr(obj, "hidden_solution") or hasattr(obj, "parameters"):
        raise ValueError(
            "Refusing raw domain Clue containing private 'parameters' or 'hidden_solution'; "
            "Controller must project to PublicClueView first"
        )

    clue_id = getattr(obj, "clue_id", None)
    owner_id = getattr(obj, "owner_id", None)
    clue_type = getattr(obj, "clue_type", getattr(obj, "type", None))
    text = getattr(obj, "text", getattr(obj, "display_text", None))
    referenced = getattr(obj, "referenced_cells", ()) or ()

    return PublicClueView(
        clue_id=clue_id,
        owner_id=owner_id,
        clue_type=clue_type,
        text=text,
        referenced_cells=tuple(referenced),
        primary_cells=tuple(getattr(obj, "primary_cells", ()) or ()),
        secondary_cells=tuple(getattr(obj, "secondary_cells", ()) or ()),
        reference_labels=tuple(getattr(obj, "reference_labels", ()) or ()),
        scope=getattr(obj, "scope", "") or "",
        scope_label=getattr(obj, "scope_label", "") or "",
    )


def normalize_deduction_step(obj: Any) -> DeductionStepView:
    """Normalize a shared DTO or duck-typed step into ``DeductionStepView``."""
    if isinstance(obj, DeductionStepView):
        return obj

    session_id = getattr(obj, "session_id", "external-session")
    request_id = getattr(obj, "request_id", getattr(obj, "step", 0))
    kb_version = getattr(obj, "kb_version", 0)
    cell_id = getattr(obj, "cell_id", None)
    verdict = getattr(obj, "verdict", None)
    explanation = getattr(obj, "explanation", getattr(obj, "text", None))
    if explanation is None:
        v_label = getattr(verdict, "value", verdict) or "UNKNOWN"
        explanation = f"Suy luận hợp lệ cho ô {cell_id}: {v_label}"
    source_clue_ids = getattr(
        obj,
        "source_clue_ids",
        getattr(obj, "active_clue_ids", ()),
    ) or ()
    support_kind = getattr(obj, "support_kind", "PUBLIC_KB")
    sat_calls = getattr(obj, "sat_calls", None)
    elapsed_ms = getattr(obj, "elapsed_ms", None)
    step = getattr(obj, "step", None)
    newly_revealed = getattr(obj, "newly_revealed_clue_id", None)

    return DeductionStepView(
        session_id=session_id,
        request_id=request_id,
        kb_version=kb_version,
        cell_id=cell_id,
        verdict=verdict,
        explanation=explanation,
        source_clue_ids=tuple(source_clue_ids),
        support_kind=support_kind,
        sat_calls=sat_calls,
        elapsed_ms=elapsed_ms,
        step=step,
        newly_revealed_clue_id=newly_revealed,
    )


def normalize_hint_view(obj: Any) -> HintView:
    """Normalize a shared DTO or duck-typed hint into ``HintView``."""
    if isinstance(obj, HintView):
        return obj

    return HintView(
        session_id=getattr(obj, "session_id", "external-session"),
        kb_version=getattr(obj, "kb_version", 0),
        outcome=getattr(obj, "outcome", "NO_FORCED"),
        cell_id=getattr(obj, "cell_id", None),
        verdict=getattr(obj, "verdict", None),
        text=getattr(obj, "text", ""),
        source_clue_ids=tuple(getattr(obj, "source_clue_ids", ()) or ()),
    )


def normalize_action_result(obj: Any) -> ActionResult:
    """Normalize a shared DTO or duck-typed notification payload into ``ActionResult``."""
    if isinstance(obj, ActionResult):
        return obj

    return ActionResult(
        code=getattr(obj, "code", None),
        message=getattr(obj, "message", None),
        session_id=getattr(obj, "session_id", None),
        kb_version=getattr(obj, "kb_version", None),
        cell_id=getattr(obj, "cell_id", None),
        severity=getattr(obj, "severity", None),
    )


def normalize_level_summary(obj: Any) -> LevelSummary:
    """Normalize a shared DTO or duck-typed catalog item into ``LevelSummary``."""
    if isinstance(obj, LevelSummary):
        return obj

    if hasattr(obj, "hidden_solution") or hasattr(obj, "criminal_count"):
        raise ValueError(
            "LevelSummary must not carry private puzzle metadata ('hidden_solution' / 'criminal_count')"
        )

    return LevelSummary(
        puzzle_id=getattr(obj, "puzzle_id", None),
        title=getattr(obj, "title", None) or getattr(obj, "puzzle_id", None),
        grid_size=getattr(obj, "grid_size", None),
        difficulty_label=getattr(obj, "difficulty_label", None),
        archetype_label=getattr(obj, "archetype_label", "") or "",
    )


def normalize_results_view(obj: Any) -> ResultsView:
    """Normalize a shared DTO or duck-typed results payload into ``ResultsView``."""
    if isinstance(obj, ResultsView):
        return obj

    if hasattr(obj, "hidden_solution"):
        raise ValueError("ResultsView must not carry private 'hidden_solution'")

    return ResultsView(
        session_id=getattr(obj, "session_id", "external-session"),
        puzzle_id=getattr(obj, "puzzle_id", None),
        revealed=getattr(obj, "revealed", 0),
        total=getattr(obj, "total", 0),
        accepted_steps=getattr(obj, "accepted_steps", 0),
        hint_requests=getattr(obj, "hint_requests", 0),
        elapsed_ms=getattr(obj, "elapsed_ms", None),
        sat_calls=getattr(obj, "sat_calls", None),
        next_puzzle_id=getattr(obj, "next_puzzle_id", None),
        grid_size=getattr(obj, "grid_size", None),
        is_demo_preview=bool(getattr(obj, "is_demo_preview", False)),
    )


def validate_characters_for_grid(
    characters: Iterable[PublicCharacterView],
    grid_size: int,
) -> tuple[PublicCharacterView, ...]:
    """Validate grid bounds, uniqueness, and full N*N coverage; return row-major tuple."""
    if not _is_strict_int(grid_size) or grid_size not in SUPPORTED_GRID_SIZES:
        raise ValueError(f"Unsupported grid_size {grid_size!r}; expected 3, 4, or 5")

    items = tuple(characters)
    expected = grid_size * grid_size
    if len(items) != expected:
        raise ValueError(
            f"Expected exactly {expected} characters for {grid_size}x{grid_size} board, "
            f"got {len(items)}"
        )

    seen_ids: set[str] = set()
    seen_coords: set[tuple[int, int]] = set()
    for ch in items:
        if ch.cell_id in seen_ids:
            raise ValueError(f"Duplicate cell_id {ch.cell_id!r} in board snapshot")
        seen_ids.add(ch.cell_id)

        if not (0 <= ch.row < grid_size and 0 <= ch.col < grid_size):
            raise ValueError(
                f"Character {ch.cell_id!r} coordinate ({ch.row}, {ch.col}) "
                f"is outside {grid_size}x{grid_size} grid"
            )
        coord = (ch.row, ch.col)
        if coord in seen_coords:
            raise ValueError(f"Duplicate coordinate {coord} for character {ch.cell_id!r}")
        seen_coords.add(coord)

    # Sort deterministically in row-major order regardless of input JSON order
    return tuple(sorted(items, key=lambda c: (c.row, c.col, c.cell_id)))


def normalize_board_snapshot(snapshot: Any) -> PublicBoardSnapshot:
    """Validate and normalize any duck-typed PublicBoardSnapshot for GameBoard."""
    if isinstance(snapshot, PublicBoardSnapshot):
        return snapshot

    grid_size = getattr(snapshot, "grid_size", None)
    puzzle_id = getattr(snapshot, "puzzle_id", "UNKNOWN_CASE")
    session_id = getattr(snapshot, "session_id", "external-session")
    kb_version = getattr(snapshot, "kb_version", 0)
    raw_clues = tuple(getattr(snapshot, "clues", getattr(snapshot, "revealed_clues", ())) or ())
    norm_clues = tuple(normalize_clue_view(cl) for cl in raw_clues)
    clue_owners = {cl.owner_id for cl in norm_clues}
    raw_chars = getattr(snapshot, "characters", None)
    if raw_chars is None:
        raise ValueError("Board snapshot is missing 'characters'")

    chars = tuple(normalize_character_view(c, clue_owner_ids=clue_owners) for c in raw_chars)
    return PublicBoardSnapshot(
        session_id=session_id,
        puzzle_id=puzzle_id,
        grid_size=grid_size,
        kb_version=kb_version,
        characters=chars,
        clues=norm_clues,
    )
