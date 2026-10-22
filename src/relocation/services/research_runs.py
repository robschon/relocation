"""Create and update ``research_runs`` rows (pipeline provenance + job status)."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from relocation.models import DEFAULT_PROVIDER, ResearchRun

ACTIVE_STATUSES = ("queued", "running")
LOG_TAIL_LINES = 400
# Bumped when the research prompts change materially (Phase 4 introduces v2).
PROMPT_VERSION = "v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def default_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.4")


def create_run(
    session: Session,
    *,
    kind: str,
    location_id: int | None = None,
    country_code: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    model: str | None = None,
    prompt_version: str | None = PROMPT_VERSION,
    status: str = "running",
) -> ResearchRun:
    run = ResearchRun(
        kind=kind,
        location_id=location_id,
        country_code=country_code,
        provider=provider,
        # Computed (enrichment) runs make no LLM calls, so they have no model.
        model=model if model is not None or kind == "enrichment" else default_model(),
        prompt_version=prompt_version,
        status=status,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def update_run(session_factory: Callable[[], Session], run_id: int, **changes) -> None:
    with session_factory() as session:
        run = session.get(ResearchRun, run_id)
        if run is None:
            return
        for key, value in changes.items():
            setattr(run, key, value)
        session.commit()


def finish_run(
    session_factory: Callable[[], Session],
    run_id: int,
    *,
    status: str,
    error: str | None = None,
    **changes,
) -> None:
    update_run(session_factory, run_id, status=status, error=error, finished_at=_utcnow(), **changes)


def trim_log(lines: list[str]) -> str:
    return "\n".join(lines[-LOG_TAIL_LINES:])


def mark_interrupted_runs(session: Session) -> int:
    """Runs left queued/running by a previous backend process can't still be going."""
    count = (
        session.query(ResearchRun)
        .filter(ResearchRun.status.in_(ACTIVE_STATUSES))
        .update(
            {
                ResearchRun.status: "interrupted",
                ResearchRun.finished_at: _utcnow(),
                ResearchRun.error: "Backend restarted while this run was in progress.",
            },
            synchronize_session=False,
        )
    )
    session.commit()
    return count
