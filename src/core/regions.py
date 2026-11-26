"""Named spatial regions, independent of SAT variables and hidden statuses.

Coordinates are zero-based. Odd boards exclude the middle row/column from
both halves; CENTER is the interior (all cells except the outer border).
"""

SPATIAL_REGIONS = frozenset({
    "CORNERS", "BORDER", "CENTER", "TOP_HALF", "BOTTOM_HALF", "LEFT_HALF", "RIGHT_HALF",
})


def in_spatial_region(kind: str, row: int, col: int, size: int) -> bool:
    edge_row, edge_col = row in (0, size - 1), col in (0, size - 1)
    if kind == "CORNERS":
        return edge_row and edge_col
    if kind == "BORDER":
        return edge_row or edge_col
    if kind == "CENTER":
        return not edge_row and not edge_col
    if kind == "TOP_HALF":
        return row < size // 2
    if kind == "BOTTOM_HALF":
        return row >= (size + 1) // 2
    if kind == "LEFT_HALF":
        return col < size // 2
    if kind == "RIGHT_HALF":
        return col >= (size + 1) // 2
    raise ValueError(f"Unsupported spatial region {kind!r}")
