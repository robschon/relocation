"""Preview what recomputing the derived scores (swimming, beach access) does to rankings.

Works on a temporary copy of the database; the real database is not changed.

    uv run python scripts/preview_derived_scores.py
    uv run python scripts/preview_derived_scores.py --skip-beach     # no network for Overpass
    uv run python scripts/preview_derived_scores.py --top 25

Writes data/reports/derived_scores_preview_<date>.csv with every location's before/after.
To apply for real afterwards:

    uv run python scripts/update_swimming_scores.py
    uv run python scripts/update_beach_accessibility_scores.py
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from relocation.config import DATABASE_URL
from relocation.database import enable_sqlite_foreign_keys
from relocation.migrate import upgrade_database
from relocation.models import Category
from relocation.services.effective_scores import effective_scores
from relocation.services.ranking import compute_rankings, resolve_users

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"


def snapshot(session) -> dict:
    users = resolve_users(session)
    derived = {c.id: c.key for c in session.query(Category).filter(Category.kind == "derived")}
    derived_scores = {
        (s.location_id, derived[s.category_id]): s.score
        for s in effective_scores(session)
        if s.category_id in derived
    }
    views = {"combined": compute_rankings(session)}
    for user in users:
        views[user.display_name or user.name] = compute_rankings(session, user=user.id)
    out = {}
    for view, rankings in views.items():
        for rank, r in enumerate(rankings, 1):
            row = out.setdefault(r.location_id, {"name": r.location_name, "country": r.country})
            row[f"{view}_rank"] = rank
            row[f"{view}_score"] = round(r.overall_score, 2)
    for loc_id, row in out.items():
        for key in derived.values():
            row[key] = derived_scores.get((loc_id, key))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-beach", action="store_true", help="Only recompute swimming (no Overpass calls)")
    parser.add_argument("--top", type=int, default=15, help="Rows to print in the summary")
    parser.add_argument("--overpass-url", help="Overpass mirror to use for the beach step")
    args = parser.parse_args()

    if not DATABASE_URL.startswith("sqlite:///"):
        print("This preview only supports SQLite databases.")
        return 1
    source = DATABASE_URL.removeprefix("sqlite:///")

    with tempfile.TemporaryDirectory(prefix="derived-preview-") as tmp:
        copy_path = Path(tmp) / "preview.db"
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        dst = sqlite3.connect(copy_path)
        src.backup(dst)
        src.close()
        dst.close()

        print(f"[copy] {source} -> temporary copy", flush=True)
        url = f"sqlite:///{copy_path}"
        engine = enable_sqlite_foreign_keys(create_engine(url))
        upgrade_database(engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            before = snapshot(session)

        env = {**os.environ, "RELOCATION_DATABASE_URL": url, "RELOCATION_LLM_USAGE_LOG": "0"}
        steps = [PROJECT_ROOT / "scripts" / "update_swimming_scores.py"]
        if not args.skip_beach:
            steps.append(PROJECT_ROOT / "scripts" / "update_beach_accessibility_scores.py")
        if args.overpass_url:
            env["RELOCATION_OVERPASS_URL"] = args.overpass_url
        for step in steps:
            print(f"[run] {step.name} (on a temporary copy)", flush=True)
            # Stream the step's output so long Overpass runs show progress.
            process = subprocess.Popen(
                [sys.executable, "-u", str(step)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(f"      {line.rstrip()}", flush=True)
            if process.wait() not in (0, 2):
                print(f"[error] {step.name} failed (exit {process.returncode}); no preview produced.")
                return 1

        with Session() as session:
            after = snapshot(session)
        engine.dispose()

    views = [k.removesuffix("_rank") for k in next(iter(before.values())) if k.endswith("_rank")]
    derived_keys = ["swimming", "beach_access"]
    rows = []
    for loc_id, b in before.items():
        a = after.get(loc_id, {})
        row = {"location": b["name"], "country": b["country"]}
        for key in derived_keys:
            row[f"{key}_before"], row[f"{key}_after"] = b.get(key), a.get(key)
        for view in views:
            row[f"{view}_rank_before"], row[f"{view}_rank_after"] = b[f"{view}_rank"], a.get(f"{view}_rank")
            row[f"{view}_score_before"], row[f"{view}_score_after"] = b[f"{view}_score"], a.get(f"{view}_score")
        rows.append(row)
    rows.sort(key=lambda r: r["combined_rank_after"] or 9999)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORTS_DIR / f"derived_scores_preview_{date.today():%Y-%m-%d}.csv"
    with report.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    changed = sum(1 for r in rows if r["swimming_before"] != r["swimming_after"] or r["beach_access_before"] != r["beach_access_after"])
    print(f"\nDerived scores changed for {changed} of {len(rows)} locations.\n")
    print(f"Combined top {args.top} after recompute (rank before -> after, swim/beach before -> after):")
    for r in rows[: args.top]:
        move = r["combined_rank_before"] - r["combined_rank_after"]
        arrow = f"+{move}" if move > 0 else (str(move) if move < 0 else "=")
        print(
            f"  {r['combined_rank_after']:>3}. {r['location']:<32} {r['combined_rank_before']:>3} -> {r['combined_rank_after']:<3} ({arrow:>4})"
            f"  swim {r['swimming_before']}->{r['swimming_after']}  beach {r['beach_access_before']}->{r['beach_access_after']}"
        )
    movers = sorted(rows, key=lambda r: abs(r["combined_rank_before"] - r["combined_rank_after"]), reverse=True)[:10]
    print("\nBiggest combined-rank moves:")
    for r in movers:
        print(
            f"  {r['location']:<32} {r['combined_rank_before']:>3} -> {r['combined_rank_after']:<3}"
            f"  swim {r['swimming_before']}->{r['swimming_after']}  beach {r['beach_access_before']}->{r['beach_access_after']}"
        )
    print(f"\nFull table: {report.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
