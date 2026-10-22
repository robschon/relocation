"""Run the v2 pipeline for a location (or rescore across locations), recording a research run.

    run_location(location_id)                      # what's missing or stale; skips what's current
    run_location(location_id, force=True)          # redo every researched category + visa info
    run_location(location_id, category_keys=["tax"], skip_synthesis=True)
    run_rescore(category_keys=["visa", "tax"])     # re-score from stored evidence (no web search)
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import date, datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from relocation.config import PROJECT_ROOT
from relocation.database import SessionLocal
from relocation.models import Category, Location, ProCon, Research, ResearchRun
from relocation.pipeline.context import Profile, research_instructions
from relocation.pipeline.llm import LlmCallFailed, LlmClient
from relocation.pipeline.policy import profile_suggests_us_citizens, research_decision
from relocation.pipeline.steps import (
    RunContext,
    RunSummary,
    current_research,
    refresh_visa_info,
    rescore_from_evidence,
    research_and_score,
    synthesize,
)
from relocation.services.effective_scores import effective_scores
from relocation.services.errors import NotFound, ValidationFailed
from relocation.services.research_runs import create_run, finish_run, trim_log, update_run
from relocation.settings import get_settings


class RunLog:
    """Collects log lines; prints them and periodically saves step + log tail on the run row."""

    def __init__(self, run_id: int | None = None, session_factory=SessionLocal, echo: bool = True,
                 flush_seconds: float = 1.5):
        self.run_id = run_id
        self.session_factory = session_factory
        self.echo = echo
        self.flush_seconds = flush_seconds
        self.lines: list[str] = []
        self.step: str | None = None
        self._last_flush = 0.0

    def __call__(self, line: str) -> None:
        self.lines.append(line)
        if self.echo:
            print(line, flush=True)
        step_changed = line.startswith("[step]")
        if step_changed:
            self.step = line.removeprefix("[step]").strip()[:200]
        if self.run_id is not None and (step_changed or time.monotonic() - self._last_flush >= self.flush_seconds):
            self.flush()

    def flush(self) -> None:
        if self.run_id is None:
            return
        update_run(self.session_factory, self.run_id, step=self.step, log_tail=trim_log(self.lines))
        self._last_flush = time.monotonic()


def _tail(log) -> dict:
    """Final log tail for the run row, when the logger keeps lines (RunLog)."""
    return {"log_tail": trim_log(log.lines)} if isinstance(log, RunLog) else {}


def _categories(session: Session, category_keys: list[str] | None) -> list[Category]:
    categories = session.query(Category).order_by(Category.sort_order).all()
    if not category_keys:
        return categories
    wanted = [k.lower() for k in category_keys]
    return [c for c in categories if c.key in wanted or any(w in c.name.lower() for w in wanted)]


def _start(session: Session, *, run_id: int | None, kind: str, location: Location | None, provider: str,
           session_factory) -> int:
    settings = get_settings()
    if run_id is None:
        run = create_run(
            session, kind=kind, location_id=location.id if location else None,
            country_code=location.country_code if location else None, provider=provider,
            model=settings.research_model, prompt_version=settings.prompt_version, status="running",
        )
        return run.id
    update_run(session_factory, run_id, status="running", model=settings.research_model,
               prompt_version=settings.prompt_version)
    return run_id


def _context(session: Session, *, llm: LlmClient | None, run_id: int, provider: str, log) -> RunContext:
    settings = get_settings()
    profile = Profile.load(session)
    today = date.today()
    llm = llm or LlmClient(settings=settings, provider=provider, run_id=run_id)
    llm.run_id = run_id
    llm.provider = provider
    return RunContext(
        llm=llm,
        settings=settings,
        profile=profile,
        instructions=research_instructions(profile, summary_words=settings.summary_words, today=today),
        run_id=run_id,
        provider=provider,
        today=today,
        us_citizens=profile_suggests_us_citizens(profile.answers),
        log=log,
    )


def evidence_versions(session: Session, rows: list[Research]) -> dict[int, str | None]:
    """research.id -> prompt_version of the run that produced it ("legacy" for pre-run-tracking rows)."""
    run_ids = {r.run_id for r in rows if r.run_id is not None}
    versions = dict(session.query(ResearchRun.id, ResearchRun.prompt_version).filter(ResearchRun.id.in_(run_ids))) if run_ids else {}
    return {r.id: versions.get(r.run_id) for r in rows}


def needs_upgrade(session: Session, location: Location, provider: str = "openai") -> list[str]:
    """Researched categories whose current evidence is missing or from an older prompt version."""
    version = get_settings().prompt_version
    current = current_research(session, location, provider)
    versions = evidence_versions(session, list(current.values()))
    stale = []
    for category in session.query(Category).filter(Category.kind == "researched").order_by(Category.sort_order):
        row = current.get(category.id)
        if row is None or versions.get(row.id) != version:
            stale.append(category.name)
    return stale


def export_markdown(location_name: str) -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "export_research_markdown.py"), location_name],
        cwd=str(PROJECT_ROOT), check=False,
    )


def run_location(
    location_id: int,
    *,
    force: bool = False,
    category_keys: list[str] | None = None,
    skip_visa: bool = False,
    skip_synthesis: bool = False,
    force_description: bool = False,
    run_id: int | None = None,
    kind: str = "full",
    provider: str = "openai",
    session_factory=SessionLocal,
    llm: LlmClient | None = None,
    log: Callable[[str], None] | None = None,
    write_markdown: bool = True,
    upgrade_versions: bool = False,
) -> RunSummary:
    """Research what's missing or stale (or everything, with force).

    upgrade_versions: also redo evidence produced by an older prompt version (used by the backfill).
    """
    log = log or print
    summary = RunSummary()
    with session_factory() as session:
        location = session.get(Location, location_id)
        if location is None:
            raise NotFound(f"Location {location_id} not found")
        run_id = _start(session, run_id=run_id, kind=kind, location=location, provider=provider,
                        session_factory=session_factory)
        log(f"[start] {location.name} ({location.country}) run #{run_id}")
        try:
            ctx = _context(session, llm=llm, run_id=run_id, provider=provider, log=log)
            current = current_research(session, location, provider)
            versions = evidence_versions(session, list(current.values())) if upgrade_versions else {}
            scores = {s.category_id: s for s in effective_scores(session, provider=provider, location_id=location.id)}

            log("[step] Research and score categories")
            visa_researched = False  # the visa research call also saves the country's visa pathways
            for category in _categories(session, category_keys):
                if category.kind == "derived":
                    log(f"  [skip] {category.name} (computed from data)")
                    continue
                existing = current.get(category.id)
                refresh, reason = research_decision(category.refresh_after_days, existing, force)
                if not refresh and upgrade_versions and versions.get(existing.id) != ctx.settings.prompt_version:
                    refresh, reason = True, f"from prompt version {versions.get(existing.id) or 'unknown'}"
                try:
                    if refresh:
                        log(f"[step] Research: {category.name}" + (f" ({reason})" if existing else ""))
                        research_and_score(ctx, session, location, category)
                        summary.researched.append(category.name)
                        if category.key == "visa":
                            visa_researched = True
                    elif scores.get(category.id) is None or scores[category.id].research_id != existing.id:
                        log(f"[step] Rescore from stored evidence: {category.name}")
                        rescore_from_evidence(ctx, session, location, category, existing)
                        summary.rescored.append(category.name)
                    else:
                        log(f"  [skip] {category.name} (current)")
                        summary.skipped.append(category.name)
                except (LlmCallFailed, ValidationFailed) as exc:
                    session.rollback()
                    log(f"  [error] {category.name}: {exc}")
                    summary.failures.append(category.name)

            selected = _categories(session, category_keys)
            visa_selected = category_keys is None or any(c.key == "visa" for c in selected)
            if not skip_visa and visa_selected:
                log("[step] Visa info")
                try:
                    # Skip if the visa research call in this run already stored fresh pathways.
                    summary.visa_refreshed = visa_researched or refresh_visa_info(
                        ctx, session, location, force=force and not visa_researched
                    )
                except (LlmCallFailed, ValidationFailed) as exc:
                    session.rollback()
                    log(f"  [error] Visa info: {exc}")
                    summary.failures.append("visa info")

            if not skip_synthesis:
                has_pros = session.query(ProCon).filter_by(location_id=location.id, provider=provider).first() is not None
                needs = summary.scores_changed or not has_pros or force or force_description or not location.description
                if needs:
                    log("[step] Pros/cons and description")
                    try:
                        synthesize(ctx, session, location, force_description=force_description)
                        summary.synthesized = True
                    except (LlmCallFailed, ValidationFailed) as exc:
                        session.rollback()
                        log(f"  [error] Synthesis: {exc}")
                        summary.failures.append("synthesis")
                else:
                    log("  [skip] Pros/cons and description (no score changed)")

            if kind == "full":
                location.full_research_ran_at = datetime.now(timezone.utc)
                session.commit()
            if write_markdown and kind == "full":
                export_markdown(location.name)
            log(
                f"[done] researched={len(summary.researched)} rescored={len(summary.rescored)} "
                f"skipped={len(summary.skipped)} failed={len(summary.failures)}"
            )
            finish_run(
                session_factory, run_id, status="completed", step="completed",
                error=("Failed: " + ", ".join(summary.failures)) if summary.failures else None,
                **_tail(log),
            )
        except Exception as exc:
            session.rollback()
            log(f"[error] {type(exc).__name__}: {exc}")
            finish_run(session_factory, run_id, status="failed", step="failed",
                       error=f"{type(exc).__name__}: {exc}", **_tail(log))
            raise
    return summary


def run_rescore(
    *,
    category_keys: list[str],
    location_ids: list[int] | None = None,
    stale_only: bool = False,
    provider: str = "openai",
    session_factory=SessionLocal,
    llm: LlmClient | None = None,
    log: Callable[[str], None] | None = None,
) -> RunSummary:
    """Re-score categories from stored evidence. Country-scope categories are scored once per country."""
    log = log or print
    summary = RunSummary()
    with session_factory() as session:
        run_id = _start(session, run_id=None, kind="rescore", location=None, provider=provider,
                        session_factory=session_factory)
        ctx = _context(session, llm=llm, run_id=run_id, provider=provider, log=log)
        categories = _categories(session, category_keys)
        query = session.query(Location).order_by(Location.name)
        if location_ids:
            query = query.filter(Location.id.in_(location_ids))
        done_countries: set[tuple[str, int]] = set()
        for location in query.all():
            current = current_research(session, location, provider)
            scores = {s.category_id: s for s in effective_scores(session, provider=provider, location_id=location.id)}
            for category in categories:
                research = current.get(category.id)
                if category.kind == "derived" or research is None:
                    continue
                if category.scope == "country":
                    slot = (location.country_code, category.id)
                    if slot in done_countries:
                        continue
                    done_countries.add(slot)
                if stale_only and scores.get(category.id) and scores[category.id].research_id == research.id:
                    continue
                try:
                    rescore_from_evidence(ctx, session, location, category, research)
                    summary.rescored.append(f"{location.name}: {category.name}")
                    log(f"  [done] {location.name}: {category.name}")
                except (LlmCallFailed, ValidationFailed) as exc:
                    session.rollback()
                    summary.failures.append(f"{location.name}: {category.name}")
                    log(f"  [error] {location.name}: {category.name}: {exc}")
        finish_run(session_factory, run_id, status="completed",
                   error=("Failed: " + ", ".join(summary.failures))[:2000] if summary.failures else None)
    return summary
