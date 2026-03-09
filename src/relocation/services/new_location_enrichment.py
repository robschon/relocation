from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OCEAN_SCRIPT = PROJECT_ROOT / "scripts" / "update_ocean_temperatures.py"
SWIMMING_SCRIPT = PROJECT_ROOT / "scripts" / "update_swimming_scores.py"
AUTO_ENRICH_ENV_VAR = "RELOCATION_AUTO_ENRICH_NEW_LOCATIONS"
_DISABLED_VALUES = {"0", "false", "no", "off"}


def _auto_enrich_enabled() -> bool:
    raw_value = os.getenv(AUTO_ENRICH_ENV_VAR, "1")
    return raw_value.strip().lower() not in _DISABLED_VALUES


def _run_pipeline_command(command: list[str], *, step_name: str) -> bool:
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        LOGGER.error(
            "Post-create %s step failed (exit=%s): %s\nstdout:\n%s\nstderr:\n%s",
            step_name,
            completed.returncode,
            " ".join(command),
            (completed.stdout or "").strip(),
            (completed.stderr or "").strip(),
        )
        return False

    if completed.stdout:
        LOGGER.info("Post-create %s output:\n%s", step_name, completed.stdout.strip())
    return True


def run_location_post_create_pipeline(location_id: int) -> None:
    """Populate ocean temperatures and swimming score for a newly created location."""
    if not _auto_enrich_enabled():
        LOGGER.info("Skipping post-create enrichment; %s disabled", AUTO_ENRICH_ENV_VAR)
        return

    if location_id <= 0:
        LOGGER.error("Skipping post-create enrichment; invalid location_id=%s", location_id)
        return

    if not OCEAN_SCRIPT.exists() or not SWIMMING_SCRIPT.exists():
        LOGGER.error(
            "Skipping post-create enrichment; script missing (ocean=%s swimming=%s)",
            OCEAN_SCRIPT.exists(),
            SWIMMING_SCRIPT.exists(),
        )
        return

    ocean_ok = _run_pipeline_command(
        [
            sys.executable,
            str(OCEAN_SCRIPT),
            "--location-id",
            str(location_id),
            "--request-interval-seconds",
            "0",
            "--only-missing",
        ],
        step_name="ocean_temperatures",
    )
    if not ocean_ok:
        return

    _run_pipeline_command(
        [
            sys.executable,
            str(SWIMMING_SCRIPT),
            "--location-id",
            str(location_id),
        ],
        step_name="swimming_score",
    )
