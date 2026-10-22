"""Export location research from DB into markdown files in ./research."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "relocation.db"
OUT_DIR = PROJECT_ROOT / "research"


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _freshness_label(
    *,
    window_days: int | None,
    verification_status: str | None,
    source_checked_at: str | None,
    today: date,
) -> str:
    if verification_status == "stale":
        return "stale"

    if not source_checked_at:
        return "unverified"

    if not window_days:
        return verification_status or "needs_review"

    try:
        checked = date.fromisoformat(str(source_checked_at))
    except ValueError:
        return "unverified"

    age_days = (today - checked).days
    if age_days > window_days:
        return "stale"
    return "fresh"


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
            SELECT r.*
            FROM research r
            JOIN categories rc ON rc.id = r.category_id
            WHERE r.provider = 'openai' AND r.is_current = 1
              AND (
                (rc.scope = 'location' AND r.location_id = ?)
                OR (rc.scope = 'country' AND r.location_id IS NULL
                    AND r.country_code = (SELECT country_code FROM locations WHERE id = ?))
              )
        )
        SELECT
            c.sort_order,
            c.name AS category_name,
            CASE WHEN c.requires_citation = 1 THEN c.refresh_after_days END AS freshness_window_days,
            lr.content,
            lr.key_facts,
            lr.source,
            lr.source_checked_at,
            lr.verification_status,
            lr.confidence,
            s.score,
            s.notes AS score_notes
        FROM categories c
        LEFT JOIN latest_research lr
            ON lr.category_id = c.id
        LEFT JOIN effective_scores s
            ON s.category_id = c.id AND s.location_id = ? AND s.provider = 'openai'
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
        f"**Export date**: {now_label}",
        "**Data sources**: Database research entries and linked source notes",
        "",
        "---",
        "",
        "## Summary Scores",
        "",
        "| Category | Score | Verification | Key Factor |",
        "|---|---:|---|---|",
    ]

    today = date.today()
    for row in rows:
        content = (row["content"] or "No research content yet.").replace("\n", " ").strip()
        key = f"{content[:110]}..." if len(content) > 113 else content
        score = f"{row['score']}/10" if row["score"] is not None else "N/A"
        freshness = _freshness_label(
            window_days=row["freshness_window_days"],
            verification_status=row["verification_status"],
            source_checked_at=row["source_checked_at"],
            today=today,
        )
        checked = row["source_checked_at"] or "n/a"
        verification = f"{freshness} (checked {checked})"
        lines.append(f"| {row['category_name']} | {score} | {verification} | {key} |")

    lines.extend(["", "---", ""])

    for idx, row in enumerate(rows, start=1):
        lines.append(f"## {idx}. {row['category_name']}")
        lines.append("")
        lines.append(row["content"] or "No research content available.")
        facts = json.loads(row["key_facts"]) if row["key_facts"] else []
        if facts:
            lines.append("")
            lines.append("**Key facts:**")
            for fact in facts:
                value = f": {fact['value']}" if fact.get("value") else ""
                link = f" ([source]({fact['source_url']}))" if fact.get("source_url") else ""
                lines.append(f"- {fact.get('fact', '')}{value}{link}")
        lines.append("")
        score_line = f"**Score:** {row['score']}/10" if row["score"] is not None else "**Score:** N/A"
        lines.append(score_line)
        lines.append(f"**Score notes:** {(row['score_notes'] or 'No score notes available.').strip()}")
        lines.append(f"**Source:** {(row['source'] or 'No source noted.').strip()}")
        freshness = _freshness_label(
            window_days=row["freshness_window_days"],
            verification_status=row["verification_status"],
            source_checked_at=row["source_checked_at"],
            today=today,
        )
        lines.append(f"**Verification status:** {(row['verification_status'] or 'needs_review').strip()}")
        lines.append(f"**Freshness:** {freshness}")
        lines.append(f"**Source checked:** {(row['source_checked_at'] or 'Unknown').strip()}")
        confidence = row["confidence"]
        if confidence is not None:
            lines.append(f"**Confidence:** {confidence:.2f}")
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
