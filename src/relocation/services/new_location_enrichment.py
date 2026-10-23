"""Post-create hook: enrich a new location with ocean, swimming and beach-access data."""

from __future__ import annotations

import logging
import os

from relocation.database import SessionLocal
from relocation.models import Location

LOGGER = logging.getLogger(__name__)

AUTO_ENRICH_ENV_VAR = "RELOCATION_AUTO_ENRICH_NEW_LOCATIONS"
_DISABLED_VALUES = {"0", "false", "no", "off"}


def _auto_enrich_enabled() -> bool:
    return os.getenv(AUTO_ENRICH_ENV_VAR, "1").strip().lower() not in _DISABLED_VALUES


def run_location_post_create_pipeline(location_id: int) -> None:
    """Populate deterministic ocean/swimming/beach scores for a newly created location (runs in-process)."""
    if not _auto_enrich_enabled():
        LOGGER.info("Skipping post-create enrichment; %s disabled", AUTO_ENRICH_ENV_VAR)
        return
    if location_id <= 0:
        LOGGER.error("Skipping post-create enrichment; invalid location_id=%s", location_id)
        return

    with SessionLocal() as session:
        location = session.get(Location, location_id)
        if not location:
            LOGGER.error("Skipping post-create enrichment; location_id=%s not found", location_id)
            return
        if location.latitude is None or location.longitude is None:
            LOGGER.info("Skipping post-create enrichment; location_id=%s has no confirmed coordinates", location_id)
            return

    from relocation.enrichment.runner import enrich_locations

    result = enrich_locations([location_id], request_interval_seconds=0, log=LOGGER.info)
    if not result.ok:
        LOGGER.error("Post-create enrichment for location_id=%s finished with failures: %s", location_id, result.exit_codes)
