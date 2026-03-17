# Relocation

Relocation research workspace for comparing places to live. The repo includes:

- a FastAPI backend under `src/relocation`
- a Typer CLI exposed as `relocation`
- a React + Vite frontend under `frontend`
- AI-assisted research scripts under `scripts`
- generated research markdown under `research`

## Project Structure

- `src/relocation`: backend API, CLI, models, services, and database setup
- `frontend`: React app for browsing locations, rankings, research jobs, and related data
- `scripts`: research and enrichment workflows
- `tests`: backend and script-facing tests
- `research`: generated or curated markdown research files
- `docs`: supporting docs, including the CLI reference

## Getting Started

### Backend

```bash
uv sync --dev
uv run relocation init
uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server proxies `/api` requests to `http://localhost:8000`.

Helper scripts are also available:

```bash
./scripts/start-backend.sh
./scripts/start-frontend.sh
```

## Common Commands

Backend:

```bash
uv run pytest -q
uv run ruff check
uv run relocation --help
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

## Main Entry Points

- API app: `src/relocation/api/app.py`
- CLI app: `src/relocation/cli/main.py`
- Frontend app: `frontend/src/App.jsx`
- Shared frontend API client: `frontend/src/api.js`

## Research Workflows

The OpenAI-backed research scripts expect:

- the backend API to be running
- `OPENAI_API_KEY` to be available in your shell

Examples:

```bash
uv run python scripts/research_location_openai.py "<City>"
uv run python scripts/research_location_openai.py "<City>" --force
uv run python scripts/research_location_openai.py "<City>" --category "Cost"
uv run python scripts/research_location_openai.py "<City>" --skip-description
uv run python scripts/research_location_openai.py "<City>" --force-description
uv run python scripts/full_research_location_openai.py "<City>"
uv run python scripts/full_research_location_openai.py --location-id 42
```

Legacy Anthropic/Claude-oriented script:

```bash
uv run python scripts/research_location.py "<City>"
```

## Location Creation Notes

The current workflow is moving toward exact-place disambiguation before adding a new location.

- Use the backend candidate lookup at `GET /api/v1/location-candidates` or the frontend add-location flow to confirm the exact place first.
- Creating a location with confirmed `latitude` and `longitude` allows the post-create enrichment pipeline to run automatically.
- Creating a location without coordinates is still accepted by the backend, but automatic enrichment is skipped.
- Duplicate location creation now returns `409 Conflict`.

## Documentation

- CLI reference: [`docs/cli-reference.md`](docs/cli-reference.md)

## Notes

Older docs and examples may still mention `uv run relocation serve`. That command is no longer present; start the backend with `uvicorn` instead.
