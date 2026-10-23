"""Compute derived beach-access scores from OpenStreetMap (Overpass) beach data.

Thin wrapper around relocation.enrichment.beach; run with --help for options.
'uv run relocation pipeline enrich <location>' runs all three enrichment steps.
"""

from relocation.enrichment.beach import main

if __name__ == "__main__":
    raise SystemExit(main())
