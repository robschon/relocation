"""Compute derived swimming scores from stored ocean temperatures.

Thin wrapper around relocation.enrichment.swimming; run with --help for options.
'uv run relocation pipeline enrich <location>' runs all three enrichment steps.
"""

from relocation.enrichment.swimming import main

if __name__ == "__main__":
    raise SystemExit(main())
