"""Export a location's current research and scores to ``research/<slug>.md``.

The markdown files are generated output: the database is the source of truth.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from relocation.config import PROJECT_ROOT
from relocation.models import Location
from relocation.services.effective_scores import effective_scores
from relocation.slugs import location_slug

OUT_DIR = PROJECT_ROOT / "research"


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


def build_markdown(session: Session, location: Location, out_dir: Path = OUT_DIR) -> tuple[Path, str]:
    rows = session.execute(
        text(
            """
        WITH latest_research AS (
            SELECT r.*
            FROM research r
            JOIN categories rc ON rc.id = r.category_id
            WHERE r.provider = 'openai' AND r.is_current = 1
              AND (
                (rc.scope = 'location' AND r.location_id = :location_id)
                OR (rc.scope = 'country' AND r.location_id IS NULL AND r.country_code = :country_code)
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
            c.id AS category_id
        FROM categories c
        LEFT JOIN latest_research lr
            ON lr.category_id = c.id
        ORDER BY c.sort_order ASC
        """
        ),
        {"location_id": location.id, "country_code": location.country_code},
    ).mappings().all()
    scores = {s.category_id: s for s in effective_scores(session, provider="openai", location_id=location.id)}
    rows = [
        {
            **row,
            "score": scores[row["category_id"]].score if row["category_id"] in scores else None,
            "score_notes": scores[row["category_id"]].notes if row["category_id"] in scores else None,
        }
        for row in rows
    ]

    region = (location.region or "").strip()
    locale = f"{location.name}, {region}" if region else location.name
    title = f"# {locale} ({location.country}) - Relocation Research"

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
        facts = row["key_facts"] or []
        if isinstance(facts, str):
            facts = json.loads(facts)
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

    path = out_dir / f"{location.slug or location_slug(location.name, location.country)}.md"
    return path, "\n".join(lines).rstrip() + "\n"



def export_locations(session: Session, locations: list[Location], out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for location in locations:
        path, content = build_markdown(session, location, out_dir)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def stale_files(session: Session, out_dir: Path = OUT_DIR) -> list[Path]:
    """Markdown files in ``out_dir`` that do not belong to any location's current slug."""
    expected = {f"{slug}.md" for (slug,) in session.query(Location.slug)}
    return sorted(path for path in out_dir.glob("*.md") if path.name not in expected)


def export_location_by_id(location_id: int) -> Path | None:
    """Best-effort export used after pipeline runs; never raises."""
    from relocation.database import SessionLocal

    try:
        with SessionLocal() as session:
            location = session.get(Location, location_id)
            if location is None:
                return None
            return export_locations(session, [location])[0]
    except Exception as exc:  # noqa: BLE001 - export must not fail a research run
        print(f"[warn] markdown export failed for location {location_id}: {exc}")
        return None
