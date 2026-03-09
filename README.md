# Relocation

CLI and API tooling for evaluating relocation candidates.

## AI Research Script Quick Start

Prereqs:
- API server running: `uv run relocation serve`
- OpenAI key set in your shell: `OPENAI_API_KEY`

Run with OpenAI (default path):

```bash
uv run python scripts/research_location_openai.py "<City>"
uv run python scripts/research_location_openai.py "<City>" --force
uv run python scripts/research_location_openai.py "<City>" --category "Cost"
uv run python scripts/research_location_openai.py "<City>" --skip-description
uv run python scripts/research_location_openai.py "<City>" --force-description
```

Optional Claude version (legacy):

```bash
uv run python scripts/research_location.py "<City>"
uv run python scripts/research_location.py "<City>" --skip-description
uv run python scripts/research_location.py "<City>" --force-description
```
