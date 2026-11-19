"""Centralized project metadata, team roster, and external links for GRIDUCTIVE.

Pure-Python configuration module (zero PySide6 dependency) so GitHub / YouTube
URLs and team information are maintained in a single authoritative place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class TeamMemberInfo:
    """Confirmed project team member entry."""

    student_id: str
    full_name: str
    stage2_role: str


PROJECT_TITLE: str = "GRIDUCTIVE SOLVER"
PROJECT_SUBTITLE: str = "Detective Case Files — Logic Deduction Game"
COURSE_LABEL: str = "CSC14003 · Cơ sở Trí tuệ Nhân tạo · HCMUS"

PROJECT_INTRO_PARAGRAPHS: tuple[str, ...] = (
    (
        "Griductive Solver là đồ án môn Cơ sở Trí tuệ Nhân tạo, xây dựng hệ thống "
        "giải trò chơi suy luận logic Griductive."
    ),
    (
        "Người chơi điều tra các nghi phạm trên bàn cờ 3×3, 4×4 hoặc 5×5, sử dụng "
        "những manh mối đã được công khai để xác định ai là Criminal và ai là Innocent. "
        "Điểm đặc trưng của trò chơi là nguyên tắc No-Guess: người chơi chỉ được đưa ra "
        "kết luận khi trạng thái của nghi phạm có thể được chứng minh chắc chắn bằng logic."
    ),
    (
        "Hệ thống sử dụng biểu diễn CNF, thuật toán DPLL SAT Solver và kiểm tra suy diễn "
        "logic để xác định các kết luận hợp lệ. Giao diện desktop được xây dựng bằng "
        "Python và PySide6."
    ),
)

TECH_SPECS: tuple[tuple[str, str], ...] = (
    ("Language", "Python"),
    ("GUI Framework", "PySide6"),
    ("AI Methods", "CNF, DPLL, SAT Entailment"),
    ("Game Principle", "No-Guess"),
    ("Supported Boards", "3×3 / 4×4 / 5×5"),
)

TEAM_MEMBERS: tuple[TeamMemberInfo, ...] = (
    TeamMemberInfo("24122015", "Mai Hoàng Hiệp", "Controller / Integration"),
    TeamMemberInfo("24122022", "Nguyễn Hoài Phước", "GUI Engineer"),
    TeamMemberInfo("24122035", "Phan Nguyễn Gia Huy", "Benchmark / Testing"),
    TeamMemberInfo("24122009", "Phan Thế Phong", "Documentation / Report"),
    TeamMemberInfo("24122051", "Nguyễn Đức Tài", "Deductive Logic Agent"),
)

GITHUB_REPO_URL: str = "https://github.com/hoanghiep06/Griductive_Solver"
# Update this constant once an official project demo video URL is published.
YOUTUBE_DEMO_URL: Optional[str] = None


def is_valid_external_url(url: Optional[str]) -> bool:
    """Return True only for well-formed http(s) external URLs."""
    if not isinstance(url, str):
        return False
    cleaned = url.strip()
    if not cleaned:
        return False
    parsed = urlparse(cleaned)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
