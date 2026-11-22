"""Public presentation catalog for Detective Case Files (Option 1 — Editorial Naming).

Pure-Python UI display metadata mapping official puzzle IDs (``3x3_01``..``5x5_05``)
to concise Vietnamese detective case numbers (``#01``..``#15``), editorial titles,
and localized difficulty labels.

Strictly presentation-only: ZERO imports from ``src.core``, ``src.solvers``,
``src.encoder``, ``src.agent``, or ``src.controller``; never reads puzzle JSON
files or hidden solutions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CaseDisplayMeta:
    """Editorial display title and sequential case index for an official puzzle."""

    case_number: str
    name: str

    @property
    def full_title(self) -> str:
        return f"{self.case_number} · {self.name}"


OFFICIAL_CASE_CATALOG: dict[str, CaseDisplayMeta] = {
    "3x3_01": CaseDisplayMeta("#01", "Thư viện nửa đêm"),
    "3x3_02": CaseDisplayMeta("#02", "Chìa khóa phòng lưu trữ"),
    "3x3_03": CaseDisplayMeta("#03", "Nhân chứng hành lang"),
    "3x3_04": CaseDisplayMeta("#04", "Vết mực trên bản đồ"),
    "3x3_05": CaseDisplayMeta("#05", "Chuyến tàu cuối ngày"),
    "4x4_01": CaseDisplayMeta("#06", "Bảo tàng cổ vật"),
    "4x4_02": CaseDisplayMeta("#07", "Cuộc họp kín tại cảng"),
    "4x4_03": CaseDisplayMeta("#08", "Bức thư không ký tên"),
    "4x4_04": CaseDisplayMeta("#09", "Đồng hồ tháp chuông"),
    "4x4_05": CaseDisplayMeta("#10", "Căn phòng khóa trái"),
    "5x5_01": CaseDisplayMeta("#11", "Mạng lưới gián điệp"),
    "5x5_02": CaseDisplayMeta("#12", "Hồ sơ mật khu công nghiệp"),
    "5x5_03": CaseDisplayMeta("#13", "Sương mù ga trung tâm"),
    "5x5_04": CaseDisplayMeta("#14", "Két sắt ngân hàng"),
    "5x5_05": CaseDisplayMeta("#15", "Chuyên án tổng lực"),
}

_DIFFICULTY_VI_MAP: dict[str, str] = {
    "tutorial": "Nhập môn",
    "easy": "Dễ",
    "medium": "Trung bình",
    "hard": "Khó",
    "very hard": "Rất khó",
    "nhập môn": "Nhập môn",
    "dễ": "Dễ",
    "trung bình": "Trung bình",
    "khó": "Khó",
    "rất khó": "Rất khó",
}

_DIFFICULTY_TONE_MAP: dict[str, str] = {
    "tutorial": "paperInfo",
    "nhập môn": "paperInfo",
    "easy": "paperNeutral",
    "dễ": "paperNeutral",
    "medium": "paperNeutral",
    "trung bình": "paperNeutral",
    "hard": "paperAccent",
    "khó": "paperAccent",
    "very hard": "paperAccent",
    "rất khó": "paperAccent",
}

_PROFESSION_VI_MAP: dict[str, str] = {
    "analyst": "Phân tích viên",
    "artist": "Họa sĩ",
    "astronomer": "Nhà thiên văn",
    "baker": "Thợ làm bánh",
    "barista": "Nhân viên pha chế",
    "carpenter": "Thợ mộc",
    "chef": "Đầu bếp trưởng",
    "chemist": "Nhà hóa học",
    "clerk": "Thư ký",
    "cook": "Đầu bếp",
    "detective": "Thám tử",
    "doctor": "Bác sĩ",
    "engineer": "Kỹ sư",
    "florist": "Người bán hoa",
    "guard": "Bảo vệ",
    "historian": "Nhà sử học",
    "illustrator": "Họa sĩ minh họa",
    "journalist": "Nhà báo",
    "lawyer": "Luật sư",
    "librarian": "Thủ thư",
    "musician": "Nhạc sĩ",
    "nurse": "Y tá",
    "painter": "Họa sĩ",
    "photographer": "Nhiếp ảnh gia",
    "pilot": "Phi công",
    "tailor": "Thợ may",
    "teacher": "Giáo viên",
    "watchmaker": "Thợ đồng hồ",
}


def localize_profession(profession: Optional[str]) -> str:
    """Translate English character profession labels into concise Vietnamese for display."""
    if not profession:
        return ""
    cleaned = profession.strip()
    if not cleaned:
        return ""
    return _PROFESSION_VI_MAP.get(cleaned.lower(), cleaned)


def localize_verdict(verdict: Optional[str], *, uppercase: bool = False) -> str:
    """Translate internal verdict token (CRIMINAL / INNOCENT) to Vietnamese display label."""
    if verdict == "CRIMINAL":
        return "TỘI PHẠM" if uppercase else "Tội phạm"
    if verdict == "INNOCENT":
        return "VÔ TỘI" if uppercase else "Vô tội"
    return "CHƯA XÁC ĐỊNH" if uppercase else "Chưa xác định"


def get_case_display_meta(puzzle_id: str) -> Optional[CaseDisplayMeta]:
    """Return official editorial metadata for ``puzzle_id`` if registered."""
    return OFFICIAL_CASE_CATALOG.get(puzzle_id.strip())


def format_case_title(puzzle_id: str, fallback_title: Optional[str] = None) -> str:
    """Return canonical ``#NN · Tên vụ án`` for official puzzles, or a clean fallback."""
    meta = get_case_display_meta(puzzle_id)
    if meta is not None:
        return meta.full_title
    if fallback_title and fallback_title.strip():
        return fallback_title.strip()
    return f"Hồ sơ {puzzle_id}"


def split_case_number_and_name(puzzle_id: str, title: str) -> tuple[Optional[str], str]:
    """Split a case entry into ``(case_number, clean_title)`` for aligned rendering.

    Handles both official catalog titles (``#01 · Thư viện nửa đêm``) and legacy
    placeholder titles (``Hồ sơ 3x3_01``) as well as demo titles prefixed with ``#NN · ``.
    """
    cleaned = title.strip()
    meta = get_case_display_meta(puzzle_id)
    if meta is not None and cleaned in (
        f"Hồ sơ {puzzle_id}",
        puzzle_id,
        meta.full_title,
        meta.name,
    ):
        return (meta.case_number, meta.name)

    if cleaned.startswith("#") and " · " in cleaned:
        prefix, rest = cleaned.split(" · ", 1)
        if len(prefix) <= 5 and rest.strip():
            return (prefix.strip(), rest.strip())

    return (None, cleaned)


def localize_difficulty(label: Optional[str]) -> Optional[str]:
    """Translate standard English manifest difficulty labels into concise Vietnamese."""
    if label is None:
        return None
    cleaned = label.strip()
    if not cleaned:
        return None
    return _DIFFICULTY_VI_MAP.get(cleaned.lower(), cleaned)


def difficulty_pill_tone(label: Optional[str]) -> str:
    """Return the Cream Detective Editorial StatusLabel tone for a difficulty pill."""
    if not label:
        return "paperNeutral"
    return _DIFFICULTY_TONE_MAP.get(label.strip().lower(), "paperNeutral")


def format_gameplay_case_header(puzzle_id: str, grid_size: int) -> str:
    """Format the Gameplay top-bar case heading cleanly without duplicating grid text."""
    meta = get_case_display_meta(puzzle_id)
    if meta is not None:
        return f"Hồ sơ {meta.case_number} · {meta.name}  ·  Bàn cờ {grid_size}×{grid_size}"
    return f"Hồ sơ: {puzzle_id}  ·  Bàn cờ {grid_size}×{grid_size}"


__all__ = [
    "CaseDisplayMeta",
    "OFFICIAL_CASE_CATALOG",
    "difficulty_pill_tone",
    "format_case_title",
    "format_gameplay_case_header",
    "get_case_display_meta",
    "localize_difficulty",
    "localize_profession",
    "localize_verdict",
    "split_case_number_and_name",
]
