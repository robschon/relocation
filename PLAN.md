# Relocation Planning Tool — Implementation Plan

## Overview

A web app + CLI + Google Sheets sync for tracking and comparing potential international retirement destinations. Two fixed users (husband and wife) who each weight scoring categories independently. SQLite database, Python backend, local hosting.

## Architecture

- **Database**: SQLite
- **Backend**: Python / FastAPI
- **CLI**: Typer
- **Frontend**: TBD in Phase 2 (React or similar)
- **Google Sheets**: Phase 3

## Project Structure

```
$HOME/Code/relocation/
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── src/
│   └── relocation/
│       ├── __init__.py
│       ├── config.py              # Settings (DB path, etc.)
│       ├── database.py            # Engine, session factory, Base
│       ├── models.py              # SQLAlchemy ORM models
│       ├── schemas.py             # Pydantic schemas for API
│       ├── seed.py                # Seed data
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py             # FastAPI app factory
│       │   └── routers/
│       │       ├── __init__.py
│       │       ├── locations.py
│       │       ├── categories.py
│       │       ├── scores.py
│       │       ├── weights.py
│       │       ├── research.py
│       │       ├── pros_cons.py
│       │       ├── visa.py
│       │       ├── profile.py
│       │       └── rankings.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py            # Typer app entry point
│       │   ├── locations.py
│       │   ├── categories.py
│       │   ├── scores.py
│       │   ├── weights.py
│       │   ├── research.py
│       │   ├── pros_cons.py
│       │   ├── visa.py
│       │   ├── profile.py
│       │   └── rank.py
│       ├── profile_builder/
│       │   ├── __init__.py
│       │   ├── questions.py       # Question definitions
│       │   ├── builder.py         # Interactive questionnaire
│       │   └── formatter.py       # Markdown export
│       └── services/
│           ├── __init__.py
│           └── ranking.py         # Weighted score calculation
├── data/
│   └── relocation.db              # SQLite (created at runtime)
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_models.py
    ├── test_api.py
    ├── test_cli.py
    └── test_ranking.py
```

## Database Schema

### Tables

#### `users`
| Column     | Type         | Constraints           |
|------------|-------------|-----------------------|
| id         | INTEGER      | PK, autoincrement     |
| name       | VARCHAR(50)  | NOT NULL, UNIQUE      |
| created_at | DATETIME     | NOT NULL, default=now |

Seeded with: `husband`, `wife`

#### `locations`
| Column      | Type          | Constraints                          |
|-------------|--------------|--------------------------------------|
| id          | INTEGER       | PK, autoincrement                    |
| name        | VARCHAR(200)  | NOT NULL                             |
| country     | VARCHAR(100)  | NOT NULL                             |
| region      | VARCHAR(100)  | nullable                             |
| population  | INTEGER       | nullable                             |
| description | TEXT          | nullable                             |
| notes       | TEXT          | nullable                             |
| created_at  | DATETIME      | NOT NULL, default=now                |
| updated_at  | DATETIME      | NOT NULL, default=now, onupdate=now  |

UNIQUE on `(name, country)`

#### `categories`
| Column      | Type          | Constraints           |
|-------------|-------------|-----------------------|
| id          | INTEGER       | PK, autoincrement     |
| name        | VARCHAR(200)  | NOT NULL, UNIQUE      |
| description | TEXT          | nullable              |
| sort_order  | INTEGER       | NOT NULL, default=0   |
| created_at  | DATETIME      | NOT NULL, default=now |

Seeded with 13 categories (see below)

#### `scores`
| Column      | Type    | Constraints                              |
|-------------|---------|------------------------------------------|
| id          | INTEGER | PK, autoincrement                        |
| location_id | INTEGER | FK -> locations.id, NOT NULL             |
| category_id | INTEGER | FK -> categories.id, NOT NULL            |
| score       | INTEGER | NOT NULL, CHECK(1 <= score <= 10)        |
| notes       | TEXT    | nullable                                 |
| created_at  | DATETIME | NOT NULL, default=now                   |
| updated_at  | DATETIME | NOT NULL, default=now, onupdate=now     |

UNIQUE on `(location_id, category_id)`. One score per location per category (objective). User preferences expressed via weights.

#### `weights`
| Column      | Type    | Constraints                              |
|-------------|---------|------------------------------------------|
| id          | INTEGER | PK, autoincrement                        |
| user_id     | INTEGER | FK -> users.id, NOT NULL                 |
| category_id | INTEGER | FK -> categories.id, NOT NULL            |
| weight      | FLOAT   | NOT NULL, CHECK(weight >= 0)             |
| created_at  | DATETIME | NOT NULL, default=now                   |
| updated_at  | DATETIME | NOT NULL, default=now, onupdate=now     |

UNIQUE on `(user_id, category_id)`. Scale 1-10 (0 = "don't care").

#### `research`
| Column      | Type          | Constraints                    |
|-------------|--------------|--------------------------------|
| id          | INTEGER       | PK, autoincrement              |
| location_id | INTEGER       | FK -> locations.id, NOT NULL   |
| category_id | INTEGER       | FK -> categories.id, nullable  |
| content     | TEXT          | NOT NULL                       |
| source      | VARCHAR(500)  | nullable                       |
| source_date | DATE          | nullable                       |
| created_at  | DATETIME      | NOT NULL, default=now          |

Multiple entries per location/category expected.

#### `pros_cons`
| Column      | Type        | Constraints                              |
|-------------|-------------|------------------------------------------|
| id          | INTEGER     | PK, autoincrement                        |
| location_id | INTEGER     | FK -> locations.id, NOT NULL             |
| category_id | INTEGER     | FK -> categories.id, nullable            |
| type        | VARCHAR(4)  | NOT NULL, CHECK(type IN ('pro', 'con'))  |
| content     | TEXT        | NOT NULL                                 |
| created_at  | DATETIME    | NOT NULL, default=now                    |

#### `visa_info`
| Column            | Type          | Constraints                          |
|-------------------|--------------|--------------------------------------|
| id                | INTEGER       | PK, autoincrement                    |
| country           | VARCHAR(100)  | NOT NULL                             |
| visa_type         | VARCHAR(200)  | NOT NULL                             |
| description       | TEXT          | nullable                             |
| residency_pathway | TEXT          | nullable                             |
| requirements      | TEXT          | nullable                             |
| timeline          | VARCHAR(200)  | nullable                             |
| cost              | VARCHAR(200)  | nullable                             |
| notes             | TEXT          | nullable                             |
| created_at        | DATETIME      | NOT NULL, default=now                |
| updated_at        | DATETIME      | NOT NULL, default=now, onupdate=now  |

Keyed by `country` string (not FK to locations — visa rules are country-level).

#### `profile_responses`
| Column       | Type          | Constraints                          |
|--------------|--------------|--------------------------------------|
| id           | INTEGER       | PK, autoincrement                    |
| section      | VARCHAR(100)  | NOT NULL                             |
| question_key | VARCHAR(100)  | NOT NULL, UNIQUE                     |
| question     | TEXT          | NOT NULL                             |
| answer       | TEXT          | nullable                             |
| created_at   | DATETIME      | NOT NULL, default=now                |
| updated_at   | DATETIME      | NOT NULL, default=now, onupdate=now  |

Key-value store for profile questionnaire responses.

## Seed Data

### 13 Scoring Categories
1. Cost of living / housing
2. Climate / weather
3. Healthcare quality & access
4. Visa / residency feasibility
5. Tax implications (income, property, estate)
6. Safety / stability
7. Language / cultural accessibility
8. Walkability / public transit
9. Cultural amenities / lifestyle
10. Travel connectivity & proximity to family/friends
11. Food scene
12. Natural beauty / outdoor recreation
13. Expat community / English prevalence

### 4 Seed Locations
- **Osa Peninsula**, Costa Rica — Remote, biodiverse Pacific coast region
- **Fremantle**, Western Australia (~30k pop) — Historic port city near Perth with strong arts scene
- **Baja Peninsula**, Mexico — Desert peninsula, popular with US expats
- **Lima**, Peru (~10M pop) — Capital city, world-renowned food scene

### Default Weights
All categories seeded at weight=5 (neutral) for both users.

## API Endpoints

Base: `http://localhost:8000/api/v1`

- **Locations**: GET/POST/PUT/DELETE `/locations`, GET `/locations/{id}`
- **Categories**: GET/POST/PUT `/categories`, GET `/categories/{id}`
- **Scores**: GET/POST/PUT `/scores`, GET `/locations/{id}/scores` (POST uses upsert)
- **Weights**: GET/POST/PUT `/weights`, GET `/users/{name}/weights` (POST uses upsert)
- **Research**: GET/POST/PUT/DELETE `/research`
- **Pros/Cons**: GET/POST/DELETE `/pros-cons`, GET `/locations/{id}/pros-cons`
- **Visa**: GET/POST/PUT/DELETE `/visa`
- **Profile**: GET/POST `/profile`, GET `/profile/export` (markdown)
- **Rankings**: GET `/rankings?user=husband|wife|combined`
- **Users**: GET `/users`

## CLI Commands

```
relocation init                           # Initialize DB + seed data
relocation location list|add|show|remove
relocation category list
relocation score set|list|matrix
relocation weight set|list|matrix
relocation research add|list|show|remove
relocation pro add / con add
relocation pros-cons list
relocation visa add|list|show
relocation profile build|show|export
relocation rank [--user husband|wife] [--detailed]
```

CLI uses fuzzy substring matching for location and category names.

## Ranking Algorithm

For each location:
1. Get all scores (location_id, category_id, score)
2. Get weights for specified user (or average both users' weights for "combined")
3. `weighted_score = sum(score_i * weight_i) / sum(weight_i)`
4. Sort descending

Missing scores are skipped. Missing weights default to 5.

## Profile Builder

Interactive questionnaire covering:
- **Demographics**: ages, health, pets
- **Financial**: monthly budget, housing budget, income sources, tax situation
- **Languages & Culture**: languages spoken, cultural preferences, international experience
- **Lifestyle**: interests/hobbies, daily routine, food preferences, exercise
- **Requirements**: must-haves, deal-breakers, climate preference, healthcare needs
- **Connections**: family locations, friend locations, visit frequency, remote work needs
- **Other**: timeline, trial period openness, additional notes

Exports as a formatted markdown document for use as Claude research context.

## Implementation Order

1. **Project scaffolding**: uv init, dependencies, directory structure, config, .gitignore, git init
2. **Database models**: database.py + models.py (all 8 ORM models)
3. **Seed data + init command**: seed.py + `relocation init`
4. **Core CLI**: location, category, score, weight, research, pros/cons, visa commands
5. **Ranking service + rank CLI**: ranking algorithm, `relocation rank`
6. **Profile builder**: questions, interactive builder, markdown export
7. **FastAPI backend**: Pydantic schemas, app factory, all routers
8. **Tests**: fixtures, model tests, API tests, ranking tests

## Verification

After implementation, this sequence should work:

```bash
uv run relocation init
uv run relocation location list
uv run relocation category list
uv run relocation weight set husband "cost of living" 8
uv run relocation score set osa "cost of living" 7 --notes "Very affordable"
uv run relocation rank --detailed
uv run relocation profile build
uv run relocation profile export
uv run uvicorn relocation.api.app:app --reload
curl http://localhost:8000/api/v1/locations
uv run pytest -v
```
