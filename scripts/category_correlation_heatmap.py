#!/usr/bin/env python3
"""Generate category-correlation reports from the relocation score matrix."""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from xml.sax.saxutils import escape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "relocation.db"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "reports"


@dataclass(frozen=True)
class Category:
    id: int
    name: str


@dataclass(frozen=True)
class PairSummary:
    category_a: str
    category_b: str
    pearson_r: float
    mean_abs_diff: float
    median_abs_diff: float
    exact_match_count: int
    within_one_count: int
    location_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an SVG heatmap and CSV summary for category correlations."
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_REPORT_DIR),
        help=f"Directory for generated reports (default: {DEFAULT_REPORT_DIR})",
    )
    parser.add_argument(
        "--basename",
        default="category_correlation",
        help="Base filename for report outputs (default: category_correlation)",
    )
    return parser.parse_args()


def fetch_matrix(db_path: Path) -> tuple[list[Category], list[int], dict[tuple[int, int], int]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    categories = [
        Category(id=int(row["id"]), name=str(row["name"]))
        for row in conn.execute("SELECT id, name FROM categories ORDER BY id")
    ]
    location_ids = [int(row["id"]) for row in conn.execute("SELECT id FROM locations ORDER BY id")]
    score_map = {
        (int(row["location_id"]), int(row["category_id"])): int(row["score"])
        for row in conn.execute("SELECT location_id, category_id, score FROM scores")
    }
    conn.close()
    return categories, location_ids, score_map


def series_by_category(
    categories: list[Category],
    location_ids: list[int],
    score_map: dict[tuple[int, int], int],
) -> dict[int, list[int]]:
    return {
        category.id: [score_map[(location_id, category.id)] for location_id in location_ids]
        for category in categories
    }


def pearson(xs: list[int], ys: list[int]) -> float:
    mean_x = mean(xs)
    mean_y = mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denominator_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if not denominator_x or not denominator_y:
        return 0.0
    return numerator / (denominator_x * denominator_y)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def summarize_pairs(categories: list[Category], series: dict[int, list[int]]) -> list[PairSummary]:
    pairs: list[PairSummary] = []
    for index, category_a in enumerate(categories):
        for category_b in categories[index + 1 :]:
            xs = series[category_a.id]
            ys = series[category_b.id]
            diffs = [abs(x - y) for x, y in zip(xs, ys)]
            pairs.append(
                PairSummary(
                    category_a=category_a.name,
                    category_b=category_b.name,
                    pearson_r=pearson(xs, ys),
                    mean_abs_diff=mean(diffs),
                    median_abs_diff=median(diffs),
                    exact_match_count=sum(diff == 0 for diff in diffs),
                    within_one_count=sum(diff <= 1 for diff in diffs),
                    location_count=len(diffs),
                )
            )
    return pairs


def build_correlation_matrix(
    categories: list[Category],
    series: dict[int, list[int]],
) -> list[list[float]]:
    matrix: list[list[float]] = []
    for category_a in categories:
        row: list[float] = []
        for category_b in categories:
            row.append(pearson(series[category_a.id], series[category_b.id]))
        matrix.append(row)
    return matrix


def interpolate_color(value: float) -> str:
    clamped = max(-1.0, min(1.0, value))
    if clamped < 0:
        start = (186, 26, 26)
        end = (250, 245, 240)
        ratio = clamped + 1.0
    else:
        start = (250, 245, 240)
        end = (17, 94, 89)
        ratio = clamped

    rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))
    return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"


def text_color(value: float) -> str:
    return "#f8fafc" if abs(value) >= 0.55 else "#111827"


def render_svg(
    categories: list[Category],
    matrix: list[list[float]],
    location_count: int,
    output_path: Path,
) -> None:
    cell_size = 44
    left_margin = 300
    top_margin = 210
    right_margin = 80
    bottom_margin = 80
    legend_height = 18
    width = left_margin + len(categories) * cell_size + right_margin
    height = top_margin + len(categories) * cell_size + bottom_margin + 90

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<defs>',
        '  <linearGradient id="legend-gradient" x1="0%" y1="0%" x2="100%" y2="0%">',
        '    <stop offset="0%" stop-color="rgb(186,26,26)" />',
        '    <stop offset="50%" stop-color="rgb(250,245,240)" />',
        '    <stop offset="100%" stop-color="rgb(17,94,89)" />',
        "  </linearGradient>",
        "</defs>",
        '  <title id="title">Category Correlation Heatmap</title>',
        '  <desc id="desc">Pearson correlation between each pair of scoring categories across all locations.</desc>',
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#fffdf8" />',
        '  <text x="36" y="48" font-size="28" font-family="Helvetica, Arial, sans-serif" font-weight="700" fill="#111827">Category Correlation Heatmap</text>',
        f'  <text x="36" y="76" font-size="15" font-family="Helvetica, Arial, sans-serif" fill="#4b5563">Pearson r across {location_count} fully scored locations and {len(categories)} categories</text>',
    ]

    for index, category in enumerate(categories):
        x = left_margin + index * cell_size + cell_size / 2
        label = escape(category.name)
        lines.append(
            f'  <text x="{x:.1f}" y="{top_margin - 12}" transform="rotate(-45 {x:.1f},{top_margin - 12})" '
            'font-size="11" font-family="Helvetica, Arial, sans-serif" text-anchor="start" fill="#374151">'
            f"{label}</text>"
        )
        y = top_margin + index * cell_size + cell_size / 2 + 4
        lines.append(
            f'  <text x="{left_margin - 12}" y="{y:.1f}" font-size="12" font-family="Helvetica, Arial, sans-serif" '
            f'text-anchor="end" fill="#374151">{label}</text>'
        )

    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            x = left_margin + column_index * cell_size
            y = top_margin + row_index * cell_size
            lines.append(
                f'  <rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{interpolate_color(value)}" stroke="#fffdf8" stroke-width="1.5" rx="4" />'
            )
            lines.append(
                f'  <text x="{x + cell_size / 2:.1f}" y="{y + cell_size / 2 + 4:.1f}" '
                f'font-size="11" font-family="Menlo, Consolas, monospace" text-anchor="middle" fill="{text_color(value)}">{value:.2f}</text>'
            )

    legend_x = 36
    legend_y = top_margin + len(categories) * cell_size + 36
    legend_width = 260
    lines.extend(
        [
            f'  <text x="{legend_x}" y="{legend_y - 12}" font-size="13" font-family="Helvetica, Arial, sans-serif" fill="#374151">Correlation scale</text>',
            f'  <rect x="{legend_x}" y="{legend_y}" width="{legend_width}" height="{legend_height}" fill="url(#legend-gradient)" rx="9" />',
            f'  <text x="{legend_x}" y="{legend_y + legend_height + 18}" font-size="11" font-family="Helvetica, Arial, sans-serif" fill="#6b7280">-1.0</text>',
            f'  <text x="{legend_x + legend_width / 2:.1f}" y="{legend_y + legend_height + 18}" font-size="11" font-family="Helvetica, Arial, sans-serif" text-anchor="middle" fill="#6b7280">0.0</text>',
            f'  <text x="{legend_x + legend_width}" y="{legend_y + legend_height + 18}" font-size="11" font-family="Helvetica, Arial, sans-serif" text-anchor="end" fill="#6b7280">1.0</text>',
        ]
    )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(pair_summaries: list[PairSummary], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "category_a",
                "category_b",
                "pearson_r",
                "mean_abs_diff",
                "median_abs_diff",
                "exact_match_count",
                "within_one_count",
                "location_count",
            ]
        )
        for pair in sorted(pair_summaries, key=lambda item: item.pearson_r, reverse=True):
            writer.writerow(
                [
                    pair.category_a,
                    pair.category_b,
                    f"{pair.pearson_r:.6f}",
                    f"{pair.mean_abs_diff:.6f}",
                    f"{pair.median_abs_diff:.6f}",
                    pair.exact_match_count,
                    pair.within_one_count,
                    pair.location_count,
                ]
            )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    categories, location_ids, score_map = fetch_matrix(db_path)
    series = series_by_category(categories, location_ids, score_map)
    pair_summaries = summarize_pairs(categories, series)
    correlation_matrix = build_correlation_matrix(categories, series)

    svg_path = output_dir / f"{args.basename}_heatmap.svg"
    csv_path = output_dir / f"{args.basename}_pairs.csv"
    render_svg(categories, correlation_matrix, len(location_ids), svg_path)
    write_csv(pair_summaries, csv_path)

    strongest_pair = max(pair_summaries, key=lambda item: item.pearson_r)
    closest_pair = min(pair_summaries, key=lambda item: (item.mean_abs_diff, -item.pearson_r))

    print(f"Wrote heatmap: {svg_path}")
    print(f"Wrote pair summary: {csv_path}")
    print(
        "Top correlated pair: "
        f"{strongest_pair.category_a} <> {strongest_pair.category_b} "
        f"(r={strongest_pair.pearson_r:.3f})"
    )
    print(
        "Closest raw-score pair: "
        f"{closest_pair.category_a} <> {closest_pair.category_b} "
        f"(mean_abs_diff={closest_pair.mean_abs_diff:.3f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
