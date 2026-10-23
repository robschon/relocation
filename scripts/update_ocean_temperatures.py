"""Fetch monthly ocean temperature climatology (Open-Meteo marine) for locations.

Thin wrapper around relocation.enrichment.ocean; run with --help for options.
'uv run relocation pipeline enrich <location>' runs all three enrichment steps.
"""

from relocation.enrichment.ocean import main

if __name__ == "__main__":
    raise SystemExit(main())
