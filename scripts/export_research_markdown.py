"""Export location research from DB into markdown files in ./research."""

from __future__ import annotations

import argparse
import re
import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "relocation.db"
OUT_DIR = PROJECT_ROOT / "research"


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def build_markdown(conn: sqlite3.Connection, location_name: str) -> tuple[Path, str]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    location = cur.execute(
        "SELECT id, name, country, region FROM locations WHERE name = ?",
        (location_name,),
    ).fetchone()
    if location is None:
        raise ValueError(f"Location not found: {location_name}")

    rows = cur.execute(
        """
        WITH latest_research AS (
            SELECT r1.*
            FROM research r1
            JOIN (
                SELECT category_id, MAX(id) AS max_id
                FROM research
                WHERE location_id = ?
                GROUP BY category_id
            ) x ON x.max_id = r1.id
        )
        SELECT
            c.sort_order,
            c.name AS category_name,
            lr.content,
            lr.source,
            s.score,
            s.notes AS score_notes
        FROM categories c
        LEFT JOIN latest_research lr
            ON lr.category_id = c.id AND lr.location_id = ?
        LEFT JOIN scores s
            ON s.category_id = c.id AND s.location_id = ?
        ORDER BY c.sort_order ASC
        """,
        (location["id"], location["id"], location["id"]),
    ).fetchall()

    region = (location["region"] or "").strip()
    locale = f"{location['name']}, {region}" if region else location["name"]
    title = f"# {locale} ({location['country']}) - Relocation Research"

    now_label = datetime.now().strftime("%B %Y")
    lines: list[str] = [
        title,
        "",
        f"**Research date**: {now_label}",
        "**Data sources**: Database research entries and linked source notes",
        "",
        "---",
        "",
        "## Summary Scores",
        "",
        "| Category | Score | Key Factor |",
        "|---|---:|---|",
    ]

    for row in rows:
        content = (row["content"] or "No research content yet.").replace("\n", " ").strip()
        key = f"{content[:110]}..." if len(content) > 113 else content
        score = f"{row['score']}/10" if row["score"] is not None else "N/A"
        lines.append(f"| {row['category_name']} | {score} | {key} |")

    lines.extend(["", "---", ""])

    for idx, row in enumerate(rows, start=1):
        lines.append(f"## {idx}. {row['category_name']}")
        lines.append("")
        lines.append(row["content"] or "No research content available.")
        lines.append("")
        score_line = f"**Score:** {row['score']}/10" if row["score"] is not None else "**Score:** N/A"
        lines.append(score_line)
        lines.append(f"**Score notes:** {(row['score_notes'] or 'No score notes available.').strip()}")
        lines.append(f"**Source:** {(row['source'] or 'No source noted.').strip()}")
        lines.append("")

    filename = f"{slugify(location['name'])}-{slugify(location['country'])}.md"
    path = OUT_DIR / filename
    return path, "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export markdown research docs for locations.")
    parser.add_argument("locations", nargs="+", help='Exact location name(s), e.g. "Valletta / Sliema"')
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        for name in args.locations:
            output_path, content = build_markdown(conn, name)
            output_path.write_text(content, encoding="utf-8")
            print(f"[ok] wrote {output_path}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
