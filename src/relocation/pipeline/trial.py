"""Run pipeline v2 on a copy of the database and compare it with the live (v1) data.

The live database is never written: the trial copy gets the new research, scores,
pros/cons and llm_calls rows. v1 token figures come from the live llm_calls rows for
the same locations (most recent day with research calls).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from relocation.config import DATA_DIR, DATABASE_URL
from relocation.database import enable_sqlite_foreign_keys
from relocation.migrate import upgrade_database
from relocation.models import Category, Location, LlmCall, Research, ResearchRun
from relocation.pipeline.llm import LlmClient
from relocation.pipeline.runner import RunLog, run_location
from relocation.services.effective_scores import effective_scores
from relocation.services.llm_usage import record_llm_call

TRIALS_DIR = DATA_DIR / "trials"
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "web_search_calls")


def _live_path() -> Path:
    if not DATABASE_URL.startswith("sqlite:///"):
        raise RuntimeError("Trials only support SQLite databases.")
    return Path(DATABASE_URL.removeprefix("sqlite:///"))


def make_trial_copy() -> Path:
    TRIALS_DIR.mkdir(parents=True, exist_ok=True)
    target = TRIALS_DIR / f"v2-trial-{datetime.now():%Y%m%d-%H%M%S}.db"
    src = sqlite3.connect(f"file:{_live_path()}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    src.backup(dst)
    src.close()
    dst.close()
    return target


def _session_factory(path: Path):
    engine = enable_sqlite_foreign_keys(create_engine(f"sqlite:///{path}", connect_args={"timeout": 15}))
    upgrade_database(engine)
    return sessionmaker(bind=engine)


def run_trial(location_ids: list[int], *, force: bool = True, trial_path: Path | None = None,
              category_keys: list[str] | None = None) -> Path:
    path = trial_path or make_trial_copy()
    TrialSession = _session_factory(path)

    def recorder(**kwargs):
        record_llm_call(**kwargs, session_factory=TrialSession)

    for location_id in location_ids:
        llm = LlmClient(recorder=recorder)
        log = RunLog(session_factory=TrialSession)
        run_location(location_id, force=force, category_keys=category_keys,
                     kind="category" if category_keys else "full", session_factory=TrialSession, llm=llm, log=log,
                     write_markdown=False)
    return path


@dataclass
class LocationComparison:
    name: str
    v1: dict
    v2: dict
    score_changes: list[tuple[str, int, int]]
    v2_cited_categories: int
    v2_categories: int
    extra: dict | None = None


def _sum_calls(rows) -> dict:
    totals = {"calls": len(rows), **{f: 0 for f in TOKEN_FIELDS}}
    for row in rows:
        for f in TOKEN_FIELDS:
            totals[f] += getattr(row, f) or 0
    return totals


def _v1_calls(session: Session, location_id: int) -> list[LlmCall]:
    v2_runs = [rid for (rid,) in session.query(ResearchRun.id).filter(ResearchRun.prompt_version == "v2")]
    query = session.query(LlmCall).filter(LlmCall.location_id == location_id)
    if v2_runs:
        query = query.filter((LlmCall.run_id.is_(None)) | (LlmCall.run_id.notin_(v2_runs)))
    groups = defaultdict(list)  # a run, or (before run tracking) a day
    for call in query.all():
        groups[("run", call.run_id) if call.run_id else ("day", call.created_at.date())].append(call)
    if not groups:
        return []
    # The baseline is the most complete v1 pass: most research calls, then the latest.
    best = max(groups.values(), key=lambda rows: (sum(r.route == "research" for r in rows), max(r.created_at for r in rows)))
    return best if any(r.route == "research" for r in best) else []


def compare(trial_path: Path, location_ids: list[int]) -> list[LocationComparison]:
    live = sessionmaker(bind=create_engine(f"sqlite:///{_live_path()}"))()
    trial = sessionmaker(bind=create_engine(f"sqlite:///{trial_path}"))()
    categories = {c.id: c for c in trial.query(Category)}
    out = []
    for location_id in location_ids:
        location = trial.get(Location, location_id)
        v2_runs = trial.query(ResearchRun).filter(
            ResearchRun.location_id == location_id, ResearchRun.prompt_version == "v2").order_by(ResearchRun.id).all()
        v2_run_ids = [r.id for r in v2_runs]
        # Like-for-like with v1: the first full v2 run (retries inside it included); later --reuse runs are extra.
        first_full = next((r.id for r in v2_runs if r.kind == "full"), None)
        v2_calls = trial.query(LlmCall).filter(LlmCall.run_id == first_full).all() if first_full else []
        extra_calls = trial.query(LlmCall).filter(
            LlmCall.run_id.in_([rid for rid in v2_run_ids if rid != first_full])).all()
        before = {s.category_id: s.score for s in effective_scores(live, provider="openai", location_id=location_id)}
        after = {s.category_id: s.score for s in effective_scores(trial, provider="openai", location_id=location_id)}
        changes = [(categories[cid].name, before[cid], after[cid]) for cid in after
                   if cid in before and before[cid] != after[cid]]
        v2_research = trial.query(Research).filter(Research.run_id == first_full).all() if first_full else []
        out.append(LocationComparison(
            name=location.name,
            v1=_sum_calls(_v1_calls(live, location_id)),
            v2=_sum_calls(v2_calls),
            score_changes=sorted(changes, key=lambda c: -abs(c[2] - c[1])),
            v2_cited_categories=sum(
                1 for r in v2_research
                if r.source_urls and (r.source or "").lower().startswith("web search")
            ),
            extra=_sum_calls(extra_calls),
            v2_categories=len(v2_research),
        ))
    live.close()
    trial.close()
    return out


def format_report(rows: list[LocationComparison]) -> str:
    lines = ["First full run per location (v2 retries included; later --reuse runs listed separately)",
             "Location                     |  v1 calls  in/out tokens      |  v2 calls  in (cached)/out tokens  searches"]
    for r in rows:
        lines.append(
            f"{r.name[:28]:<28} | {r.v1['calls']:>5}  {r.v1['input_tokens']:>7,}/{r.v1['output_tokens']:<7,}     | "
            f"{r.v2['calls']:>5}  {r.v2['input_tokens']:>7,} ({r.v2['cached_input_tokens']:,})/{r.v2['output_tokens']:<7,} "
            f"{r.v2['web_search_calls']:>5}"
        )
    with_v1 = [r for r in rows if r.v1["output_tokens"]]
    if with_v1:
        def change(field: str) -> str:
            v1 = sum(r.v1[field] for r in with_v1)
            v2 = sum(r.v2[field] for r in with_v1)
            if not v1:
                return "n/a"
            ratio = v2 / v1 - 1
            return f"{abs(ratio):.0%} {'less' if ratio < 0 else 'more'} than v1"

        lines.append(f"\nOutput tokens: {change('output_tokens')}. Input tokens: {change('input_tokens')}. "
                     "Web-search tool fees are charged per search on top of tokens.")
    for r in rows:
        moved = [abs(new - old) for _, old, new in r.score_changes]
        lines.append(f"\n{r.name}: {len(r.score_changes)} score change(s)"
                     + (f", mean move {mean(moved):.1f}" if moved else "")
                     + f"; {r.v2_cited_categories}/{r.v2_categories} research rows from web search")
        if r.extra and r.extra["calls"]:
            lines.append(f"    later re-runs: {r.extra['calls']} calls, {r.extra['input_tokens']:,} in / "
                         f"{r.extra['output_tokens']:,} out, {r.extra['web_search_calls']} searches")
        for name, old, new in r.score_changes[:6]:
            lines.append(f"    {name}: {old} -> {new}")
    return "\n".join(lines)


def latest_trial() -> Path | None:
    trials = sorted(TRIALS_DIR.glob("v2-trial-*.db")) if TRIALS_DIR.exists() else []
    return trials[-1] if trials else None

