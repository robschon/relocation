"""Run the enrichment steps in order, in-process: ocean temperatures -> swimming score -> beach-access score.

Swimming depends on ocean data, so it (and beach access, which falls back to the
ocean-grid distance) is skipped when the ocean step fails. Each scoring step
records its own ``research_runs`` row (kind ``enrichment``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from relocation.enrichment import beach, ocean, swimming

STEPS = ("ocean", "swimming", "beach")


@dataclass
class EnrichmentResult:
    exit_codes: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(code == 0 for code in self.exit_codes.values())


def _call(step: str, main: Callable[[list[str]], int], argv: list[str], log: Callable[[str], None]) -> int:
    log(f"[enrich] {step}: {' '.join(argv) or '(all locations)'}")
    try:
        code = main(argv)
    except SystemExit as exc:  # argparse / script-level aborts
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:  # noqa: BLE001 - one failed step must not crash the caller
        log(f"[enrich] {step} failed: {type(exc).__name__}: {exc}")
        code = 1
    return int(code or 0)


def enrich_locations(
    location_ids: list[int] | None = None,
    *,
    steps: tuple[str, ...] = STEPS,
    refresh: bool = False,
    request_interval_seconds: float | None = None,
    log: Callable[[str], None] = print,
) -> EnrichmentResult:
    """Enrich the given locations (or all). Without ``refresh``, only missing ocean data / beach scores are fetched."""
    ids: list[str] = []
    for location_id in location_ids or []:
        ids += ["--location-id", str(location_id)]
    interval = [] if request_interval_seconds is None else ["--request-interval-seconds", str(request_interval_seconds)]
    result = EnrichmentResult()

    if "ocean" in steps:
        argv = ids + interval + ([] if not refresh else ["--no-only-missing"])
        code = _call("ocean", ocean.main, argv, log)
        # Exit 1 = nothing to do (all ocean data already present), which is fine.
        result.exit_codes["ocean"] = 0 if code == 1 and not refresh else code
        if result.exit_codes["ocean"] != 0:
            log("[enrich] ocean step failed; skipping swimming and beach")
            return result
    if "swimming" in steps:
        result.exit_codes["swimming"] = _call("swimming", swimming.main, list(ids), log)
    if "beach" in steps:
        argv = ids + interval + ([] if refresh else ["--only-missing"])
        result.exit_codes["beach"] = _call("beach", beach.main, argv, log)
    return result
