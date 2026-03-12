# Relocation Planning Tool — Current State Plan

Updated: 2026-03-11

## 1) Project Snapshot (Current)

### Core stack
- Backend: FastAPI + SQLAlchemy + SQLite
- CLI: Typer (`relocation`)
- Frontend: React + Vite + Tailwind + Recharts
- Research automation: OpenAI/Anthropic-powered scripts + deterministic scoring scripts

### What is running today
- Full CRUD-style workflows for locations, scores, weights, research, pros/cons, and visa info (API + CLI, with some intentional read-only endpoints like categories/users).
- Ranking engine for `husband`, `wife`, and `combined`.
- Profile questionnaire + markdown export.
- Ocean temperature ingestion and query APIs.
- Derived category scoring for:
  - Year-round swimming viability
  - Beach accessibility
- Full-research job launcher endpoint with progress polling.
- React dashboard and management pages across major entities.

### Local database snapshot (from `data/relocation.db` on 2026-03-11)
- Locations: 108
- Categories: 15
- Scores: 1,620
- Weights: 30
- Research entries: 1,646
- Pros/cons: 1,702
- Visa entries: 155
- Ocean temperature monthly rows: 1,284 (107 locations represented)

### Verification status
- Backend/unit/API tests: `63 passed` (`uv run pytest -q`)
- Frontend production build: passes (`npm run build`)
- Lint status:
  - Python lint (`ruff`): failing (3 unused imports)
  - Frontend lint (`eslint`): failing (React hooks/state-in-effect and one unused variable)

## 2) Completed Work

### Phase A — Foundation (Done)
- Data model established for users, locations, categories, scores, weights, research, pros/cons, visa, profile responses, ocean temperatures.
- DB init/seed workflow in place (`relocation init`).
- Seed categories expanded from original 13 to 15 (adds swimming viability + beach accessibility).

### Phase B — Core Product Surface (Done)
- CLI commands implemented for all primary workflows:
  - `location`, `category`, `score`, `weight`, `research`, `pros-cons`, `visa`, `profile`, `rank`
- API routers implemented for:
  - locations, categories, scores, weights, research, pros/cons, visa, profile, rankings, users, ocean temperatures, full-research jobs
- Ranking service supports per-user and combined scoring outputs with category-level detail.

### Phase C — Research/Data Enrichment (Mostly Done)
- Research and visa schemas now include source provenance and confidence fields.
- Freshness/evidence validation added for strict categories (notably visa/tax pathways).
- New-location background enrichment pipeline runs:
  - Ocean temperatures update
  - Swimming score update
  - Beach accessibility score update
- Script suite exists for research generation, rescoring, normalization, and exports.

### Phase D — Frontend Application (Implemented, Needs Hardening)
- React app routes/pages are in place for dashboard, locations, location detail, score matrix, weights, research, pros/cons, visa, profile, ocean temperatures.
- Full-research jobs can be started from the UI and polled for progress.
- Data visualizations available (rank charts/radar comparison).

## 3) Current Gaps / Risks

### Engineering hygiene
- Lint gates are currently red:
  - Backend: 3 Ruff violations.
  - Frontend: React hooks/state-in-effect lint errors + warnings.
- No frontend automated test suite yet (backend test coverage is strong).

### Reliability/operational
- Full-research jobs are in-memory only; job state does not survive backend restart.
- DB migration approach is currently SQLite compatibility logic in `init_db()` rather than versioned migrations (no Alembic flow in active use).

### Documentation drift
- Some docs mention `uv run relocation serve`, but current CLI has no `serve` command.
- `PLAN.md` was previously a greenfield blueprint and did not reflect current implementation details until this update.

## 4) Active Priorities (Next)

### Priority 1 — Stabilize quality gates
- Fix Python Ruff violations and make `ruff check` pass.
- Fix frontend ESLint violations and warnings.
- Add lint checks to routine validation commands.

### Priority 2 — Align docs with reality
- Update README and `docs/adding-a-location.md` to use current run commands (e.g., `uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000`).
- Document current 15-category model and deterministic enrichment behavior.

### Priority 3 — Improve job durability
- Persist full-research job metadata/status in DB (or durable store) instead of process memory.
- Add restart-safe polling behavior for the frontend.

### Priority 4 — Frontend performance and confidence
- Address bundle-size warning (~698 kB built JS chunk) via code splitting.
- Add at least smoke-level UI tests for critical flows (locations, research, rankings).

## 5) Medium-Term Roadmap

### Data quality and governance
- Expand strict freshness/verification policies beyond visa/tax where appropriate.
- Add stale-data reporting and recheck workflows.

### Product workflow improvements
- Streamline “add location” flow into one orchestrated backend pipeline.
- Improve error/reporting UX for long-running research tasks.

### Nice-to-have / deferred
- Google Sheets sync remains unimplemented (still optional/deferred).

## 6) Current Runbook

```bash
# Backend
uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000

# CLI init
uv run relocation init

# Tests
uv run pytest -q

# Python lint
uv run ruff check

# Frontend
cd frontend
npm run dev
npm run build
npm run lint
```
