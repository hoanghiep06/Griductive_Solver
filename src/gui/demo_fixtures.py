"""Isolated PUBLIC MOCK DATA fixtures for Phase 3–4 standalone GUI demo.

IMPORTANT:
    - Contains 100% synthetic public presentation data for UI testing/demo.
    - Contains NO ``hidden_solution``, NO unrevealed clues, NO SAT/DPLL calls,
      and NEVER reads ``puzzles/*.json`` or ``puzzles/manifest.json``.
    - Exists strictly for developer UI demonstration before Hiệp's Controller
      and Tài's Logic Agent are integrated.
"""

from __future__ import annotations

from src.gui.view_models import (
    ActionCode,
    ActionResult,
    CardVisibility,
    DeductionStepView,
    HintView,
    LevelSummary,
    PublicBoardSnapshot,
    PublicCharacterView,
    PublicClueView,
    ResultsView,
)


def build_demo_3x3_snapshot(*, puzzle_id: str = "MOCK_3x3_DEMO") -> PublicBoardSnapshot:
    """SCENARIO A — 3×3 (9 characters: 2 initially revealed, 7 hidden, 2 public clues)."""
    rows = [
        ("A1", "Abel", "Bác sĩ", 0, 0, CardVisibility.REVEALED, "INNOCENT", True),
        ("B1", "Bea", "Thủ thư", 0, 1, CardVisibility.REVEALED, "CRIMINAL", True),
        ("C1", "Clara", "Nhà báo", 0, 2, CardVisibility.HIDDEN, None, False),
        ("A2", "Derek", "Chuyên viên phân tích", 1, 0, CardVisibility.HIDDEN, None, False),
        ("B2", "Eliza", "Kỹ sư cơ khí", 1, 1, CardVisibility.HIDDEN, None, False),
        ("C2", "Franz", "Dược sĩ", 1, 2, CardVisibility.HIDDEN, None, False),
        ("A3", "Grant", "Bảo vệ", 2, 0, CardVisibility.HIDDEN, None, False),
        ("B3", "Hannah", "Nhà sử học", 2, 1, CardVisibility.HIDDEN, None, False),
        ("C3", "Ivy", "Họa sĩ minh họa", 2, 2, CardVisibility.HIDDEN, None, False),
    ]
    chars = tuple(
        PublicCharacterView(cid, name, prof, r, c, vis, verd, has_clue)
        for cid, name, prof, r, c, vis, verd, has_clue in rows
    )
    clues = (
        PublicClueView(
            clue_id="CLUE_A1",
            owner_id="A1",
            clue_type="EXACTLY",
            text="[MẪU] Hàng 1 có chính xác 1 nghi phạm là tội phạm.",
            referenced_cells=("A1", "B1", "C1"),
        ),
        PublicClueView(
            clue_id="CLUE_B1",
            owner_id="B1",
            clue_type="DIFFERENT",
            text="[MẪU] Clara (C1) và Derek (A2) thuộc hai phe đối lập nhau.",
            referenced_cells=("C1", "A2"),
        ),
    )
    return PublicBoardSnapshot(
        session_id=f"demo-mock-3x3-{puzzle_id}",
        puzzle_id=puzzle_id,
        grid_size=3,
        kb_version=1,
        characters=chars,
        clues=clues,
    )


def build_demo_4x4_snapshot(*, puzzle_id: str = "MOCK_4x4_DEMO") -> PublicBoardSnapshot:
    """SCENARIO B — 4×4 (16 characters, 4 revealed, long wrapping public clues)."""
    rows = [
        ("A1", "Nguyễn Minh Khang", "Giám định pháp y trưởng", 0, 0, CardVisibility.REVEALED, "INNOCENT", True),
        ("B1", "Trần Bảo Ngọc", "Phóng viên điều tra", 0, 1, CardVisibility.HIDDEN, None, False),
        ("C1", "Lê Hoàng Phúc", "Kiến trúc sư đô thị", 0, 2, CardVisibility.REVEALED, "CRIMINAL", True),
        ("D1", "Phạm Thảo Vy", "Thủ thư lưu trữ cổ", 0, 3, CardVisibility.HIDDEN, None, False),
        ("A2", "Vũ Quốc Anh", "Kỹ sư an ninh mạng", 1, 0, CardVisibility.HIDDEN, None, False),
        ("B2", "Đặng Hải Yến", "Bác sĩ tâm lý học", 1, 1, CardVisibility.REVEALED, "INNOCENT", True),
        ("C2", "Bùi Đức Thành", "Chuyên gia hóa học", 1, 2, CardVisibility.HIDDEN, None, False),
        ("D2", "Đỗ Khánh Linh", "Biên tập viên thời sự", 1, 3, CardVisibility.HIDDEN, None, False),
        ("A3", "Hồ Gia Huy", "Thợ sửa đồng hồ", 2, 0, CardVisibility.HIDDEN, None, False),
        ("B3", "Ngô Phương Anh", "Luật sư tranh tụng", 2, 1, CardVisibility.HIDDEN, None, False),
        ("C3", "Dương Nhật Minh", "Nhiếp ảnh gia tự do", 2, 2, CardVisibility.REVEALED, "CRIMINAL", True),
        ("D3", "Lý Thanh Trúc", "Quản lý bảo tàng", 2, 3, CardVisibility.HIDDEN, None, False),
        ("A4", "Trương Tuấn Kiệt", "Nhân viên điều phối", 3, 0, CardVisibility.HIDDEN, None, False),
        ("B4", "Hoàng Mai Chi", "Giảng viên văn học", 3, 1, CardVisibility.HIDDEN, None, False),
        ("C4", "Phan Hữu Nghĩa", "Cảnh sát tuần tra", 3, 2, CardVisibility.HIDDEN, None, False),
        ("D4", "Võ Kim Ngân", "Họa sĩ phục chế tranh", 3, 3, CardVisibility.HIDDEN, None, False),
    ]
    chars = tuple(
        PublicCharacterView(cid, name, prof, r, c, vis, verd, has_clue)
        for cid, name, prof, r, c, vis, verd, has_clue in rows
    )
    clues = (
        PublicClueView(
            clue_id="CLUE_A1",
            owner_id="A1",
            clue_type="FACT",
            text="[MẪU] Báo cáo hiện trường công khai xác nhận Nguyễn Minh Khang (A1) không có mặt tại kho hồ sơ vào khung giờ xảy ra vụ mất cắp.",
            referenced_cells=("A1",),
        ),
        PublicClueView(
            clue_id="CLUE_C1",
            owner_id="C1",
            clue_type="SAME",
            text="[MẪU] Hai nghi phạm Trần Bảo Ngọc (B1) và Phạm Thảo Vy (D1) có cùng trạng thái CRIMINAL hoặc INNOCENT theo lời khai đã kiểm chứng.",
            referenced_cells=("B1", "D1"),
        ),
        PublicClueView(
            clue_id="CLUE_B2",
            owner_id="B2",
            clue_type="AT_LEAST",
            text="[MẪU] Trong nhóm các ô lân cận xung quanh Đặng Hải Yến (B2), có ít nhất 2 nghi phạm là CRIMINAL cần khoanh vùng kiểm tra.",
            referenced_cells=("A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3"),
        ),
        PublicClueView(
            clue_id="CLUE_C3",
            owner_id="C3",
            clue_type="AT_MOST",
            text="[MẪU] Toàn bộ cột C (từ C1 đến C4) chỉ có nhiều nhất 2 nghi phạm là CRIMINAL, giúp thu hẹp phạm vi điều tra ở nửa dưới bàn cờ.",
            referenced_cells=("C1", "C2", "C3", "C4"),
        ),
    )
    return PublicBoardSnapshot(
        session_id=f"demo-mock-4x4-{puzzle_id}",
        puzzle_id=puzzle_id,
        grid_size=4,
        kb_version=2,
        characters=chars,
        clues=clues,
    )


def build_demo_5x5_snapshot(*, puzzle_id: str = "MOCK_5x5_DEMO") -> PublicBoardSnapshot:
    """SCENARIO C — 5×5 (25 characters, 6 revealed covering all 6 clue types for scroll QA)."""
    names_profs = [
        ("Abel", "Bác sĩ"), ("Bea", "Thủ thư"), ("Clara", "Nhà báo"), ("Derek", "Phân tích"), ("Eliza", "Kỹ sư"),
        ("Franz", "Dược sĩ"), ("Grant", "Bảo vệ"), ("Hannah", "Sử học"), ("Ivy", "Họa sĩ"), ("Jonas", "Luật sư"),
        ("Kira", "Giám định"), ("Liam", "Thợ mộc"), ("Mina", "Kế toán"), ("Noah", "Bác sĩ"), ("Olga", "Biên tập"),
        ("Paul", "Nhiếp ảnh"), ("Quinn", "Quản lý"), ("Rosa", "Kiến trúc"), ("Soren", "Hóa học"), ("Tessa", "Giảng viên"),
        ("Uriel", "Điều phối"), ("Vera", "Phóng viên"), ("Wade", "An ninh"), ("Xena", "Cơ khí"), ("Yuki", "Phục chế"),
    ]
    revealed_map = {
        "A1": "INNOCENT",
        "C2": "CRIMINAL",
        "D2": "INNOCENT",
        "B4": "INNOCENT",
        "A5": "INNOCENT",
        "E5": "CRIMINAL",
    }
    chars = []
    idx = 0
    for r in range(5):
        for c in range(5):
            cid = f"{chr(ord('A') + c)}{r + 1}"
            name, prof = names_profs[idx]
            idx += 1
            verdict = revealed_map.get(cid)
            vis = CardVisibility.REVEALED if verdict is not None else CardVisibility.HIDDEN
            chars.append(
                PublicCharacterView(
                    cell_id=cid,
                    name=name,
                    profession=prof,
                    row=r,
                    col=c,
                    visibility=vis,
                    verdict=verdict,
                    has_public_clue=(verdict is not None),
                )
            )
    clues = (
        PublicClueView("CLUE_A1", "A1", "FACT", "[MẪU] Hồ sơ xác thực Abel (A1) là vô tội.", ("A1",)),
        PublicClueView("CLUE_C2", "C2", "SAME", "[MẪU] Bea (B1) và Eliza (E1) có cùng trạng thái.", ("B1", "E1")),
        PublicClueView("CLUE_D2", "D2", "DIFFERENT", "[MẪU] Franz (A2) và Grant (B2) thuộc hai phe khác nhau.", ("A2", "B2")),
        PublicClueView("CLUE_B4", "B4", "EXACTLY", "[MẪU] Hàng 4 có chính xác 2 nghi phạm là tội phạm.", ("A4", "B4", "C4", "D4", "E4")),
        PublicClueView("CLUE_A5", "A5", "AT_LEAST", "[MẪU] Nhóm lân cận của Paul (A4) có ít nhất 1 nghi phạm là tội phạm.", ("A3", "B3", "B4", "A5", "B5")),
        PublicClueView("CLUE_E5", "E5", "AT_MOST", "[MẪU] Cột E có nhiều nhất 2 nghi phạm là tội phạm trong toàn vụ án.", ("E1", "E2", "E3", "E4", "E5")),
    )
    return PublicBoardSnapshot(
        session_id=f"demo-mock-5x5-{puzzle_id}",
        puzzle_id=puzzle_id,
        grid_size=5,
        kb_version=3,
        characters=tuple(chars),
        clues=clues,
    )


def build_demo_snapshot(grid_size: int, *, puzzle_id: str | None = None) -> PublicBoardSnapshot:
    """Return the synthetic public mock snapshot for 3, 4, or 5."""
    if grid_size == 3:
        return build_demo_3x3_snapshot(puzzle_id=puzzle_id or "MOCK_3x3_DEMO")
    if grid_size == 4:
        return build_demo_4x4_snapshot(puzzle_id=puzzle_id or "MOCK_4x4_DEMO")
    if grid_size == 5:
        return build_demo_5x5_snapshot(puzzle_id=puzzle_id or "MOCK_5x5_DEMO")
    raise ValueError(f"Unsupported demo grid_size {grid_size!r}; expected 3, 4, or 5")


def build_demo_trace(grid_size: int, *, session_id: str = "demo-session") -> tuple[DeductionStepView, ...]:
    """Return synthetic mock deduction trace entries for UI scroll & color QA."""
    if grid_size == 3:
        return (
            DeductionStepView(
                session_id=session_id,
                request_id=1,
                kb_version=1,
                cell_id="B1",
                verdict="CRIMINAL",
                explanation="Suy luận từ lời khai công khai xác định B1 là tội phạm.",
                source_clue_ids=("CLUE_A1",),
                support_kind="PUBLIC_KB",
                sat_calls=3,
                elapsed_ms=1.4,
            ),
            DeductionStepView(
                session_id=session_id,
                request_id=2,
                kb_version=1,
                cell_id="C1",
                verdict="INNOCENT",
                explanation="Kết hợp các lời khai công khai chứng minh C1 là vô tội.",
                source_clue_ids=("CLUE_A1", "CLUE_B1"),
                support_kind="PUBLIC_KB",
                sat_calls=2,
                elapsed_ms=1.1,
                newly_revealed_clue_id="CLUE_C1",
            ),
        )

    if grid_size == 4:
        return (
            DeductionStepView(
                session_id=session_id,
                request_id=1,
                kb_version=1,
                cell_id="C1",
                verdict="CRIMINAL",
                explanation="Chứng minh C1 là CRIMINAL dựa trên các lời khai hiện có.",
                source_clue_ids=("CLUE_A1",),
                sat_calls=3,
                elapsed_ms=2.2,
            ),
            DeductionStepView(
                session_id=session_id,
                request_id=2,
                kb_version=2,
                cell_id="B2",
                verdict="INNOCENT",
                explanation="Đối chiếu lời khai hàng 1 và cột B xác nhận B2 là INNOCENT.",
                source_clue_ids=("CLUE_A1", "CLUE_C1"),
                sat_calls=4,
                elapsed_ms=3.1,
            ),
            DeductionStepView(
                session_id=session_id,
                request_id=3,
                kb_version=2,
                cell_id="C3",
                verdict="CRIMINAL",
                explanation="Số lượng tội phạm lân cận buộc C3 phải là CRIMINAL.",
                source_clue_ids=("CLUE_C1", "CLUE_B2"),
                support_kind="VERIFIED_SUBSET",
                sat_calls=5,
                elapsed_ms=2.8,
            ),
            DeductionStepView(
                session_id=session_id,
                request_id=4,
                kb_version=2,
                cell_id="D2",
                verdict="INNOCENT",
                explanation="Giới hạn tội phạm trên cột C và hàng 2 xác nhận D2 là INNOCENT.",
                source_clue_ids=("CLUE_B2", "CLUE_C3"),
                sat_calls=3,
                elapsed_ms=1.9,
            ),
        )

    # 5x5: 6 steps to test long trace scrolling
    return tuple(
        DeductionStepView(
            session_id=session_id,
            request_id=i,
            kb_version=i,
            cell_id=cell,
            verdict=verdict,
            explanation=f"Bước suy luận #{i:02d}: chứng minh ô {cell} là {verdict} từ các lời khai công khai.",
            source_clue_ids=clues,
            sat_calls=2 + i,
            elapsed_ms=1.5 + i * 0.4,
        )
        for i, (cell, verdict, clues) in enumerate(
            [
                ("C2", "CRIMINAL", ("CLUE_A1",)),
                ("D2", "INNOCENT", ("CLUE_A1", "CLUE_C2")),
                ("B4", "INNOCENT", ("CLUE_C2", "CLUE_D2")),
                ("A5", "INNOCENT", ("CLUE_B4",)),
                ("E5", "CRIMINAL", ("CLUE_B4", "CLUE_A5")),
                ("C4", "INNOCENT", ("CLUE_A5", "CLUE_E5")),
            ],
            start=1,
        )
    )


def build_demo_hint(*, session_id: str = "demo-session", cell_id: str = "C1") -> HintView:
    """Return a synthetic mock HintView (strictly non-mutating UI preview)."""
    return HintView(
        session_id=session_id,
        kb_version=1,
        outcome="FORCED",
        cell_id=cell_id,
        verdict="INNOCENT",
        text=f"Dựa trên các lời khai hiện tại, có thể chứng minh chắc chắn trạng thái của ô {cell_id}.",
        source_clue_ids=("CLUE_A1", "CLUE_B1"),
    )


def build_demo_notification(code: ActionCode, *, cell_id: str | None = "C1") -> ActionResult:
    """Return synthetic mock notifications for developer QA buttons."""
    messages = {
        ActionCode.ACCEPTED: "Phán quyết chính xác và đã được chứng minh bằng suy luận logic.",
        ActionCode.NOT_PROVABLE: "Chưa đủ dữ kiện công khai để chứng minh chắc chắn phán quyết này. Không lật thẻ.",
        ActionCode.CONTRADICTED: "Phán quyết mâu thuẫn với hệ quả logic của các manh mối công khai hiện tại.",
        ActionCode.INCONSISTENT: "Cơ sở tri thức công khai bị mâu thuẫn (UNSAT). Dừng suy luận tự động.",
    }
    return ActionResult(
        code=code,
        message=messages.get(code, f"Thông báo trạng thái {code.value}."),
        session_id="demo-session",
        kb_version=1,
        cell_id=cell_id,
    )


def build_demo_level_catalog() -> tuple[LevelSummary, ...]:
    """Return a synthetic 15-case public mock catalog (5×3×3, 5×4×4, 5×5×5).

    Does NOT read ``puzzles/manifest.json`` or any ``puzzles/*.json`` file.
    Does NOT fabricate experimental difficulty scores (``difficulty_label=None``).
    """
    entries: list[LevelSummary] = []
    from src.gui.case_catalog import OFFICIAL_CASE_CATALOG

    for grid_size in (3, 4, 5):
        for idx in range(1, 6):
            official_id = f"{grid_size}x{grid_size}_{idx:02d}"
            meta = OFFICIAL_CASE_CATALOG[official_id]
            entries.append(
                LevelSummary(
                    puzzle_id=f"MOCK_{official_id}",
                    title=f"{meta.full_title} (Dữ liệu mẫu)",
                    grid_size=grid_size,
                    difficulty_label=None,  # Never fabricate difficulty ratings
                )
            )
    return tuple(entries)


def build_demo_results_view(*, puzzle_id: str = "MOCK_3x3_01", grid_size: int = 3) -> ResultsView:
    """Return a synthetic preview ResultsView (explicitly marked ``is_demo_preview=True``)."""
    total = grid_size * grid_size
    if puzzle_id in OFFICIAL_PUZZLE_IDS:
        idx = OFFICIAL_PUZZLE_IDS.index(puzzle_id)
        next_id = OFFICIAL_PUZZLE_IDS[idx + 1] if idx + 1 < len(OFFICIAL_PUZZLE_IDS) else None
    else:
        next_id = "MOCK_4x4_01" if grid_size == 3 else ("MOCK_5x5_01" if grid_size == 4 else None)
    return ResultsView(
        session_id=f"demo-preview-{puzzle_id}",
        puzzle_id=puzzle_id,
        revealed=total,
        total=total,
        accepted_steps=max(1, total - 2),
        hint_requests=1,
        elapsed_ms=42800.0,
        sat_calls=None,  # Explicitly None when no real solver ran
        next_puzzle_id=next_id,
        grid_size=grid_size,
        is_demo_preview=True,
    )


# ---------------------------------------------------------------------------
# Phase C5 — Official Public Roster Demo Fixtures (Public Metadata ONLY)
# ---------------------------------------------------------------------------
# Uses ONLY public character metadata (puzzle_id, cell_id, character_name,
# profession) from assets/characters/portrait_manifest.json via PortraitRegistry.
# NEVER reads puzzles/*.json, NEVER accesses hidden_solution, NEVER runs SAT.

OFFICIAL_PUZZLE_IDS: tuple[str, ...] = (
    "3x3_01",
    "3x3_02",
    "3x3_03",
    "3x3_04",
    "3x3_05",
    "4x4_01",
    "4x4_02",
    "4x4_03",
    "4x4_04",
    "4x4_05",
    "5x5_01",
    "5x5_02",
    "5x5_03",
    "5x5_04",
    "5x5_05",
)

from src.gui.case_catalog import OFFICIAL_CASE_CATALOG as _OFFICIAL_CASE_CATALOG

_OFFICIAL_CASE_TITLES: dict[str, str] = {
    pid: meta.full_title for pid, meta in _OFFICIAL_CASE_CATALOG.items()
}

# Synthetic demo-only revealed verdicts for visual QA of Hidden vs Revealed cards.
# (Strictly synthetic UI preview — NOT derived from hidden_solution!)
_DEMO_SYNTHETIC_REVEALED_BY_SIZE: dict[int, dict[str, str]] = {
    3: {"A1": "INNOCENT", "B1": "CRIMINAL"},
    4: {"A1": "INNOCENT", "C1": "CRIMINAL", "B2": "INNOCENT", "C3": "CRIMINAL"},
    5: {
        "A1": "INNOCENT",
        "C2": "CRIMINAL",
        "D2": "INNOCENT",
        "B4": "INNOCENT",
        "A5": "INNOCENT",
        "E5": "CRIMINAL",
    },
}


def build_official_public_level_catalog() -> tuple[LevelSummary, ...]:
    """Return all 15 official puzzle IDs (3x3_01..5x5_05) using public metadata ONLY."""
    entries: list[LevelSummary] = []
    for pid in OFFICIAL_PUZZLE_IDS:
        gs = 3 if pid.startswith("3x3_") else (4 if pid.startswith("4x4_") else 5)
        entries.append(
            LevelSummary(
                puzzle_id=pid,
                title=_OFFICIAL_CASE_TITLES.get(pid, f"Hồ sơ {pid}"),
                grid_size=gs,
                difficulty_label=None,
            )
        )
    return tuple(entries)


def build_official_public_snapshot(
    puzzle_id: str = "3x3_01",
    *,
    include_demo_reveals: bool = True,
) -> PublicBoardSnapshot:
    """Build a public-only ``PublicBoardSnapshot`` for any of the 15 official cases.

    Reads character ``(name, profession)`` exclusively from ``PortraitRegistry``
    (``assets/characters/portrait_manifest.json``). Never touches ``puzzles/*.json``
    or ``hidden_solution``.
    """
    from src.gui.assets.portrait_registry import default_portrait_registry

    pid = puzzle_id.strip()
    if pid not in OFFICIAL_PUZZLE_IDS:
        raise ValueError(f"Unknown official puzzle_id {pid!r}; expected one of {OFFICIAL_PUZZLE_IDS}")

    gs = 3 if pid.startswith("3x3_") else (4 if pid.startswith("4x4_") else 5)
    reg = default_portrait_registry()
    synth_reveals = _DEMO_SYNTHETIC_REVEALED_BY_SIZE.get(gs, {}) if include_demo_reveals else {}

    chars: list[PublicCharacterView] = []
    for r in range(gs):
        for c in range(gs):
            cid = f"{chr(ord('A') + c)}{r + 1}"
            entry = reg.get_mapping(pid, cid)
            name = entry.character_name if entry is not None else f"Suspect {cid}"
            prof = entry.profession if entry is not None else "Unknown"
            verdict = synth_reveals.get(cid)
            vis = CardVisibility.REVEALED if verdict is not None else CardVisibility.HIDDEN
            chars.append(
                PublicCharacterView(
                    cell_id=cid,
                    name=name,
                    profession=prof,
                    row=r,
                    col=c,
                    visibility=vis,
                    verdict=verdict,
                    has_public_clue=(verdict is not None),
                )
            )

    by_id = {ch.cell_id: ch for ch in chars}
    if gs == 3:
        clues = (
            PublicClueView(
                clue_id="CLUE_A1",
                owner_id="A1",
                clue_type="EXACTLY",
                text=f"Hàng 1 ({by_id['A1'].name}, {by_id['B1'].name}, {by_id['C1'].name}) có đúng 1 CRIMINAL.",
                referenced_cells=("A1", "B1", "C1"),
            ),
            PublicClueView(
                clue_id="CLUE_B1",
                owner_id="B1",
                clue_type="DIFFERENT",
                text=f"{by_id['C1'].name} (C1 · {by_id['C1'].profession}) và {by_id['A2'].name} (A2 · {by_id['A2'].profession}) khác phe.",
                referenced_cells=("C1", "A2"),
            ),
        )
    elif gs == 4:
        clues = (
            PublicClueView(
                clue_id="CLUE_A1",
                owner_id="A1",
                clue_type="FACT",
                text=f"Xác nhận {by_id['A1'].name} (A1 · {by_id['A1'].profession}) là INNOCENT.",
                referenced_cells=("A1",),
            ),
            PublicClueView(
                clue_id="CLUE_C1",
                owner_id="C1",
                clue_type="SAME",
                text=f"{by_id['B1'].name} (B1) và {by_id['D1'].name} (D1) có cùng trạng thái.",
                referenced_cells=("B1", "D1"),
            ),
            PublicClueView(
                clue_id="CLUE_B2",
                owner_id="B2",
                clue_type="AT_LEAST",
                text=f"Các ô lân cận của {by_id['B2'].name} (B2 · {by_id['B2'].profession}) có ít nhất 2 CRIMINAL.",
                referenced_cells=("A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3"),
            ),
            PublicClueView(
                clue_id="CLUE_C3",
                owner_id="C3",
                clue_type="AT_MOST",
                text="Cột C (C1..C4) có nhiều nhất 2 nghi phạm là CRIMINAL.",
                referenced_cells=("C1", "C2", "C3", "C4"),
            ),
        )
    else:
        clues = (
            PublicClueView(
                clue_id="CLUE_A1",
                owner_id="A1",
                clue_type="FACT",
                text=f"Xác nhận {by_id['A1'].name} (A1 · {by_id['A1'].profession}) là INNOCENT.",
                referenced_cells=("A1",),
            ),
            PublicClueView(
                clue_id="CLUE_C2",
                owner_id="C2",
                clue_type="SAME",
                text=f"{by_id['B1'].name} (B1) và {by_id['E1'].name} (E1) có cùng trạng thái.",
                referenced_cells=("B1", "E1"),
            ),
            PublicClueView(
                clue_id="CLUE_D2",
                owner_id="D2",
                clue_type="DIFFERENT",
                text=f"{by_id['A2'].name} (A2) và {by_id['B2'].name} (B2) thuộc hai phe đối lập.",
                referenced_cells=("A2", "B2"),
            ),
            PublicClueView(
                clue_id="CLUE_B4",
                owner_id="B4",
                clue_type="EXACTLY",
                text="Hàng 4 (A4..E4) có chính xác 2 nghi phạm là CRIMINAL.",
                referenced_cells=("A4", "B4", "C4", "D4", "E4"),
            ),
            PublicClueView(
                clue_id="CLUE_A5",
                owner_id="A5",
                clue_type="AT_LEAST",
                text=f"Vùng lân cận của {by_id['A4'].name} (A4) có ít nhất 1 CRIMINAL.",
                referenced_cells=("A3", "B3", "B4", "A5", "B5"),
            ),
            PublicClueView(
                clue_id="CLUE_E5",
                owner_id="E5",
                clue_type="AT_MOST",
                text="Cột E (E1..E5) có nhiều nhất 2 nghi phạm là CRIMINAL.",
                referenced_cells=("E1", "E2", "E3", "E4", "E5"),
            ),
        )

    return PublicBoardSnapshot(
        session_id=f"official-public-{pid}",
        puzzle_id=pid,
        grid_size=gs,
        kb_version=1,
        characters=tuple(chars),
        clues=clues if include_demo_reveals else (),
    )
