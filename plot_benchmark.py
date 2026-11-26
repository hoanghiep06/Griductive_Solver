"""
Modern Aesthetic Benchmark Visualization for Griductive Solver (Project 2 - CSC14003).
Author: Huy (TV 4 - Benchmark Automation Lead)

Redesigned with modern, publication-grade aesthetics:
- Tailwind / Modern Minimalist color palette (Indigo, Cyan, Rose/Coral)
- Frameless clean layout with subtle slate gridlines and despine styling
- Elegant typography, badges, and clean metric annotations
- 300 DPI high-resolution output for report inclusion
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Modern Aesthetic Theme & Design System
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Inter", "Helvetica Neue", "Arial", "sans-serif"],
    "font.size": 10,
    "text.color": "#1E293B",
    "axes.labelcolor": "#334155",
    "axes.edgecolor": "#CBD5E1",
    "axes.linewidth": 1.0,
    "xtick.color": "#64748B",
    "ytick.color": "#64748B",
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": "#FFFFFF",
    "grid.color": "#F1F5F9",
    "grid.linestyle": "--",
    "grid.alpha": 0.8,
})

# Modern Tailwind/SaaS Palette
COLOR_3X3 = "#6366F1"      # Vibrant Indigo
COLOR_4X4 = "#0EA5E9"      # Ocean Sky Blue
COLOR_5X5 = "#F43F5E"      # Vibrant Rose / Coral
COLOR_ACCENT = "#8B5CF6"   # Purple Violet
COLOR_EMERALD = "#10B981"  # Emerald Green
COLOR_AMBER = "#F59E0B"    # Warm Amber
COLOR_SLATE_DARK = "#0F172A"
COLOR_SLATE_MUTED = "#64748B"


def despine(ax: plt.Axes) -> None:
    """Remove top and right spines for a clean modern look."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E2E8F0")
    ax.spines["bottom"].set_color("#CBD5E1")


def load_benchmark_data(csv_path: Path | str) -> List[Dict[str, Any]]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Benchmark CSV file not found: {csv_path.resolve()}")

    records: List[Dict[str, Any]] = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "puzzle_id": row["puzzle_id"],
                "grid_size": int(row["grid_size"]),
                "status": row["status"],
                "primary_vars": int(row["primary_vars"]),
                "aux_vars": int(row["aux_vars"]),
                "total_vars": int(row["total_vars"]),
                "total_clauses": int(row["total_clauses"]),
                "clause_to_var_ratio": float(row["clause_to_var_ratio"]),
                "sat_calls": int(row["sat_calls"]),
                "decisions": int(row["decisions"]),
                "propagations": int(row["propagations"]),
                "backtracks": int(row["backtracks"]),
                "prop_to_dec_ratio": float(row["prop_to_dec_ratio"]),
                "backtrack_rate": float(row["backtrack_rate"]),
                "deduction_steps": int(row["deduction_steps"]),
                "runtime_ms": float(row["runtime_ms"]),
            })
    return records


# ---------------------------------------------------------------------------
# Figure 1: Runtime Scaling Across Puzzle Sizes
# ---------------------------------------------------------------------------
def plot_runtime(records: List[Dict[str, Any]], output_path: Path) -> None:
    puzzles = [r["puzzle_id"] for r in records]
    runtimes = [r["runtime_ms"] for r in records]
    sizes = [r["grid_size"] for r in records]

    palette = [COLOR_3X3 if s == 3 else COLOR_4X4 if s == 4 else COLOR_5X5 for s in sizes]

    fig, ax = plt.subplots(figsize=(11.5, 5.8), dpi=300)
    bars = ax.bar(puzzles, runtimes, color=palette, width=0.62, alpha=0.92, zorder=3)

    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.65, zorder=0, which="both")
    despine(ax)

    ax.set_ylabel("Thời gian chạy (ms) — Thang đo Logarithm", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_xlabel("Mã Puzzle", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_title("Thời Gian Thực Thi (Runtime) Theo Từng Kích Thước Bàn Cờ", fontsize=13, fontweight="bold", pad=16, color=COLOR_SLATE_DARK)

    # Data value badges on top of bars
    for bar, val in zip(bars, runtimes):
        h = bar.get_height()
        label = f"{val:.1f}ms" if val < 1000 else f"{val/1000:.2f}s"
        ax.annotate(
            label,
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#334155",
            rotation=20,
        )

    # Stylish legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLOR_3X3, label="3×3 Maps (TB: 25.8 ms)"),
        Patch(facecolor=COLOR_4X4, label="4×4 Maps (TB: 440.6 ms)"),
        Patch(facecolor=COLOR_5X5, label="5×5 Stress Tests (TB: 3.03 s)"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="upper left",
        frameon=True,
        facecolor="#F8FAFC",
        edgecolor="#E2E8F0",
        fontsize=9.5,
        borderpad=0.8,
    )

    plt.xticks(rotation=40, ha="right", fontsize=9.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Figure 2: Decisions, Backtracks & Propagations
# ---------------------------------------------------------------------------
def plot_dpll_metrics(records: List[Dict[str, Any]], output_path: Path) -> None:
    puzzles = [r["puzzle_id"] for r in records]
    decisions = [r["decisions"] for r in records]
    backtracks = [r["backtracks"] for r in records]
    propagations = [r["propagations"] for r in records]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12.5, 9.5), dpi=300)

    x = np.arange(len(puzzles))
    width = 0.36

    # Subplot A: Decisions vs Backtracks with Dual Y-Axis
    ax1_twin = ax1.twinx()

    bar1 = ax1.bar(x - width/2, decisions, width, label="Decisions (Phân nhánh - Trục trái)", color="#6366F1", alpha=0.9, zorder=3)
    bar2 = ax1_twin.bar(x + width/2, backtracks, width, label="Backtracks (Quay lui - Trục phải)", color="#F43F5E", alpha=0.9, zorder=3)

    ax1.set_ylabel("Số lượt Phân nhánh (Decisions)", fontsize=10.5, fontweight="bold", color="#4338CA")
    ax1_twin.set_ylabel("Số lượt Quay lui (Backtracks)", fontsize=10.5, fontweight="bold", color="#BE123C")
    ax1.tick_params(axis='y', labelcolor="#4338CA")
    ax1_twin.tick_params(axis='y', labelcolor="#BE123C")

    # Set proportional limits so red bars are clearly visible and correspond nicely to blue bars
    max_dec = max(decisions) if decisions else 2500
    max_back = max(backtracks) if backtracks else 150
    ax1.set_ylim(0, max_dec * 1.15)
    ax1_twin.set_ylim(0, max_back * 1.15)

    ax1.set_title("(A) So Sánh Giữa Phân Nhánh (Decisions) Và Quay Lui (Backtracks) — Trục Tung Kép", fontsize=12, fontweight="bold", color=COLOR_SLATE_DARK, pad=10)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    despine(ax1)
    despine(ax1_twin)

    # Combined legend
    lines = [bar1, bar2]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left", frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=9.5)

    # Highlight backtracks > 0 with annotations
    for i, b in enumerate(backtracks):
        if b > 0:
            ax1_twin.annotate(
                f"{b}",
                (x[i] + width/2, b),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color="#BE123C",
            )

    # Explicit x-ticks for ax1 so horizontal axis is 100% clear
    ax1.set_xticks(x)
    ax1.set_xticklabels(puzzles, rotation=35, ha="right", fontsize=9.0)
    ax1.set_xlabel("Mã Puzzle (Kích thước: 3x3 → 4x4 → 5x5)", fontsize=10.0, fontweight="bold", labelpad=6)

    # Subplot B: Unit Propagations
    ax2.bar(x, propagations, width=0.55, color="#0EA5E9", alpha=0.9, zorder=3, label="Unit Propagations (Lan truyền đơn vị)")
    ax2.set_ylabel("Số lượng lan truyền", fontsize=10.5, fontweight="bold")
    ax2.set_title("(B) Sức Mạnh Lan Truyền Mệnh Đề Đơn Vị (Đạt đỉnh >129,000 lần ở 5×5_02)", fontsize=12, fontweight="bold", color=COLOR_SLATE_DARK, pad=10)
    ax2.set_xlabel("Mã Puzzle", fontsize=10.5, fontweight="bold", labelpad=8)
    ax2.grid(axis="y", linestyle="--", alpha=0.6, zorder=0)
    despine(ax2)
    ax2.legend(loc="upper left", frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=9.5)

    # Annotate top propagation peaks
    for i, p in enumerate(propagations):
        if p > 15000:
            ax2.annotate(
                f"{p:,}",
                (x[i], p),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#0369A1",
            )

    ax2.set_xticks(x)
    ax2.set_xticklabels(puzzles, rotation=35, ha="right", fontsize=9.0)

    # Add section separator lines between 3x3, 4x4, 5x5
    for ax in (ax1, ax2):
        ax.axvline(4.5, color="#94A3B8", linestyle=":", linewidth=1.2, alpha=0.7)
        ax.axvline(9.5, color="#94A3B8", linestyle=":", linewidth=1.2, alpha=0.7)

    # Add region label annotations at top
    ax1.text(2.0, max_dec * 1.05, "Lưới 3×3", ha="center", fontsize=9, fontweight="bold", color="#64748B")
    ax1.text(7.0, max_dec * 1.05, "Lưới 4×4", ha="center", fontsize=9, fontweight="bold", color="#64748B")
    ax1.text(12.0, max_dec * 1.05, "Lưới 5×5 (Stress)", ha="center", fontsize=9, fontweight="bold", color="#64748B")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Figure 3: Complexity Growth (Variables & Clauses)
# ---------------------------------------------------------------------------
def plot_complexity_growth(records: List[Dict[str, Any]], output_path: Path) -> None:
    puzzles = [r["puzzle_id"] for r in records]
    primary_vars = [r["primary_vars"] for r in records]
    aux_vars = [r["aux_vars"] for r in records]
    total_clauses = [r["total_clauses"] for r in records]

    fig, ax1 = plt.subplots(figsize=(11.5, 5.8), dpi=300)

    x = np.arange(len(puzzles))
    width = 0.52

    # Stacked Bars: Primary + Auxiliary Variables
    ax1.bar(x, primary_vars, width, label="Biến chính (Primary: N²)", color="#6366F1", alpha=0.92, zorder=3)
    ax1.bar(x, aux_vars, width, bottom=primary_vars, label="Biến phụ (Auxiliary Variables)", color="#38BDF8", alpha=0.92, zorder=3)

    ax1.set_ylabel("Số lượng Biến Mệnh đề", fontsize=11, fontweight="bold", color="#3730A3")
    ax1.set_xlabel("Mã Puzzle", fontsize=11, fontweight="bold", labelpad=8)
    ax1.grid(axis="y", linestyle="--", alpha=0.6, zorder=0)
    despine(ax1)

    # Secondary Axis: Total CNF Clauses line
    ax2 = ax1.twinx()
    ax2.plot(x, total_clauses, color="#F59E0B", marker="o", linewidth=2.4, markersize=6.5, label="Số lượng Mệnh đề CNF (Trục phải)", zorder=4)
    ax2.set_ylabel("Số lượng Mệnh đề CNF", fontsize=11, fontweight="bold", color="#B45309")
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.spines["right"].set_color("#FDE68A")

    # Combine legends cleanly
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=9.5)

    ax1.set_xticks(x)
    ax1.set_xticklabels(puzzles, rotation=40, ha="right", fontsize=9.5)
    ax1.set_title("Sự Tăng Trưởng Biến Phụ Và Mệnh Đề CNF Khi Mở Rộng Bàn Cờ", fontsize=13, fontweight="bold", pad=16, color=COLOR_SLATE_DARK)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Figure 4: Master 2x2 Summary Dashboard
# ---------------------------------------------------------------------------
def plot_summary_dashboard(records: List[Dict[str, Any]], output_path: Path) -> None:
    sizes = [r["grid_size"] for r in records]
    puzzles = [r["puzzle_id"] for r in records]
    decisions = [r["decisions"] for r in records]
    backtracks = [r["backtracks"] for r in records]
    propagations = [r["propagations"] for r in records]
    total_vars = [r["total_vars"] for r in records]
    aux_vars = [r["aux_vars"] for r in records]
    clauses = [r["total_clauses"] for r in records]

    fig, axs = plt.subplots(2, 2, figsize=(15.5, 10.5), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")

    # Panel (A): Runtime Average
    avg_runtimes = [
        np.mean([r["runtime_ms"] for r in records if r["grid_size"] == 3]),
        np.mean([r["runtime_ms"] for r in records if r["grid_size"] == 4]),
        np.mean([r["runtime_ms"] for r in records if r["grid_size"] == 5]),
    ]
    bars_a = axs[0, 0].bar(["3×3 (5 maps)", "4×4 (5 maps)", "5×5 Stress (5 maps)"], avg_runtimes, color=[COLOR_3X3, COLOR_4X4, COLOR_5X5], width=0.55, alpha=0.9, zorder=3)
    axs[0, 0].set_yscale("log")
    axs[0, 0].set_ylabel("Thời gian chạy TB (ms) — Log Scale", fontweight="bold", fontsize=10)
    axs[0, 0].set_title("(A) Thời Gian Giải Trung Bình Theo Kích Thước Bàn Cờ", fontweight="bold", fontsize=11.5, pad=10, color=COLOR_SLATE_DARK)
    axs[0, 0].grid(axis="y", linestyle="--", alpha=0.6, zorder=0, which="both")
    despine(axs[0, 0])
    for bar, val in zip(bars_a, avg_runtimes):
        txt = f"{val:.1f} ms" if val < 1000 else f"{val/1000:.2f} s"
        axs[0, 0].annotate(txt, (bar.get_x() + bar.get_width() / 2, bar.get_height()), xytext=(0, 4), textcoords="offset points", ha="center", fontweight="bold", fontsize=9.5, color="#1E293B")

    # Panel (B): Backtracks
    axs[0, 1].plot(puzzles, backtracks, marker="o", color=COLOR_5X5, linewidth=2.0, markersize=6, label="Số lần Backtrack (Quay lui)", zorder=3)
    axs[0, 1].set_ylabel("Số lượng Quay lui", fontweight="bold", fontsize=10)
    axs[0, 1].set_title("(B) Bùng Nổ Xung Đột & Quay Lui (0 ở 3x3 -> 86 ở 5x5)", fontweight="bold", fontsize=11.5, pad=10, color=COLOR_SLATE_DARK)
    axs[0, 1].grid(True, linestyle="--", alpha=0.6, zorder=0)
    axs[0, 1].tick_params(axis="x", rotation=40)
    despine(axs[0, 1])
    axs[0, 1].axvspan(-0.5, 4.5, color=COLOR_3X3, alpha=0.08, label="3×3 (0 quay lui)")
    axs[0, 1].axvspan(4.5, 9.5, color=COLOR_4X4, alpha=0.08, label="4×4")
    axs[0, 1].axvspan(9.5, 14.5, color=COLOR_5X5, alpha=0.08, label="5×5 (Bùng nổ)")
    axs[0, 1].legend(loc="upper left", frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=8.5)

    # Panel (C): Propagations vs Decisions Correlation
    scatter_colors = [COLOR_3X3 if s == 3 else COLOR_4X4 if s == 4 else COLOR_5X5 for s in sizes]
    axs[1, 0].scatter(decisions, propagations, c=scatter_colors, s=90, edgecolors="#1E293B", linewidths=0.8, alpha=0.9, zorder=3)
    axs[1, 0].set_xlabel("Số lần Phân nhánh (Decisions)", fontweight="bold", fontsize=10)
    axs[1, 0].set_ylabel("Số lần Lan truyền Đơn vị (Propagations)", fontweight="bold", fontsize=10)
    axs[1, 0].set_title("(C) Tương Quan Giữa Lan Truyền Đơn Vị Và Phân Nhánh", fontweight="bold", fontsize=11.5, pad=10, color=COLOR_SLATE_DARK)
    axs[1, 0].grid(True, linestyle="--", alpha=0.6, zorder=0)
    despine(axs[1, 0])
    for i, p in enumerate(puzzles):
        if sizes[i] == 5:
            axs[1, 0].annotate(p, (decisions[i], propagations[i]), xytext=(6, -2), textcoords="offset points", fontsize=8, color="#0F172A", fontweight="bold")

    # Panel (D): Variable and Clauses Growth
    x = np.arange(len(puzzles))
    axs[1, 1].plot(x, total_vars, marker="s", color=COLOR_3X3, linewidth=1.8, markersize=5, label="Tổng số Biến (Total Vars)", zorder=3)
    axs[1, 1].plot(x, aux_vars, marker="^", color=COLOR_4X4, linestyle="--", linewidth=1.8, markersize=5, label="Biến phụ (Aux Vars)", zorder=3)
    axs[1, 1].plot(x, [c / 3 for c in clauses], marker="d", color=COLOR_AMBER, linewidth=1.8, markersize=5, label="Số Mệnh đề / 3 (Scaled Clauses)", zorder=3)
    axs[1, 1].set_xticks(x)
    axs[1, 1].set_xticklabels(puzzles, rotation=40, fontsize=8.5)
    axs[1, 1].set_ylabel("Số lượng", fontweight="bold", fontsize=10)
    axs[1, 1].set_title("(D) Tăng Trưởng Biến Phụ Và Mệnh Đề CNF Qua 15 Maps", fontweight="bold", fontsize=11.5, pad=10, color=COLOR_SLATE_DARK)
    axs[1, 1].grid(True, linestyle="--", alpha=0.6, zorder=0)
    despine(axs[1, 1])
    axs[1, 1].legend(loc="upper left", frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0", fontsize=8.5)

    fig.suptitle("HỆ THỐNG ĐÁNH GIÁ THỰC NGHIỆM DPLL SAT SOLVER (GRIDUCTIVE SOLVER — TV4 HUY)", fontsize=13.5, fontweight="bold", color=COLOR_SLATE_DARK, y=0.992)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Modern Griductive Benchmark Visualizer")
    parser.add_argument(
        "--csv",
        type=str,
        default="benchmark_results.csv",
        help="Path to benchmark_results.csv (default: benchmark_results.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="docs/figures",
        help="Directory to save figures (default: docs/figures)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading benchmark data from: {csv_path.resolve()}")
    records = load_benchmark_data(csv_path)

    print(f"Rendering modern aesthetic figures to: {output_dir.resolve()} ...")
    plot_runtime(records, output_dir / "fig1_runtime_by_size.png")
    plot_dpll_metrics(records, output_dir / "fig2_dpll_metrics.png")
    plot_complexity_growth(records, output_dir / "fig3_complexity_growth.png")
    plot_summary_dashboard(records, output_dir / "fig4_summary_dashboard.png")

    print("All 4 modern aesthetic figures rendered successfully at 300 DPI!")


if __name__ == "__main__":
    main()
