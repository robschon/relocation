# Adding a New Location Candidate

Step-by-step playbook for adding a new relocation candidate to the project.

## Prerequisites

- Database initialized (`uv run relocation init`)
- For API-backed flows and AI research scripts: backend running (`uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000`)
- For OpenAI research scripts: `OPENAI_API_KEY` set

## Steps

### 1. Confirm the exact place first

The current workflow is moving toward exact-place disambiguation before creation. Prefer confirming the exact candidate and coordinates before adding a new location.

Recommended options:

- Frontend: use the add-location flow and click `Find Matches`
- API: call `GET /api/v1/location-candidates`

Example:

```bash
curl -sS "http://127.0.0.1:8000/api/v1/location-candidates?name=Cascais&country=Portugal&region=Lisbon%20Metropolitan%20Area"
```

What to confirm before creating the record:

- `display_name` matches the intended place
- `latitude` and `longitude` are correct
- `region` is right, especially for ambiguous same-name places

Notes:

- Creating a duplicate location now returns `409 Conflict`.
- Automatic post-create enrichment only runs when the location has confirmed coordinates.

### 2. Create the location record

Recommended: create the location through the frontend or API so you can include confirmed coordinates up front.

API example:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cascais",
    "country": "Portugal",
    "region": "Lisbon Metropolitan Area",
    "latitude": 38.6979,
    "longitude": -9.4215,
    "population": 214000,
    "description": "Affluent coastal town west of Lisbon with beaches, historic center, and excellent rail connection to the capital"
  }'
```

Legacy CLI path:

```bash
uv run relocation location add "<City>" "<Country>" \
  --region "<Region>" \
  --population <number> \
  --desc "<One-line description>"
```

Example:
```bash
uv run relocation location add "Cascais" "Portugal" \
  --region "Lisbon Metropolitan Area" \
  --population 214000 \
  --desc "Affluent coastal town west of Lisbon with beaches, historic center, and excellent rail connection to the capital"
```

CLI caveat:

- `relocation location add` does not currently accept `latitude` or `longitude`
- If you create a location without coordinates, the backend accepts it, but automatic enrichment is skipped until coordinates are added later

### 3. Write the research file

Create `research/<city>-<country>.md` following the established template. Use any existing file as reference (e.g., `research/funchal-madeira-portugal.md`).

#### Required structure

```markdown
# <City>, <Region> (<Country>) — Relocation Research

**Research date**: <Month Year>
**Data sources**: <Description of sources and live web research date>
**Exchange rate**: <Rate used, with date>

---

## Summary Scores

| Category | Score | Key Factor |
|----------|-------|------------|
| Cost of living / housing | X/10 | ... |
| Climate / weather | X/10 | ... |
| Healthcare quality & access | X/10 | ... |
| Visa / residency feasibility | X/10 | ... |
| Tax implications | X/10 | ... |
| Safety / stability / values | X/10 | ... |
| Language & community | X/10 | ... |
| Walkability / public transit | X/10 | ... |
| Cultural amenities / lifestyle | X/10 | ... |
| Travel connectivity & proximity to family/friends | X/10 | ... |
| Food scene | X/10 | ... |
| Natural beauty / outdoor recreation | X/10 | ... |
| Environmental quality & climate risk | X/10 | ... |

---

## 1. Cost of Living & Housing
### Property Market
| Metric | Value |
|--------|-------|
| Avg price per m² | ... |
| ... | ... |

### Cost of Living (Monthly, couple)
| Category | Monthly (local/USD) |
|----------|---------------------|
| Rent (1-bed city center) | ... |
| ... | ... |
| **Total (renting)** | **...** |

<Narrative with cross-location comparisons>

**Score: X/10.** <Justification with comparisons to other locations>

---

## 2. Climate & Weather
<Bullet points: type, summer, winter, avg temp, rainfall, humidity, ocean, sunshine, extreme weather>

**Score: X/10.** <Justification>

---

## 3. Healthcare Quality & Access
<Key hospitals/clinics, country ranking, insurance options, limitations>

**Score: X/10.** <Justification>

---

## 4. Visa & Residency Feasibility
### <Primary Visa Type>
| Requirement | Detail |
|-------------|--------|
| ... | ... |

**Score: X/10.** <Justification>

---

## 5. Tax Implications
<Income tax, property tax, US tax obligations, treaties, special regimes>

**Score: X/10.** <Justification>

---

## 6. Safety / Stability / Values
<Crime rates, political stability, LGBTQ+ rights, progressiveness, diversity/pluralism>

**Score: X/10.** <Justification>

---

## 7. Language & Community
<Language requirements, expat community size, English prevalence, social integration>

**Score: X/10.** <Justification>

---

## 8. Walkability & Public Transit
<Walk score, transit options, bike infrastructure, car necessity>

**Score: X/10.** <Justification>

---

## 9. Cultural Amenities & Lifestyle
<Museums, theaters, music, nightlife, festivals, community activities>

**Score: X/10.** <Justification>

---

## 10. Travel Connectivity & Proximity to Family/Friends
<Airport access, direct flights to US, travel time, timezone difference>

**Score: X/10.** <Justification>

---

## 11. Food Scene
<Restaurant quality/variety, markets, local cuisine, dietary options>

**Score: X/10.** <Justification>

---

## 12. Natural Beauty & Outdoor Recreation
<Scenery, parks, beaches, hiking, diving, nature access>

**Score: X/10.** <Justification>

---

## 13. Environmental Quality & Climate Risk
<Air quality (AQI), drinking water safety, pollution, climate change risks (sea level rise, drought, extreme weather), environmental regulations>

**Score: X/10.** <Justification>

---

## Key Strategic Recommendations

> **<One-sentence summary of the location's value proposition>**

### The Unique Value Proposition
1. ...
2. ...

### If Considering
1. ...
2. ...

---

## Verification Status

### Verified via Live Web Research (<Date>)
- [x] <Fact checked>
- [x] <Fact checked>
```

#### Key conventions
- Every deep-dive section ends with a bold `**Score: X/10.**` line with justification
- Include cross-location comparisons (e.g., "below Valencia's 9/10 but above Lima's 5/10")
- Property and cost tables use local currency with USD equivalent
- Visa sections use requirement/detail tables

### 4. Score all 13 categories in the database

Enter scores using the CLI. Each score needs the location name, a category name (partial match works), a score 1-10, and notes:

```bash
uv run relocation score set "<City>" "Cost" <score> --notes "<brief justification>"
uv run relocation score set "<City>" "Climate / weather" <score> --notes "..."
uv run relocation score set "<City>" "Healthcare" <score> --notes "..."
uv run relocation score set "<City>" "Visa" <score> --notes "..."
uv run relocation score set "<City>" "Tax" <score> --notes "..."
uv run relocation score set "<City>" "Safety" <score> --notes "..."
uv run relocation score set "<City>" "Language" <score> --notes "..."
uv run relocation score set "<City>" "Walkability" <score> --notes "..."
uv run relocation score set "<City>" "Cultural" <score> --notes "..."
uv run relocation score set "<City>" "Travel" <score> --notes "..."
uv run relocation score set "<City>" "Food" <score> --notes "..."
uv run relocation score set "<City>" "Natural beauty" <score> --notes "..."
uv run relocation score set "<City>" "Environmental" <score> --notes "..."
```

**Note**: Use `"Climate / weather"` (not just `"Climate"`) and `"Natural beauty"` (not just `"Natural"`) to avoid ambiguous matches with the Environmental category.

### 5. Add research notes to the database

Insert a concise summary of each category's research into the `research` table. Each entry should be a dense paragraph of key facts, data points, and comparisons, essentially a compressed version of the research file section.

```sql
INSERT INTO research (
  location_id,
  category_id,
  content,
  source,
  source_date,
  source_checked_at,
  verification_status,
  confidence,
  created_at
)
VALUES (
  <loc_id>,
  <cat_id>,
  '<concise research summary>',
  '<sources>',
  '<published_date_or_null>',
  '<checked_date_or_null>',
  'needs_review',
  NULL,
  datetime('now')
);
```

- One entry per category (13 total)
- Content should be ~1-3 sentences of key facts with numbers
- Include source attribution
- Use `source_date` for when the source was published, if known
- Use `source_checked_at` for when you verified it
- Visa/tax research should include verification metadata when possible because the API enforces stricter evidence rules there

### 6. Add pros and cons

Insert pros and cons into the `pros_cons` table, each tied to a specific category. Aim for ~8 pros and ~8 cons per location.

```sql
INSERT INTO pros_cons (location_id, category_id, type, content, created_at)
VALUES (<loc_id>, <cat_id>, 'pro', '<concise pro statement>', datetime('now'));
```

Guidelines:
- Each pro/con is tied to one category via `category_id`
- `type` must be `'pro'` or `'con'`
- Content should be a single compelling sentence with key data points
- Pros: highlight the location's strongest selling points with specifics
- Cons: flag genuine weaknesses, risks, or trade-offs honestly
- A category can have multiple pros or cons if warranted
- Cross-reference other locations where useful (e.g., "20-30% higher than Funchal")

### 7. (Optional) Run AI research script

Populates the `research` and `visa_info` tables with AI-generated structured data, and also writes a bespoke one-sentence location description to `locations.description`. Requires the backend API to be running.

```bash
# Start the backend API (in another terminal)
uv run uvicorn relocation.api.app:app --host 127.0.0.1 --port 8000

# Use OpenAI script (requires OPENAI_API_KEY)
# Run research for all categories
uv run python scripts/research_location_openai.py "<City>"

# Re-research all categories (even if already populated)
uv run python scripts/research_location_openai.py "<City>" --force

# Research a single category
uv run python scripts/research_location_openai.py "<City>" --category "Cost"

# Skip bespoke description generation
uv run python scripts/research_location_openai.py "<City>" --skip-description

# Overwrite an existing description with a new bespoke one
uv run python scripts/research_location_openai.py "<City>" --force-description

# Optional: Claude version (requires ANTHROPIC_API_KEY)
uv run python scripts/research_location.py "<City>"
uv run python scripts/research_location.py "<City>" --skip-description
uv run python scripts/research_location.py "<City>" --force-description
```

What changed in the current generation flow:

- Research prompts are now more location-specific and may use region plus confirmed coordinates to avoid drifting to the wrong place
- Re-generated entries may come back with `needs_review` verification status until manually checked
- Slugs and exported research filenames for accented place names may still look rough, so verify the generated markdown path before linking it elsewhere

### 8. Bespoke description quality check

After script run, sanity-check the card copy in DB:

```bash
sqlite3 data/relocation.db "SELECT description FROM locations WHERE name = '<City>';"
```

Quality bar:
- One sentence, ~28-42 words
- Glossy travel-mag voice with concrete place cues
- No numeric score notation (no `X/10`)
- Sounds distinct from other locations (not formulaic)

### 9. Verify

```bash
# Location details and all scores
uv run relocation location show "<City>"

# Confirm coordinates are present
sqlite3 data/relocation.db "SELECT latitude, longitude FROM locations WHERE name = '<City>';"

# Full ranking with new location included
uv run relocation rank

# Score matrix — new location should have all 13 columns filled
uv run relocation score matrix

# Weight matrix — should still show 13 categories for both users
uv run relocation weight matrix

# Research entries — should be 13 (one per category)
sqlite3 data/relocation.db "SELECT COUNT(*) FROM research WHERE location_id = (SELECT id FROM locations WHERE name = '<City>');"

# Pros/cons — should be ~16 (roughly 8 pros + 8 cons)
sqlite3 data/relocation.db "SELECT type, COUNT(*) FROM pros_cons WHERE location_id = (SELECT id FROM locations WHERE name = '<City>') GROUP BY type;"

# Description exists and is non-empty
sqlite3 data/relocation.db "SELECT COUNT(*) FROM locations WHERE name = '<City>' AND description IS NOT NULL AND trim(description) <> '';"
```

## The 13 Scoring Categories

| # | Category | What it covers |
|---|----------|----------------|
| 1 | Cost of living / housing | Rent/purchase, groceries, utilities, dining affordability |
| 2 | Climate / weather | Temperature, seasons, humidity, day-to-day weather |
| 3 | Healthcare quality & access | Hospitals, specialists, insurance, costs |
| 4 | Visa / residency feasibility | Legal residency paths, requirements, timeline |
| 5 | Tax implications | Income/property/estate tax, US obligations, treaties |
| 6 | Safety / stability / values | Crime, political stability, LGBTQ+ rights, progressiveness, diversity |
| 7 | Language & community | Language accessibility, expat community, English prevalence, social integration |
| 8 | Walkability / public transit | Car-free living, transit quality, bike infrastructure |
| 9 | Cultural amenities / lifestyle | Museums, theaters, music, nightlife, community activities |
| 10 | Travel connectivity & proximity to family/friends | Airport access, US flights, travel time/cost |
| 11 | Food scene | Restaurants, markets, local cuisine, dietary accommodation |
| 12 | Natural beauty / outdoor recreation | Scenery, parks, beaches, hiking, nature |
| 13 | Environmental quality & climate risk | Air quality, water safety, pollution, climate change vulnerability |

## Scoring Guidelines

- **10**: World-class / best possible for this category
- **8-9**: Excellent, among the best of our candidates
- **6-7**: Good, meets needs with some limitations
- **4-5**: Adequate but notable weaknesses
- **2-3**: Poor, significant concerns
- **1**: Dealbreaker-level weakness

Always justify scores relative to other locations already researched. The research files serve as the ground truth for scoring decisions.
