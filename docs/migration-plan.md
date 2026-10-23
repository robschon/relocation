# Relocation DB — Migration Plan

Drafted 2026-10-21. Covers the database refactor and a redesign of the OpenAI research calls.

The phases are ordered so each one ships on its own and the app keeps working between them. Phases 0–3 change the database. Phase 4 changes the research pipeline, and it depends on the provenance, country and category-flag work in Phases 1–3. Phase 5 is cleanup.

---

## What the audit found (baseline)

**Database**
- 129 locations, 45 countries, 15 categories. 3,396 research rows for 1,935 location/category slots: 1,461 rows (4.6M chars, 29% of all research text) have been superseded, and nothing marks which row is current.
- `PRAGMA foreign_keys` is off. There are no indexes on foreign-key columns. Schema changes are made by hand-written code in `init_db()` on every startup. `location_provider_states` exists in the DB but not in `models.py`.
- Visa and tax are scored per location and then forced to match per country by `normalize_country_category_scores.py`. `visa_info` is matched on a country name string and has duplicates (Belize). It also uses a made-up "US Territories" country, while Puerto Rico locations are filed under "United States".
- "husband"/"wife" is hard-coded about 107 times across the backend and frontend.
- Three write paths: scripts calling the API over HTTP, scripts using the ORM, and scripts using raw `sqlite3`. Validation lives in the routers, so two of those paths skip it.

**Research calls** (details in Phase 4)
- **No web search is enabled.** `client.responses.parse(...)` is called without `tools=[{"type": "web_search"}]`. The visa/tax prompt says "You must use live web research," but the model can't, so every `source_urls` entry and every "Web research checked March 2026" source line came from the model's memory. The model also sets `verification_status` itself: 1,177 rows say "verified".
- **The derived scores were overwritten.** All 129 "Year-round swimming viability" and all 129 "Beach accessibility" scores are LLM prose. None carries the deterministic note from `update_swimming_scores.py` or `update_beach_accessibility_scores.py`. The full pipeline researches and LLM-scores these two categories after the ocean/beach computation has run.
- **Country work is repeated per location.** Visa and tax research run again on every full run because of the freshness policy, with or without `--force` (visa: 301 rows for 129 locations; tax: 266). `visa_info` for a country is deleted and regenerated every time any location in that country is researched: about 129 visa calls where 45 would do.
- **All 15 scores are regenerated on every run**, including for categories whose research was skipped as unchanged.
- **The full profile goes into every call.** That's about 5.4k chars, including finances and health, sent in 17 calls per location. It also sits in the middle of the prompt, after text that changes per category, so prompt caching can't reuse it.
- **Retries resend the same request.** On a length error the same prompt goes out again with the same `max_output_tokens`, up to 4 attempts. No reasoning effort is set, and on a reasoning model the hidden reasoning tokens use up that same budget.
- **Token usage is never recorded.**

---

## Phase 0 — Safety net and measurement (½ day) — ✅ implemented 2026-10-22 in `~/Code/relocation` (branch `phase-0-db-foundation`; first built in the `relocation claude` copy)

**Status notes**
- Backup: `data/backups/relocation-20261022-pre-phase0.db`. The live DB is migrated to `0002_indexes_llm_calls`.
- Alembic revisions: `0001_baseline` (schema as of Phase 0) and `0002_indexes_llm_calls`. Existing DBs are patched once with the old compat code (`relocation/legacy_compat.py`) and stamped at the baseline; `init_db()` / app startup then upgrade to head. `tests/test_migrations.py` fails if models and migrations drift.
- A pre-Alembic DB is adopted inside `migrations/env.py`, so it works through both `alembic upgrade head` and app startup.
- Indexes: only `research(location_id, category_id)` and `pros_cons(location_id)` were needed. `scores`, `weights` and `ocean_temperature_monthly` already have unique constraints that start with their FK column.
- **Undocumented drift found in the live DB.** `research`, `scores`, `pros_cons` and `visa_info` each have a `provider` column (default `'openai'`; every row is `openai`). The scores uniqueness rule is `(location_id, category_id, provider)`, not `(location_id, category_id)`. Together with `location_provider_states` and a leftover compiled `providers.py`, this comes from a multi-provider experiment that isn't in this checkout. Phase 0 leaves it alone; Phase 1 has to drop it or adopt it (Decision 7).
- Fixed along the way:
  - The visa step always failed: the structured-output schema had an array at the top level, which OpenAI rejects.
  - Old visa rows were deleted before the replacement research had succeeded.
  - The model's free-text `verification_status` failed the API's validation.
  - The start scripts were hard-coded to `~/Code/relocation`.
- First baseline (Lima, v1 pipeline, 34 calls): 53.4k input tokens, 0 cached, 24.8k output. Research accounts for 21.2k of the output; scoring takes 20k of input to produce 1.9k of output.
- `uv run relocation init` re-adds any of the 4 original seed locations that were deleted (it added 2 on a copy of the live DB). To migrate, use `uv run alembic upgrade head` or restart the backend.


1. **Back up** `data/relocation.db` to `data/backups/relocation-YYYYMMDD.db` using the SQLite backup API, not a file copy while the server is running. Do this again before every phase.
2. **Repo hygiene.** Run `git rm --cached` on `logs/` and `.DS_Store`. Add `logs/`, `.uv-cache/`, `.pycache/`, `.DS_Store` and `data/backups/` to `.gitignore`.
3. **Alembic.** `alembic init`, set `render_as_batch=True` (SQLite needs batch mode for column changes), write a baseline revision that matches the current schema, and `alembic stamp head`. Then remove `_run_sqlite_compat_migrations()` from startup; `init_db()` only runs `alembic upgrade head`.
4. **Foreign keys on.** Add a `connect` event listener in `database.py` that runs `PRAGMA foreign_keys=ON`. Orphan checks are already clean (0 orphans in scores, research, pros_cons and ocean temperatures).
5. **Indexes.** Add a migration with indexes on `research(location_id, category_id)`, `scores(location_id)`, `pros_cons(location_id)` and `ocean_temperature_monthly(location_id)`.
6. **Token logging.** Add an `llm_calls` table with these columns: `id`, `run_id` (nullable for now), `route` (research/visa/score/pros_cons/description), `model`, `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`, `web_search_calls`, `finish_reason`, `attempt`, `latency_ms` and `created_at`. Record `response.usage` inside `generate_structured_output`. Run the current pipeline with `--force-research` on 3 locations to get a real baseline before changing anything.

**Exit check:** tests pass, `alembic upgrade head` on a copy of the DB is a no-op, and there are baseline token numbers for 3 locations.

---

## Phase 1 — Provenance: runs, methods, current evidence (1–2 days) — ✅ implemented 2026-10-22 (same branch)

**Status notes**
- Migration `0003_runs_provenance` is applied to the live DB. Backup of the state just after it: `data/backups/relocation-20261022-after-0003.db`. A test run applied the migration slightly early; the result matched the verified copy, and tests can no longer reach `data/relocation.db` (`tests/conftest.py`).
- Decision 7 → **keep multi-provider**. `provider` is now in the models on research, scores, pros_cons and visa_info, and on research_runs and llm_calls. Scores are unique per (location, category, provider). API reads take an optional `provider` filter. Rankings and "fully scored" use one provider (default `openai`). `location_provider_states` was folded into `research_runs` and dropped.
- Decision 2 → **reset**. 1,190 research and 29 visa rows went from model-claimed "verified" to `needs_review` with `verified_by='model-legacy'`. The original value can be recovered from that tag. Scripts no longer ask the model for a status.
- Backfill: one `legacy` backfill run owns all pre-existing rows, and 129 past full runs were rebuilt from `full_research_ran_at` (hidden from the jobs page). `is_current` = newest row per (location, category, provider). All 1,935 scores got `method='llm'` and a `research_id`.
- Jobs are `research_runs` rows (kind `full`). They survive restarts, and a restart marks unfinished ones `interrupted`. Scripts create their own run when launched by hand (`category` / `full` / `rescore` / `backfill`) and tag every row and LLM call with it.
- Deferred: `locations.full_research_ran_at` is still written (the Locations page reads it). Derived swim/beach scores are written under provider `openai` only, so a second provider's rankings would lack them; handle in Phase 3.

**New table `research_runs`**: `id`, `kind` (full / category / country / rescore / backfill), `location_id` (nullable), `country_code` (nullable), `provider`, `model`, `prompt_version`, `status` (queued / running / completed / failed / interrupted), `step`, `error`, `log_tail` (text, last ~400 lines), `started_at` and `finished_at`.

This replaces three things:
- the in-memory `_jobs` dict in `full_research.py`;
- `location_provider_states`, which gets dropped;
- `locations.full_research_ran_at`, which becomes derivable from the latest completed `full` run and is dropped once the UI reads from runs.

**Column changes**
- `research`: add `run_id` FK and `is_current` bool. Add a partial unique index on `(location_id, category_id) WHERE is_current`.
- `scores`: add `run_id` FK, `method` (`manual` / `llm` / `derived`) and `research_id` FK (the evidence row the score was based on).
- `pros_cons`, `visa_info`: add `run_id` FK.
- `research`, `visa_info`: add `verified_by` (nullable text). `verification_status` becomes something a person or a link-checker sets. The model never sets it.

**Backfill (inside the migration)**
- Create one synthetic run, `kind='backfill', prompt_version='legacy'`, and point all existing rows at it.
- `is_current = true` for the highest `id` per (location, category). Everything else is `false`; the rows are kept as history.
- `scores.method = 'llm'` for all 1,935 rows, because all of them are, including swim and beach. Set `research_id` to the current research row for each slot.
- Model-set "verified" (1,177 rows) → see Decision 2.

**Code**
- All readers use `is_current` instead of "newest id wins". That logic is duplicated today in `research_location_openai.py`, `full_research_location_openai.py` and `rescore_categories_openai.py`.
- The jobs API reads and writes `research_runs`. On startup, any run still marked `running` becomes `interrupted`, so a backend restart no longer loses job state.

---

## Phase 2 — Countries and category flags (1–2 days) — ✅ implemented 2026-10-22 (same branch)

**Status notes**
- Migration `0004_countries` is applied to the live DB. Backup just before it: `data/backups/relocation-20261022-pre-0004.db`. Downgrade isn't supported; restore that backup instead.
- **Change from the original plan: tax stays per location.** Tax scores vary 4–7 inside the US and inside Spain because of state and regional regimes (Puerto Rico's Act 60, Hawaii vs California and New York, the Canary Islands and the Basque foral regime), so only visa/residency is `scope=country`.
- Decision 1 → **Puerto Rico is its own jurisdiction** (`PR`, parent `US`). Luquillo, Rincón and Esperanza moved to it. The 5 "US Territories" visa rows were removed. The U.S.-citizen "no visa needed" rule covers US and PR.
- 48 countries. Codes were filled for Cuba, India, Sri Lanka, Madagascar and Slovenia. `pycountry` resolves any ISO country, and a country row is created automatically whenever a new code is written. Unknown countries are rejected with a 422.
- Visa: 46 country research rows (newest per country; the rest are history). 46 country scores, each the median of that country's locations. This moved 5 towns by 1 point: Dauin 7→8, Kailua 9→10, Loreto 8→9, Tecolutla 8→9, Valencia 9→8. Duplicate Belize visa rows were collapsed.
- The API translates both ways. Reading a location's scores or research includes its country's visa row. Writing a visa score or research "for a location" stores it on the country. The frontend works unchanged; the Research page labels country rows. Writing a location-level `Score` for a country-scope category is rejected.
- `effective_scores` SQL view for raw-SQL scripts (markdown export, correlation heatmap). Future batch migrations on locations/scores/categories must drop and recreate this view around the table rebuild.
- Pulled forward from Phase 4:
  - Research uses each category's `refresh_after_days`: visa/tax every 90 days; cost, healthcare, safety and travel yearly; the rest never unless forced.
  - Visa info is refreshed per country on the same 90-day interval.
  - A category is only re-scored when its evidence changed.
  - Effect: re-running a location without `--force-research` dropped from 33 LLM calls to 1 (pros/cons) in testing.
- `normalize_country_category_scores.py` is deleted. Category name-matching in the router and scripts is replaced by `key` / `requires_citation` / `scope` / `kind`.


**New table `countries`**: `code` (ISO-3166 alpha-2, PK), `name`, `parent_code` (nullable, for territories).
- Fill it from `countries.py`. Add PR, GU, VI, AS and MP as jurisdictions with `parent_code='US'`; see Decision 1.
- `locations.country_code` becomes a NOT NULL FK. `locations.country` is kept as a display column for one release, then dropped.
- `visa_info.country` becomes `country_code` FK. Remove duplicates (Belize QRP and Permanent Residence appear twice). Move the "US Territories" rows to the right jurisdictions or delete them.

**Categories get behaviour flags** (migration adds columns and backfills them):

| key | scope | kind | needs_web | refresh_after_days |
|---|---|---|---|---|
| cost_of_living | location | researched | yes | 365 |
| climate | location | researched | no | — |
| healthcare | location | researched | yes | 365 |
| visa | **country** | researched | yes | 90 |
| tax | **country** | researched | yes | 90 |
| safety_values | location | researched | no | 365 |
| language_community | location | researched | no | — |
| walkability | location | researched | no | — |
| culture | location | researched | no | — |
| travel_connectivity | location | researched | yes | 365 |
| food | location | researched | no | — |
| nature | location | researched | no | — |
| environment_climate_risk | location | researched | no | — |
| swimming | location | **derived** | — | — |
| beach_access | location | **derived** | — | — |

Also add `requires_citation` (true for visa and tax). This replaces the name-matching sets in `research.py`, `research_location_openai.py` and `backfill_beach_accessibility_research_openai.py`, including the misspelling check for `"beachaccesibility"`.

**Country-level evidence and scores**
- `research`: make `location_id` nullable and add `country_code`, with `CHECK ((location_id IS NULL) != (country_code IS NULL))`. The partial unique index for current rows covers both subject types.
- New table `country_scores`: `country_code`, `category_id`, `score`, `method`, `run_id`, `research_id`, `notes`, timestamps.
- New view `effective_scores`: location scores for location-scope categories joined with country scores for country-scope ones. Rankings and the frontend read this view.
- **Backfill:** each country's visa/tax score = median of its locations' current scores (what the normalize script does now). Log countries where the locations disagreed by ≥2 points so they can be checked. The current visa/tax research for one location per country becomes the country's current research; the rest become history.
- Delete `scripts/normalize_country_category_scores.py`.

---

## Phase 3 — People, derived scores, rankings (1 day) — ✅ implemented 2026-10-22

**Status notes**
- Migration `0005_named_users`: users `husband` → `partner_a` (Partner A) and `wife` → `partner_b` (Partner B), with ids kept. It runs when the backend restarts. Backup: `data/backups/relocation-20261022-pre-0005.db`.
- Rankings work for any set of users. The API returns `user_scores` and per-category `weights`/`weighted` keyed by user id, plus `scored_categories` / `total_categories` / `coverage`. `?user=` takes a name or id. The CLI, Dashboard, Compare, Sensitivity Analysis and Map pages build their columns, bars and labels from `/users`; Compare and the Dashboard's "biggest differences" table compare the first two people.
- Derived categories: an LLM can't write a score for them (API 422 and an ORM guard), and the pipeline no longer researches or scores them. One computed row per location (provider `computed`, method `derived`) serves every provider. A manual override wins, then the computed score, then a legacy LLM score.
- `update_swimming_scores.py` now scores 0 when the nearest sea is more than 60 km away (`--max-sea-distance-km`). Before this, Chiang Mai (~300 km inland) and Bartica (82 km) got 10.
- `scripts/preview_derived_scores.py` recomputes swim/beach on a temporary copy and prints and saves the ranking changes. Swim-only preview on 2026-10-22: 30 of 129 locations change.
  - Cold-water mainland Portugal falls: Faro, Lagos and Cascais go to 0; Cascais drops from 14th to 38th.
  - Warm islands rise: Funchal 26th → 8th; Costa del Silencio and Icod de los Vinos also climb.
  - The beach preview needs Overpass, which some networks block.
- Not changed: pages still pass `fully_scored_only=true`. All 129 locations are complete, so this hides nothing today; `coverage` is available if we want to show partial locations later.
- Applied 2026-10-22:
  - Swim recomputed for 125 locations; beach recomputed from Overpass for all 129, with 5 still on fallback for an `--only-missing` retry.
  - The 4 locations without ocean data keep their LLM swim score until `update_ocean_temperatures.py --only-missing` runs.
  - Funchal rose from 26th to 3rd. East Bay was set to a manual beach score of 3, because the many mapped Bay beaches inflated the computed score.
  - Overpass hardening: a descriptive User-Agent (it now returns 406 to generic clients), 20 km bounding-box queries that widen to 50 km only when needed, `--only-missing`, `--overpass-url`, and nothing is written when every lookup fails.


**Users**
- Rename the rows `husband` → `Partner A` and `wife` → `Partner B`, keeping the ids so weights stay attached. Add `display_name`.
- `compute_rankings(session, user_ids: list[int], blend="mean")`. Remove the hard-coded names from `ranking.py`, the routers, the CLI and the frontend (about 107 places). The API returns per-user scores keyed by user id.

**Derived categories**
- The service layer refuses LLM writes to `kind='derived'` categories.
- Rerun `update_swimming_scores.py` and `update_beach_accessibility_scores.py` for all 129 locations with `method='derived'`. **This will move rankings** (Decision 3). Snapshot the rankings before and after and show the difference.
- Stop researching these two categories with the LLM. Keep the existing rows as history.

**Missing scores**
- Rankings return `coverage = scored / total categories`. A location with missing scores is labelled, not quietly re-weighted. Then remove the frontend workaround that hides incomplete locations on some pages.

---

## Phase 4 — Single write path and research pipeline v2 (3–4 days) — ✅ implemented 2026-10-22; real-API trial pending

**Status notes**
- `relocation/pipeline/`:
  - `llm` (Responses API, web search, citations, retries, usage)
  - `context` (profile brief, prompt order)
  - `policy` (refresh rules)
  - `steps` (research + score, rescore, visa info, synthesis)
  - `runner`
  - `trial` (v2 on a DB copy vs v1)

  Settings are in `relocation/settings.py` (pydantic-settings, `.env`); see `.env.example`.
- One call per category returns summary, key facts, score and rationale. Key facts are stored in `research.key_facts` (migration `0006`). Web search (`search_context_size=low`) runs only for `needs_web` categories. `source_urls` come from `url_citation` annotations, falling back to `web_search_call` sources. Visa and tax must have them.
- If the API rejects web search combined with structured output, the client switches to two calls (search, then format) for the rest of the run. `relocation pipeline smoke-test` checks this with one call.
- Prompt order: identical instructions (rules, rubric, profile brief), then place, then category, so caching can work. The base brief has no finance or health details; those are added only for cost, tax, visa and healthcare. Note: caching only applies once the shared prefix exceeds about 1,024 tokens, so a short brief may stay below that.
- Synthesis (pros/cons + description) is one call on `RELOCATION_SYNTHESIS_MODEL` (default `gpt-5.4-mini`), run only when a score changed. Length cut-offs retry with a 50% larger budget. `--flex` / `RELOCATION_SERVICE_TIER=flex` gives cheaper bulk runs. Reasoning effort is left at each model's default (v1 showed 0 reasoning tokens), and is configurable.
- Single write path: the API job runs the pipeline in a worker thread (no subprocess, no HTTP back to localhost). Validation for research citations, score rules and visa evidence lives in `services/`, with API exception handlers mapping errors to 404/422. The scripts are thin wrappers. `research_location.py` (Anthropic) and `backfill_beach_accessibility_research_openai.py` are removed.
- Fake-client test, forced run of 3 locations on a live-DB copy: 15 calls per location vs 32–34 in v1. The real token comparison needs `relocation pipeline trial 4 5 6` on a machine with the API key.
- Not done / deviations:
  - No Batch API (flex covers the discount).
  - No per-country `allowed_domains` filter for visa/tax (no curated list of official domains); the prompt asks for official sources instead.
  - Post-create enrichment still runs the swim/beach scripts as subprocesses.
  - 4d backfill waits on the trial results.


### 4a. Structure
- Move the logic into a `relocation/pipeline/` package: `context.py` (profile brief, location block), `llm.py` (client, routing, retries, usage logging), `research.py`, `country.py`, `synthesis.py` and `runner.py`.
- Scripts become thin wrappers that call the pipeline with a database session. **No more HTTP calls to localhost:8000**, and no more subprocesses started from the API.
- Validation (citations required, country normalization, derived-category guard) moves from the routers into `relocation/services/`. The API, CLI and pipeline all go through it.
- **Worker:** a small thread pool in the backend that takes `research_runs WHERE status='queued'`. Post-create enrichment becomes a queued run too.
- **Config:** `pydantic-settings` with a `.env` file for `OPENAI_API_KEY` and the model per route. Delete `_discover_env_var_from_zsh`.
- Retire `scripts/research_location.py` (the legacy Anthropic script), or keep it only behind a provider interface in `llm.py`.

### 4b. Call map: current vs proposed

Token figures are estimates (≈4 chars/token), worked out from the actual prompt templates and stored output sizes. Phase 0 logging replaces them with measured numbers.

**Current full run: about 33 calls per location**

| Step | Calls | Input/call | Visible output/call |
|---|---|---|---|
| Category research | 15 | ~1.9k (profile ~1.4k) | ~1.3k (content avg 4.7k chars) |
| Visa (`visa_info`) | 1 | ~1.7k | ~2–3k |
| Score each category | 15 | ~1.6k (re-sends the research) | ~150 |
| Pros/cons | 1 | ~2.8k | ~700 |
| Description | 1 | ~2.5k | ~60 |
| **Total** | **~33** | **~59k** | **~25k + reasoning** |

That's before retries and before the reasoning tokens, which are billed as output.

**Proposed: about 12 calls for a new location in a country already researched**

| Step | Calls | Notes |
|---|---|---|
| Location research + score | 11 | One call returns evidence **and** score. Covers the 15 categories minus visa, tax, swimming and beach. Web search only where `needs_web`. Shared prompt opening (cached), category-specific text last. |
| Country research (visa, tax, `visa_info`) | 0 if fresh; 1–2 per country when stale | Runs per country, refreshed only after `refresh_after_days`. Web search with domain filters; government domains first. |
| Synthesis | 1 | Pros/cons and the description in one call, on a smaller model with low reasoning effort. |
| Derived scores | 0 | Computed. |
| **Total** | **~12** | **Roughly 16k input (most of it cached) and 8k output.** |

That's about 70% fewer output tokens per location, the expensive part. Some of the saving goes back into web-search fees on the 5 web-enabled categories, and those are the calls whose citations become real.

### 4c. Specific changes, in order of value

1. **Turn web search on where it matters**, and make citations come from the tool, not from the model's memory.
   - Use `tools=[{"type": "web_search", "search_context_size": "low"}]`, with `filters.allowed_domains` for visa and tax (official immigration and tax sites first).
   - Fill `source_urls` from the response's URL citations, not from a JSON field the model writes.
   - First check that `responses.parse` with structured output works together with the web search tool on your model. If it doesn't, split the call into search-then-format.
2. **Research once per country** for visa, tax and `visa_info`. Refresh by age (`source_checked_at` older than `refresh_after_days`), not on every run.
3. **Never LLM-research or LLM-score the derived categories.**
4. **Fold scoring into the research call.** The schema becomes `{summary, key_facts[], score, score_rationale, confidence}`. That drops 15 calls and stops re-sending about 1.2k tokens of research to score each category. Rescoring is still possible by re-running the score step over stored `key_facts`.
5. **Shorter, structured evidence.** Replace "aim to stay under roughly 900 words" with a ~250-word summary plus 5–10 `key_facts` (each with an optional number and URL). Output is the biggest cost, and the stored research is mostly read through the scores, not in full.
6. **Rescore only when the evidence changed:** skip when `score.research_id` already equals the current research id. The same rule applies to synthesis: regenerate only when a score changed.
7. **Make prompts cache-friendly.**
   - Fixed order: system instructions → profile brief → location block → category-specific instructions.
   - Nothing that changes (dates, category name) goes near the top.
   - Check `usage.input_tokens_details.cached_tokens` in `llm_calls`.
8. **Use a short profile brief instead of the full profile.**
   - Build a ~1k-char brief once per run: must-haves, deal-breakers, climate and water-temperature thresholds, languages, interests, family locations.
   - Add the finance section only for cost of living and tax, and the health section only for healthcare.
   - This also stops sending pension and asset figures in every call.
9. **Route by task.**
   - Set `reasoning={"effort": ...}` per route: low for synthesis, medium for research.
   - Use a smaller model for synthesis.
   - On a length error, raise `max_output_tokens` before retrying instead of resending the same request, and record `finish_reason`.
10. **Bulk jobs at the discounted rate.** Backfills and full rescoring can use the Batch API, or `service_tier="flex"` on ordinary calls; both are about half price in exchange for slower turnaround. Check current pricing for your model.

### 4d. Rollout
- Run v1 and v2 side by side on 5 varied locations (e.g. Valencia, Lima, Dauin, Rincón, Fremantle). Compare tokens, cost, score differences and citation quality.
- Bump `prompt_version`. Old evidence stays as history under the legacy run.
- Then backfill all 45 countries (country research) and all 129 locations (location research) as batch or flex jobs.

---

## Phase 5 — Markdown and cleanup (½–1 day) — ✅ implemented 2026-10-23 (migration `0007_location_slug_admin1`)

Backfill status when Phase 5 started: 60 locations on v2, all completed with no failed runs. Average per location: ~56k input tokens (~37% cached), ~10k output, ~9 web searches.

- **Slugs.** `locations.slug` is unique and accent-folded (`rincon-puerto-rico`, `alcala-spain`, `itacare-brazil`). It's built from the name plus the jurisdiction name in `countries`, so Puerto Rico places no longer end in `-usa` or `-us-territories`. A `before_flush` hook sets it for new locations and on rename. Collisions get the region, then a number, appended. `resolve_location` (CLI) also accepts a slug.
- **Markdown.** The exporter moved into `relocation.export_markdown`. The pipeline calls it in-process after a full run, and a failed export never fails the run. It reads scores through `effective_scores()` and names files `research/<slug>.md`. `scripts/export_research_markdown.py` takes ids, names or slugs, plus `--all` and `--prune [--dry-run]`.
  - `research/` now has exactly one file per location (129).
  - 24 duplicate or old-name files were removed. They are still in git history.
  - 8 files for places no longer in the database (Dubrovnik, El Cuyo, Osa Peninsula, Puerto Ángel, Punta Uva, Sail Rock, Santa Cruz, Sarandë) moved to `research/archive/`, which `--prune` ignores.
- **Region.**
  - `locations.admin1` is the geocoder's state/province. It is saved when a location is added from a geocoder match, shown in the research prompt when it adds something beyond `region`, and backfilled with `scripts/backfill_admin1.py [--dry-run]`. That script needs the network, so run it on the Mac.
  - `region` stays a free-text label. "Madiera" became "Madeira", "Yucután" became "Yucatán", and whitespace was trimmed.
- **Timestamps.** All `datetime` columns use a `UTCDateTime` type. They are stored as naive UTC, as before, so no data rewrite was needed, and they read back as aware UTC. The API now serialises them with `Z`, so browsers stop treating UTC as local time. Freshness ages are computed in UTC.
- **Enrichment.**
  - The ocean, swimming and beach logic moved from `scripts/` into `relocation.enrichment` (`ocean`, `swimming`, `beach`, `runner`). The scripts are now thin wrappers with the same flags.
  - New command: `relocation pipeline enrich [LOCATION...] [-s ocean|swimming|beach] [--refresh]`. By default it fetches only missing ocean data and beach scores.
  - Post-create enrichment runs in-process instead of starting three subprocesses. A failed ocean step skips swimming and beach.
- Not done (optional): trimming the Typer CRUD commands. They still work and nothing depends on removing them.

Still to run on the Mac (they need Open-Meteo or Overpass):
- `uv run relocation pipeline enrich "Las Galeras" Piscadera "San Carlos Nuevo Guaymas" "Terre-de-Haut"` fills ocean data and swim scores for the 4 locations without them.
- `uv run relocation pipeline enrich -s beach` retries the 5 beach fallbacks (Cartagena, Pipa, Icod de los vinos, Tecolutla, Amed), which still use the ocean-grid fallback.
- `uv run python scripts/backfill_admin1.py --dry-run`, then run it without `--dry-run`.

---

## Decisions needed

1. ~~**Territories.**~~ Decided 2026-10-22: PR is its own jurisdiction (done in Phase 2). Should Puerto Rico (and other US territories) be its own jurisdiction under the US, so tax (Act 60) can differ while visa stays "none"? Recommended: yes.
2. ~~**"Verified" flags.**~~ Decided 2026-10-22: reset (done in Phase 1). The 1,177 rows the model marked "verified" were never checked against live sources. Reset them to `needs_review`, or keep them with `verified_by='model-legacy'`? Recommended: reset.
3. ~~**Swim and beach scores.**~~ Decided 2026-10-22: recompute (done in Phase 3). Restoring the deterministic scores will change the rankings. OK to proceed, with a before/after snapshot?
4. **Superseded research.** Keep the 1,461 superseded rows as history (recommended; about 4.6M chars, small at this size) or delete them?
5. **`research/` markdown.** Generate it on demand and stop committing it, or keep committing it as a readable snapshot? *For now:* still committed, one file per location, regenerated after each full run. To stop committing it, add `research/*.md` to `.gitignore` and `git rm --cached` the files.
6. **Web search per category.** Proposed for cost, healthcare, travel, visa and tax. Add or remove any?
7. ~~**`provider` columns.**~~ Decided 2026-10-22: keep multi-provider (done in Phase 1). Was the multi-provider (Gemini) work abandoned? If so, Phase 1 drops the `provider` columns and `location_provider_states` and restores `UNIQUE(location_id, category_id)` on scores. If not, the models need to learn about `provider` before Phase 1.

---

## Estimated effort

| Phase | Effort |
|---|---|
| 0 Safety net and measurement | ½ day |
| 1 Provenance | 1–2 days |
| 2 Countries and category flags | 1–2 days |
| 3 People, derived, rankings | 1 day |
| 4 Pipeline v2 | 3–4 days |
| 5 Cleanup | ½–1 day |
