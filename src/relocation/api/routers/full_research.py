"""Full-research jobs: start the pipeline for a location and follow its progress.

Jobs are ``research_runs`` rows with kind="full", so they survive backend restarts
(a restart marks unfinished runs "interrupted"). The pipeline runs in a worker thread
in this process.
"""

from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from relocation.database import SessionLocal, get_db
from relocation.models import Location, ResearchRun
from relocation.pipeline.runner import RunLog, run_location
from relocation.services.research_runs import ACTIVE_STATUSES, create_run, finish_run

router = APIRouter(tags=["full_research"])


JobStatus = Literal["queued", "running", "completed", "failed", "interrupted"]


class FullResearchJobOut(BaseModel):
    id: str
    location_id: int | None
    location_name: str
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None = None
    step: str | None = None
    error: str | None = None
    output: list[str]
    provider: str
    model: str | None = None


def _job_out(run: ResearchRun) -> FullResearchJobOut:
    return FullResearchJobOut(
        id=str(run.id),
        location_id=run.location_id,
        location_name=run.location.name if run.location else "(deleted location)",
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        step=run.step,
        error=run.error,
        output=run.log_tail.splitlines() if run.log_tail else [],
        provider=run.provider,
        model=run.model,
    )


def _discover_env_var_from_zsh(var_name: str) -> str | None:
    """Best-effort lookup from ~/.zshrc for launchd contexts missing shell env."""
    try:
        result = subprocess.run(
            ["/bin/zsh", "-lc", f"source ~/.zshrc >/dev/null 2>&1; printenv {var_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None

    value = (result.stdout or "").strip()
    return value or None


def _ensure_openai_key() -> bool:
    from relocation.settings import get_settings

    if get_settings().openai_api_key:  # shell env or .env
        return True
    if not os.environ.get("OPENAI_API_KEY"):
        discovered = _discover_env_var_from_zsh("OPENAI_API_KEY")
        if discovered:
            os.environ["OPENAI_API_KEY"] = discovered
    return bool(os.environ.get("OPENAI_API_KEY"))


def _run_full_research_job(run_id: int, location_id: int, force_research: bool, force_country: bool = False) -> None:
    """Runs in a worker thread inside the backend process (no subprocess, no HTTP back to ourselves)."""
    if not _ensure_openai_key():
        finish_run(
            SessionLocal,
            run_id,
            status="failed",
            step="missing_openai_key",
            error="OPENAI_API_KEY is not set for backend jobs. Add it to .env or ~/.zshrc and restart the backend.",
        )
        return
    log = RunLog(run_id=run_id, session_factory=SessionLocal, echo=False)
    try:
        run_location(location_id, force=force_research, force_country=force_country, run_id=run_id, kind="full", log=log)
    except Exception:  # run_location already marked the run failed with the error
        pass


@router.post("/locations/{location_id}/full-research", response_model=FullResearchJobOut, status_code=202)
def start_full_research(
    location_id: int,
    force_research: bool = False,
    force_country: bool = False,
    db: Session = Depends(get_db),
):
    """force_research redoes this location's research; country visa work is reused while current
    unless force_country is set too."""
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    active = (
        db.query(ResearchRun)
        .filter(
            ResearchRun.kind == "full",
            ResearchRun.location_id == location_id,
            ResearchRun.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"A full-research job is already running for {location.name}",
        )

    run = create_run(
        db,
        kind="full",
        location_id=location.id,
        country_code=location.country_code,
        status="queued",
    )

    thread = threading.Thread(
        target=_run_full_research_job,
        args=(run.id, location.id, force_research, force_country),
        daemon=True,
    )
    thread.start()
    return _job_out(run)


def _job_query(db: Session):
    # Legacy runs reconstructed by the Phase 1 migration have no output to show.
    return db.query(ResearchRun).filter(
        ResearchRun.kind == "full",
        (ResearchRun.prompt_version.is_(None)) | (ResearchRun.prompt_version != "legacy"),
    )


@router.get("/full-research-jobs", response_model=list[FullResearchJobOut])
def list_full_research_jobs(limit: int = 200, db: Session = Depends(get_db)):
    runs = _job_query(db).order_by(ResearchRun.started_at.desc()).limit(limit).all()
    return [_job_out(run) for run in runs]


@router.get("/full-research-jobs/{job_id}", response_model=FullResearchJobOut)
def get_full_research_job(job_id: str, db: Session = Depends(get_db)):
    run = db.get(ResearchRun, int(job_id)) if job_id.isdigit() else None
    if not run or run.kind != "full":
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(run)
