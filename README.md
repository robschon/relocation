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
- `research`: generated markdown, one `<slug>.md` per location (`scripts/export_research_markdown.py --all --prune`); `research/archive/` holds files for removed locations
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

## Database migrations

The schema is managed with Alembic (migrations live in `src/relocation/migrations/versions`).
The backend applies pending migrations on startup, and `uv run relocation init` does the same.

```bash
uv run alembic upgrade head                                # apply migrations
uv run alembic current                                     # show the DB's revision
uv run alembic revision --autogenerate -m "describe change" # after editing models.py
```

`tests/test_migrations.py` fails if `models.py` and the migrations drift apart.
Back up first: `data/backups/` is git-ignored and is the place for copies.

## Research runs and provenance

Every pipeline execution is a row in `research_runs` (kind, provider, model, prompt version,
status, step, log tail). Research, scores, pros/cons, visa rows and LLM calls carry `run_id`
and `provider`; scores also record `method` (manual / llm / derived) and the `research_id`
they were based on. Only one research row per location/category/provider is `is_current`;
older rows are kept as history (`GET /api/v1/research?current_only=true` hides them).
Full-research jobs on the Research Jobs page are runs, so they survive backend restarts.

## Countries and country-level categories

Every location and visa row belongs to a `countries` row (ISO alpha-2; Puerto Rico is `PR`
under `US`). Categories carry behaviour flags (`key`, `scope`, `kind`, `needs_web`,
`requires_citation`, `refresh_after_days`). Visa/residency is `scope=country`: its research
and score live on the country (`country_scores`) and are shared by every location there. The
API returns them with each location's scores and research, and stores visa writes made
"for a location" on its country. Raw SQL readers should use the `effective_scores` view.

Research scripts re-research a category only when it's missing, older than its
`refresh_after_days`, or forced (`--force` / `--force-research`), and re-score only when
the evidence changed.

## People and derived scores

Users have a `name` (e.g. `partner_a`) and a `display_name` (`Partner A`). Rankings work for any set of
people: `/api/v1/rankings` returns each person's score keyed by user id, and `?user=partner_a`
ranks by one person. Swimming viability and beach access are computed from data, never by
the LLM:

```bash
uv run python scripts/preview_derived_scores.py        # see ranking changes on a copy first
uv run relocation pipeline enrich                       # ocean data -> swimming -> beach, missing only
uv run relocation pipeline enrich Funchal --refresh     # refetch one location
uv run relocation pipeline enrich -s swimming           # recompute swim scores (19°C, ≤60 km)
```

The same steps are available as `scripts/update_ocean_temperatures.py`,
`scripts/update_swimming_scores.py` and `scripts/update_beach_accessibility_scores.py` with
their full set of flags. New locations with coordinates are enriched automatically.

A manual score for these categories overrides the computed one.

Overpass (overpass-api.de) is a shared public server and is often overloaded. Use
`--only-missing` for routine beach runs, which only fetches locations without a computed score
and retries earlier fallbacks. Use `--overpass-url` to switch to a mirror such as
`https://overpass.kumi.systems/api/interpreter`. If the first few lookups can't connect, the
script stops without writing anything.

## LLM token usage

Every OpenAI call made by the research scripts is recorded in the `llm_calls` table
(tokens in/cached/out/reasoning, retries, latency, location/category).

```bash
uv run relocation llm-usage
uv run relocation llm-usage --since 2026-10-21 --location Valencia
```

Set `RELOCATION_LLM_USAGE_LOG=0` to turn recording off.

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

## Research Workflows (pipeline v2)

Research needs `OPENAI_API_KEY` in your shell or in a `.env` file at the project root
(see `.env.example`). The backend does **not** need to be running: the pipeline writes to
the database directly, and jobs started from the UI run inside the backend process.

```bash
uv run relocation pipeline run "<City>"            # research + score what's missing or stale
uv run relocation pipeline run 42 --force          # redo every researched category + visa info
uv run relocation pipeline run "<City>" -c tax     # one category
uv run relocation pipeline rescore -c visa -c tax  # re-score from stored evidence (no web search)
uv run relocation pipeline smoke-test              # one cheap call: checks web search + structured output
uv run relocation pipeline trial 4 5 6             # v2 on a copy of the DB, compared with v1
```

The old script names still work and call the same code:
`scripts/research_location_openai.py`, `scripts/full_research_location_openai.py`,
`scripts/rescore_categories_openai.py`.

How a run works:
- Each researched category is **one call** that returns a ~250-word summary, 5–10 key facts,
  a score and its rationale. Categories with `needs_web` (cost, healthcare, travel, visa, tax)
  use web search, and their `source_urls` come from the tool's citations. Visa and tax must
  have citations.
- A category is researched again only when it's missing, older than its `refresh_after_days`,
  or forced. If its evidence is current but its score isn't linked to it, it's re-scored
  from the stored evidence.
- Visa pathways are researched once per country (every 90 days).
- Pros/cons and the description come from one call to the synthesis model, and only when
  a score changed.
- Swimming and beach access are never sent to the LLM.
- Prompts start with the same instructions and profile brief for every call in a run, then
  the place, then the category, so prompt caching can reuse the common start. The profile
  brief only includes finance details for cost, tax and visa, and health details for healthcare.
- Settings: `RELOCATION_RESEARCH_MODEL`, `RELOCATION_SYNTHESIS_MODEL` (default `gpt-5.4-mini`),
  `RELOCATION_SERVICE_TIER=flex` (or `--flex`) for cheaper bulk runs, `RELOCATION_WEB_SEARCH=0`
  to turn search off. See `src/relocation/settings.py`.

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
