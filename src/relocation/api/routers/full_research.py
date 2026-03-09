from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Location

router = APIRouter(tags=["full_research"])

PROJECT_ROOT = Path(__file__).resolve().parents[4]
FULL_RESEARCH_SCRIPT = PROJECT_ROOT / "scripts" / "full_research_location_openai.py"

JobStatus = Literal["queued", "running", "completed", "failed"]


class FullResearchJobOut(BaseModel):
    id: str
    location_id: int
    location_name: str
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None = None
    step: str | None = None
    error: str | None = None
    output: list[str]


_jobs_lock = threading.Lock()
_jobs: dict[str, FullResearchJobOut] = {}


def _update_job(job_id: str, **changes) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        data = job.model_dump()
        data.update(changes)
        _jobs[job_id] = FullResearchJobOut(**data)


def _append_output(job_id: str, line: str) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        output = list(job.output)
        output.append(line)
        # Keep the last 400 lines for UI display.
        if len(output) > 400:
            output = output[-400:]
        _jobs[job_id] = FullResearchJobOut(**{**job.model_dump(), "output": output})


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


def _run_full_research_job(job_id: str, location_name: str) -> None:
    _update_job(job_id, status="running", step="starting")

    cmd = [sys.executable, str(FULL_RESEARCH_SCRIPT), location_name]
    env = os.environ.copy()
    if not env.get("OPENAI_API_KEY"):
        discovered = _discover_env_var_from_zsh("OPENAI_API_KEY")
        if discovered:
            env["OPENAI_API_KEY"] = discovered

    if not env.get("OPENAI_API_KEY"):
        _update_job(
            job_id,
            status="failed",
            error="OPENAI_API_KEY is not set for backend jobs. Add it to ~/.zshrc and restart backend.",
            finished_at=datetime.now(timezone.utc),
            step="missing_openai_key",
        )
        return

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            error=f"Failed to start job: {exc}",
            finished_at=datetime.now(timezone.utc),
            step="start_failed",
        )
        return

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        _append_output(job_id, line)
        if line.startswith("[step]"):
            _update_job(job_id, step=line.replace("[step]", "", 1).strip())

    return_code = process.wait()
    if return_code == 0:
        _update_job(
            job_id,
            status="completed",
            finished_at=datetime.now(timezone.utc),
            step="completed",
        )
    else:
        _update_job(
            job_id,
            status="failed",
            error=f"Pipeline exited with code {return_code}",
            finished_at=datetime.now(timezone.utc),
            step="failed",
        )


@router.post("/locations/{location_id}/full-research", response_model=FullResearchJobOut, status_code=202)
def start_full_research(location_id: int, db: Session = Depends(get_db)):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    if not FULL_RESEARCH_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="Full research script is missing")

    with _jobs_lock:
        for job in _jobs.values():
            if job.location_id == location_id and job.status in {"queued", "running"}:
                raise HTTPException(
                    status_code=409,
                    detail=f"A full-research job is already running for {location.name}",
                )

        job_id = str(uuid.uuid4())
        job = FullResearchJobOut(
            id=job_id,
            location_id=location.id,
            location_name=location.name,
            status="queued",
            started_at=datetime.now(timezone.utc),
            output=[],
        )
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_full_research_job,
        args=(job_id, location.name),
        daemon=True,
    )
    thread.start()
    return job


@router.get("/full-research-jobs/{job_id}", response_model=FullResearchJobOut)
def get_full_research_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
