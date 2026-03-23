def test_list_locations(client):
    resp = client.get("/api/v1/locations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    names = {loc["name"] for loc in data}
    assert "Lima" in names


def test_list_locations_fully_scored_only(client):
    locs = client.get("/api/v1/locations").json()
    cats = client.get("/api/v1/categories").json()
    lima_id = next(loc["id"] for loc in locs if loc["name"] == "Lima")
    fremantle_id = next(loc["id"] for loc in locs if loc["name"] == "Fremantle")

    for cat in cats:
        client.post("/api/v1/scores", json={
            "location_id": lima_id,
            "category_id": cat["id"],
            "score": 8,
        })

    client.post("/api/v1/scores", json={
        "location_id": fremantle_id,
        "category_id": cats[0]["id"],
        "score": 6,
    })

    resp = client.get("/api/v1/locations?fully_scored_only=true")
    assert resp.status_code == 200
    data = resp.json()
    assert [loc["name"] for loc in data] == ["Lima"]


def test_create_location(client):
    resp = client.post("/api/v1/locations", json={
        "name": "Lisbon",
        "country": "Portugal",
        "region": "Europe",
        "latitude": 38.7223,
        "longitude": -9.1393,
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Lisbon"
    assert resp.json()["country_code"] == "PT"
    assert resp.json()["full_research_ran_at"] is None

    resp = client.get("/api/v1/locations")
    assert len(resp.json()) == 5


def test_create_location_returns_409_for_duplicate(client):
    resp = client.post("/api/v1/locations", json={
        "name": "Lisbon",
        "country": "Portugal",
        "latitude": 38.7223,
        "longitude": -9.1393,
    })
    assert resp.status_code == 201

    dup = client.post("/api/v1/locations", json={
        "name": "Lisbon",
        "country": "Portugal",
        "latitude": 38.7223,
        "longitude": -9.1393,
    })
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"]


def test_create_location_normalizes_country_aliases(client):
    resp = client.post("/api/v1/locations", json={
        "name": "Santa Barbara",
        "country": "USA",
        "latitude": 34.4208,
        "longitude": -119.6982,
    })

    assert resp.status_code == 201
    assert resp.json()["country"] == "United States"
    assert resp.json()["country_code"] == "US"


def test_update_location_full_research_timestamp(client):
    loc_id = client.get("/api/v1/locations").json()[0]["id"]

    resp = client.put(
        f"/api/v1/locations/{loc_id}",
        json={"full_research_ran_at": "2026-03-12T10:30:00Z"},
    )

    assert resp.status_code == 200
    assert resp.json()["full_research_ran_at"].startswith("2026-03-12T10:30:00")


def test_create_location_triggers_enrichment_when_enabled(client, monkeypatch):
    from relocation.api.routers import locations as locations_router

    calls: list[int] = []

    def fake_pipeline(location_id: int) -> None:
        calls.append(location_id)

    monkeypatch.setenv("RELOCATION_AUTO_ENRICH_NEW_LOCATIONS", "1")
    monkeypatch.setattr(locations_router, "run_location_post_create_pipeline", fake_pipeline)

    resp = client.post("/api/v1/locations", json={
        "name": "Setubal",
        "country": "Portugal",
        "region": "Europe",
        "latitude": 38.5244,
        "longitude": -8.8882,
    })

    assert resp.status_code == 201
    assert calls == [resp.json()["id"]]


def test_create_location_without_coordinates_skips_enrichment(client, monkeypatch):
    from relocation.api.routers import locations as locations_router

    calls: list[int] = []

    def fake_pipeline(location_id: int) -> None:
        calls.append(location_id)

    monkeypatch.setenv("RELOCATION_AUTO_ENRICH_NEW_LOCATIONS", "1")
    monkeypatch.setattr(locations_router, "run_location_post_create_pipeline", fake_pipeline)

    resp = client.post("/api/v1/locations", json={
        "name": "Setubal",
        "country": "Portugal",
        "region": "Europe",
    })

    assert resp.status_code == 201
    assert calls == []


def test_location_candidates_endpoint(client, monkeypatch):
    from relocation.api.routers import locations as locations_router

    monkeypatch.setattr(
        locations_router,
        "search_location_candidates",
        lambda **kwargs: {
            "candidates": [
                {
                    "name": "San Andrés",
                    "display_name": "San Andrés, Santa Cruz de Tenerife, Canary Islands, Spain",
                    "country": "Spain",
                    "region": "Canary Islands",
                    "admin1": "Canary Islands",
                    "admin2": "Santa Cruz de Tenerife",
                    "admin3": "Santa Cruz de Tenerife",
                    "latitude": 28.5033,
                    "longitude": -16.1969,
                    "population": 1000,
                    "feature_code": "PPL",
                    "query": "San Andrés, Tenerife, Canary Islands, Spain",
                    "score": 165,
                    "provider": "open-meteo",
                    "region_match": True,
                }
            ],
            "warnings": [],
        },
    )

    resp = client.get("/api/v1/location-candidates?name=San%20Andr%C3%A9s&country=Spain&region=Tenerife")

    assert resp.status_code == 200
    assert resp.json()["candidates"][0]["display_name"].startswith("San Andrés")


def test_create_and_search_visa_normalizes_country_aliases(client):
    resp = client.post("/api/v1/visa", json={
        "country": "USA",
        "visa_type": "No visa required (U.S. citizen, domestic move)",
        "source_urls": ["https://example.com/usa-visa"],
        "source_checked_at": "2026-03-18",
        "verification_status": "verified",
        "confidence": 0.9,
    })

    assert resp.status_code == 201
    assert resp.json()["country"] == "United States"
    assert resp.json()["country_code"] == "US"

    search = client.get("/api/v1/visa?country=USA")
    assert search.status_code == 200
    assert any(entry["country_code"] == "US" for entry in search.json())


def test_list_categories(client):
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200
    assert len(resp.json()) == 15


def test_upsert_score(client):
    # Get a location and category
    locs = client.get("/api/v1/locations").json()
    cats = client.get("/api/v1/categories").json()
    loc_id = locs[0]["id"]
    cat_id = cats[0]["id"]

    # Create
    resp = client.post("/api/v1/scores", json={
        "location_id": loc_id,
        "category_id": cat_id,
        "score": 7,
        "notes": "initial",
    })
    assert resp.status_code == 201
    assert resp.json()["score"] == 7

    # Update (upsert)
    resp = client.post("/api/v1/scores", json={
        "location_id": loc_id,
        "category_id": cat_id,
        "score": 9,
        "notes": "updated",
    })
    assert resp.status_code == 201
    assert resp.json()["score"] == 9
    assert resp.json()["notes"] == "updated"


def test_upsert_score_allows_zero(client):
    locs = client.get("/api/v1/locations").json()
    cats = client.get("/api/v1/categories").json()
    loc_id = locs[0]["id"]
    cat_id = cats[0]["id"]

    resp = client.post("/api/v1/scores", json={
        "location_id": loc_id,
        "category_id": cat_id,
        "score": 0,
    })
    assert resp.status_code == 201
    assert resp.json()["score"] == 0


def test_rankings(client):
    # Set some scores first
    locs = client.get("/api/v1/locations").json()
    cats = client.get("/api/v1/categories").json()

    client.post("/api/v1/scores", json={
        "location_id": locs[0]["id"],
        "category_id": cats[0]["id"],
        "score": 8,
    })
    client.post("/api/v1/scores", json={
        "location_id": locs[1]["id"],
        "category_id": cats[0]["id"],
        "score": 5,
    })

    resp = client.get("/api/v1/rankings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    # First location should have highest score
    scored = [r for r in data if r["overall_score"] > 0]
    assert len(scored) == 2
    assert scored[0]["overall_score"] >= scored[1]["overall_score"]


def test_rankings_fully_scored_only(client):
    locs = client.get("/api/v1/locations").json()
    cats = client.get("/api/v1/categories").json()
    lima_id = next(loc["id"] for loc in locs if loc["name"] == "Lima")
    fremantle_id = next(loc["id"] for loc in locs if loc["name"] == "Fremantle")

    for cat in cats:
        client.post("/api/v1/scores", json={
            "location_id": lima_id,
            "category_id": cat["id"],
            "score": 7,
        })

    client.post("/api/v1/scores", json={
        "location_id": fremantle_id,
        "category_id": cats[0]["id"],
        "score": 9,
    })

    resp = client.get("/api/v1/rankings?fully_scored_only=true")
    assert resp.status_code == 200
    data = resp.json()
    assert [row["location_name"] for row in data] == ["Lima"]
    assert len(data[0]["details"]) == len(cats)


def test_users(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_pros_cons(client):
    locs = client.get("/api/v1/locations").json()
    loc_id = locs[0]["id"]

    resp = client.post("/api/v1/pros-cons", json={
        "location_id": loc_id,
        "type": "pro",
        "content": "Great weather",
    })
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/locations/{loc_id}/pros-cons")
    assert len(resp.json()) == 1
    assert resp.json()[0]["type"] == "pro"


def test_start_full_research_uses_location_id(client, monkeypatch):
    from pathlib import Path

    from relocation.api.routers import full_research

    full_research._jobs.clear()
    loc_id = client.get("/api/v1/locations").json()[0]["id"]
    calls: dict[str, object] = {}

    class DummyThread:
        def __init__(self, *, target, args, daemon):
            calls["target"] = target
            calls["args"] = args
            calls["daemon"] = daemon

        def start(self):
            calls["started"] = True

    monkeypatch.setattr(full_research, "FULL_RESEARCH_SCRIPT", Path(__file__))
    monkeypatch.setattr(full_research.threading, "Thread", DummyThread)

    resp = client.post(f"/api/v1/locations/{loc_id}/full-research")

    assert resp.status_code == 202
    assert resp.json()["location_id"] == loc_id
    assert calls["args"][1] == loc_id
    assert calls["args"][2] is False
    assert calls["started"] is True


def test_start_full_research_can_force_refresh(client, monkeypatch):
    from pathlib import Path

    from relocation.api.routers import full_research

    full_research._jobs.clear()
    loc_id = client.get("/api/v1/locations").json()[0]["id"]
    calls: dict[str, object] = {}

    class DummyThread:
        def __init__(self, *, target, args, daemon):
            calls["args"] = args

        def start(self):
            calls["started"] = True

    monkeypatch.setattr(full_research, "FULL_RESEARCH_SCRIPT", Path(__file__))
    monkeypatch.setattr(full_research.threading, "Thread", DummyThread)

    resp = client.post(f"/api/v1/locations/{loc_id}/full-research?force_research=true")

    assert resp.status_code == 202
    assert calls["args"][1] == loc_id
    assert calls["args"][2] is True
    assert calls["started"] is True


def test_list_full_research_jobs_returns_newest_first(client):
    from datetime import datetime, timezone

    from relocation.api.routers import full_research

    full_research._jobs.clear()
    older = full_research.FullResearchJobOut(
        id="older",
        location_id=1,
        location_name="Older",
        status="completed",
        started_at=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
        output=[],
    )
    newer = full_research.FullResearchJobOut(
        id="newer",
        location_id=2,
        location_name="Newer",
        status="running",
        started_at=datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc),
        output=[],
    )
    full_research._jobs[older.id] = older
    full_research._jobs[newer.id] = newer

    resp = client.get("/api/v1/full-research-jobs")

    assert resp.status_code == 200
    assert [job["id"] for job in resp.json()] == ["newer", "older"]


def test_build_full_research_cmd_includes_force_flag():
    from relocation.api.routers.full_research import _build_full_research_cmd

    cmd = _build_full_research_cmd(42, force_research=True)

    assert "--location-id" in cmd
    assert "42" in cmd
    assert cmd[-1] == "--force-research"


def test_full_research_error_derivation_uses_last_error_line():
    from relocation.api.routers.full_research import _derive_job_error

    output = [
        "[step] Research categories",
        "  [error] Tax implications: missing dated citations",
        "[failures]",
    ]

    assert _derive_job_error(output, 1) == "Tax implications: missing dated citations"
