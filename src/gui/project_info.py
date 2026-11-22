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
PROJECT_SUBTITLE: str = "Hồ Sơ Phá Án — Trò Chơi Suy Luận Logic"
COURSE_LABEL: str = "CSC14003 · Cơ sở Trí tuệ Nhân tạo · HCMUS"

PROJECT_INTRO_PARAGRAPHS: tuple[str, ...] = (
    (
        "GRIDUCTIVE SOLVER là đồ án môn Cơ sở Trí tuệ Nhân tạo, xây dựng hệ thống "
        "giải trò chơi suy luận logic Griductive."
    ),
    (
        "Người chơi điều tra các nghi phạm trên bàn cờ 3×3, 4×4 hoặc 5×5, sử dụng "
        "những manh mối đã được công khai để xác định ai là Tội phạm và ai là Vô tội. "
        "Điểm đặc trưng của trò chơi là nguyên tắc Không Đoán Mò: người chơi chỉ được đưa ra "
        "kết luận khi trạng thái của nghi phạm có thể được chứng minh chắc chắn bằng logic."
    ),
    (
        "Hệ thống sử dụng biểu diễn mệnh đề chuẩn hội (CNF), thuật toán suy diễn logic DPLL "
        "và cơ chế kiểm chứng hệ quả để xác định các kết luận hợp lệ. Ứng dụng máy tính "
        "được xây dựng bằng Python và PySide6."
    ),
)

TECH_SPECS: tuple[tuple[str, str], ...] = (
    ("Ngôn ngữ", "Python"),
    ("Nền tảng giao diện", "PySide6"),
    ("Phương pháp AI", "CNF, DPLL, Suy diễn logic"),
    ("Nguyên tắc trò chơi", "Không đoán mò"),
    ("Kích thước bàn cờ", "3×3 / 4×4 / 5×5"),
)

TEAM_MEMBERS: tuple[TeamMemberInfo, ...] = (
    TeamMemberInfo("24122015", "Mai Hoàng Hiệp", "Điều phối & Tích hợp hệ thống"),
    TeamMemberInfo("24122022", "Nguyễn Hoài Phước", "Kỹ sư Giao diện người dùng"),
    TeamMemberInfo("24122035", "Phan Nguyễn Gia Huy", "Kiểm thử & Đánh giá hiệu năng"),
    TeamMemberInfo("24122009", "Phan Thế Phong", "Tài liệu & Báo cáo đồ án"),
    TeamMemberInfo("24122051", "Nguyễn Đức Tài", "Tác tử Suy luận Logic"),
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
