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


class _DummyThread:
    calls: dict[str, object] = {}

    def __init__(self, *, target, args, daemon):
        _DummyThread.calls.update(target=target, args=args, daemon=daemon)

    def start(self):
        _DummyThread.calls["started"] = True


def _patch_job_launch(monkeypatch):

    from relocation.api.routers import full_research

    _DummyThread.calls = {}
    monkeypatch.setattr(full_research.threading, "Thread", _DummyThread)
    return _DummyThread.calls


def test_start_full_research_creates_queued_run(client, db_session, monkeypatch):
    from relocation.models import ResearchRun

    calls = _patch_job_launch(monkeypatch)
    loc_id = client.get("/api/v1/locations").json()[0]["id"]

    resp = client.post(f"/api/v1/locations/{loc_id}/full-research")

    assert resp.status_code == 202
    body = resp.json()
    assert body["location_id"] == loc_id
    assert body["status"] == "queued"
    run = db_session.get(ResearchRun, int(body["id"]))
    assert (run.kind, run.status, run.provider, run.prompt_version) == ("full", "queued", "openai", "v1")
    assert calls["args"] == (run.id, loc_id, False)
    assert calls["started"] is True


def test_start_full_research_rejects_duplicate_active_job(client, monkeypatch):
    _patch_job_launch(monkeypatch)
    loc_id = client.get("/api/v1/locations").json()[0]["id"]

    assert client.post(f"/api/v1/locations/{loc_id}/full-research").status_code == 202
    assert client.post(f"/api/v1/locations/{loc_id}/full-research").status_code == 409


def test_start_full_research_can_force_refresh(client, monkeypatch):
    calls = _patch_job_launch(monkeypatch)
    loc_id = client.get("/api/v1/locations").json()[0]["id"]

    resp = client.post(f"/api/v1/locations/{loc_id}/full-research?force_research=true")

    assert resp.status_code == 202
    assert calls["args"][1] == loc_id
    assert calls["args"][2] is True


def test_list_full_research_jobs_newest_first_without_legacy(client, db_session):
    from datetime import datetime

    from relocation.models import ResearchRun

    loc_id = client.get("/api/v1/locations").json()[0]["id"]
    db_session.add_all(
        [
            ResearchRun(kind="full", location_id=loc_id, status="completed", prompt_version="v1",
                        started_at=datetime(2026, 3, 11, 12, 0)),
            ResearchRun(kind="full", location_id=loc_id, status="running", prompt_version="v1",
                        started_at=datetime(2026, 3, 12, 12, 0)),
            ResearchRun(kind="full", location_id=loc_id, status="completed", prompt_version="legacy",
                        started_at=datetime(2026, 3, 13, 12, 0)),
            ResearchRun(kind="rescore", location_id=loc_id, status="completed", prompt_version="v1",
                        started_at=datetime(2026, 3, 14, 12, 0)),
        ]
    )
    db_session.commit()

    resp = client.get("/api/v1/full-research-jobs")

    assert resp.status_code == 200
    assert [job["status"] for job in resp.json()] == ["running", "completed"]
    assert client.get("/api/v1/full-research-jobs/not-a-number").status_code == 404


def test_full_research_job_runs_pipeline_in_process(db_session, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from relocation.api.routers import full_research
    from relocation.models import Location, ResearchRun
    from relocation.pipeline import runner
    from relocation.services.research_runs import create_run, finish_run

    TestSession = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(full_research, "SessionLocal", TestSession)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    seen = {}

    def fake_run_location(location_id, *, force, run_id, kind, log):
        seen.update(location_id=location_id, force=force, run_id=run_id, kind=kind)
        assert isinstance(log, runner.RunLog)
        log("[step] Research: Food scene")
        finish_run(TestSession, run_id, status="completed", step="completed")

    monkeypatch.setattr(full_research, "run_location", fake_run_location)
    location = db_session.query(Location).first()
    run = create_run(db_session, kind="full", location_id=location.id, status="queued")

    full_research._run_full_research_job(run.id, location.id, True)

    db_session.expire_all()
    finished = db_session.get(ResearchRun, run.id)
    assert finished.status == "completed"
    assert "[step] Research: Food scene" in finished.log_tail
    assert seen == {"location_id": location.id, "force": True, "run_id": run.id, "kind": "full"}


def test_full_research_job_without_api_key_fails_cleanly(db_session, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from relocation.api.routers import full_research
    from relocation.models import Location, ResearchRun
    from relocation.services.research_runs import create_run

    TestSession = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(full_research, "SessionLocal", TestSession)
    from relocation.settings import get_settings

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    monkeypatch.setattr(full_research, "_discover_env_var_from_zsh", lambda name: None)
    location = db_session.query(Location).first()
    run = create_run(db_session, kind="full", location_id=location.id, status="queued")

    full_research._run_full_research_job(run.id, location.id, False)

    db_session.expire_all()
    assert db_session.get(ResearchRun, run.id).status == "failed"


def test_mark_interrupted_runs(db_session):
    from relocation.models import ResearchRun
    from relocation.services.research_runs import mark_interrupted_runs

    db_session.add_all([ResearchRun(kind="full", status="running"), ResearchRun(kind="full", status="completed")])
    db_session.commit()

    assert mark_interrupted_runs(db_session) == 1
    statuses = sorted(r.status for r in db_session.query(ResearchRun).all())
    assert statuses == ["completed", "interrupted"]


def _first_ids(client):
    loc_id = client.get("/api/v1/locations").json()[0]["id"]
    cat_id = next(c["id"] for c in client.get("/api/v1/categories").json() if c["name"] == "Food scene")
    return loc_id, cat_id


def test_new_research_supersedes_previous_current_row(client):
    loc_id, cat_id = _first_ids(client)
    first = client.post("/api/v1/research", json={"location_id": loc_id, "category_id": cat_id, "content": "v1"}).json()
    second = client.post("/api/v1/research", json={"location_id": loc_id, "category_id": cat_id, "content": "v2"}).json()
    other = client.post(
        "/api/v1/research",
        json={"location_id": loc_id, "category_id": cat_id, "content": "gemini view", "provider": "gemini"},
    ).json()

    assert second["is_current"] and other["is_current"]
    current = client.get(f"/api/v1/research?location_id={loc_id}&category_id={cat_id}&current_only=true").json()
    assert sorted(r["content"] for r in current) == ["gemini view", "v2"]
    history = client.get(f"/api/v1/research?location_id={loc_id}&category_id={cat_id}&provider=openai").json()
    assert [r["content"] for r in history] == ["v2", "v1"]
    assert client.get(f"/api/v1/research/{first['id']}").json()["is_current"] is False


def test_deleting_current_research_promotes_previous(client):
    loc_id, cat_id = _first_ids(client)
    first = client.post("/api/v1/research", json={"location_id": loc_id, "category_id": cat_id, "content": "v1"}).json()
    second = client.post("/api/v1/research", json={"location_id": loc_id, "category_id": cat_id, "content": "v2"}).json()

    assert client.delete(f"/api/v1/research/{second['id']}").status_code == 204
    assert client.get(f"/api/v1/research/{first['id']}").json()["is_current"] is True


def test_scores_upsert_per_provider_and_track_method(client):
    loc_id, cat_id = _first_ids(client)
    research = client.post("/api/v1/research", json={"location_id": loc_id, "category_id": cat_id, "content": "x"}).json()

    llm = client.post(
        "/api/v1/scores",
        json={"location_id": loc_id, "category_id": cat_id, "score": 7, "method": "llm", "research_id": research["id"]},
    ).json()
    assert (llm["method"], llm["research_id"], llm["provider"]) == ("llm", research["id"], "openai")

    gemini = client.post(
        "/api/v1/scores",
        json={"location_id": loc_id, "category_id": cat_id, "score": 4, "provider": "gemini", "method": "llm"},
    ).json()
    assert gemini["id"] != llm["id"]

    # A slider edit with no method is a manual override of the openai score.
    manual = client.post("/api/v1/scores", json={"location_id": loc_id, "category_id": cat_id, "score": 9}).json()
    assert manual["id"] == llm["id"]
    assert (manual["score"], manual["method"], manual["research_id"]) == (9, "manual", None)

    only_gemini = client.get(f"/api/v1/locations/{loc_id}/scores?provider=gemini").json()
    assert [s["score"] for s in only_gemini] == [4]


def test_rankings_use_one_provider(client):
    loc_id, cat_id = _first_ids(client)
    client.post("/api/v1/scores", json={"location_id": loc_id, "category_id": cat_id, "score": 8})
    client.post("/api/v1/scores", json={"location_id": loc_id, "category_id": cat_id, "score": 2, "provider": "gemini"})

    def food_score(provider):
        rankings = client.get(f"/api/v1/rankings?provider={provider}").json()
        loc_name = client.get(f"/api/v1/locations/{loc_id}").json()["name"]
        row = next(r for r in rankings if r["location_name"] == loc_name)
        return next(d["score"] for d in row["details"] if d["category_name"] == "Food scene")

    assert food_score("openai") == 8
    assert food_score("gemini") == 2


# --- Phase 2: countries and country-scope categories ---


def _visa_category(client):
    return next(c for c in client.get("/api/v1/categories").json() if c["key"] == "visa")


def _two_peru_locations(client):
    lima = next(loc for loc in client.get("/api/v1/locations").json() if loc["name"] == "Lima")
    cusco = client.post("/api/v1/locations", json={"name": "Cusco", "country": "Peru"}).json()
    return lima, cusco


def _visa_research_payload(location_id, category_id, content):
    return {
        "location_id": location_id,
        "category_id": category_id,
        "content": content,
        "source": "Migraciones portal, checked 2026-10-22",
        "source_urls": ["https://www.gob.pe/migraciones"],
        "source_checked_at": "2026-10-22",
        "confidence": 0.7,
    }


def test_categories_expose_behaviour_flags(client):
    by_key = {c["key"]: c for c in client.get("/api/v1/categories").json()}
    assert by_key["visa"]["scope"] == "country" and by_key["visa"]["requires_citation"] is True
    assert by_key["tax"]["scope"] == "location" and by_key["tax"]["refresh_after_days"] == 90
    assert by_key["swimming"]["kind"] == "derived"


def test_visa_research_is_stored_per_country_and_shared(client):
    visa = _visa_category(client)
    lima, cusco = _two_peru_locations(client)

    created = client.post("/api/v1/research", json=_visa_research_payload(lima["id"], visa["id"], "Peru visas v1"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["location_id"], body["country_code"]) == (None, "PE")

    for loc in (lima, cusco):
        rows = client.get(f"/api/v1/research?location_id={loc['id']}&current_only=true").json()
        assert [r["content"] for r in rows if r["category_id"] == visa["id"]] == ["Peru visas v1"]

    # Researching again from the other town replaces the country's current row.
    client.post("/api/v1/research", json=_visa_research_payload(cusco["id"], visa["id"], "Peru visas v2"))
    current = client.get("/api/v1/research?country_code=PE&current_only=true").json()
    assert [r["content"] for r in current] == ["Peru visas v2"]


def test_visa_score_set_via_one_location_applies_to_country(client):
    visa = _visa_category(client)
    lima, cusco = _two_peru_locations(client)

    resp = client.post("/api/v1/scores", json={"location_id": lima["id"], "category_id": visa["id"], "score": 7})
    assert resp.status_code == 201, resp.text
    assert resp.json()["scope"] == "country" and resp.json()["country_code"] == "PE"

    cusco_scores = client.get(f"/api/v1/locations/{cusco['id']}/scores").json()
    assert [(s["score"], s["scope"]) for s in cusco_scores if s["category_id"] == visa["id"]] == [(7, "country")]

    client.post("/api/v1/scores", json={"country_code": "PE", "category_id": visa["id"], "score": 5})
    lima_scores = client.get(f"/api/v1/locations/{lima['id']}/scores").json()
    assert [s["score"] for s in lima_scores if s["category_id"] == visa["id"]] == [5]


def test_location_level_category_requires_location(client):
    food = next(c for c in client.get("/api/v1/categories").json() if c["key"] == "food")
    resp = client.post("/api/v1/scores", json={"country_code": "PE", "category_id": food["id"], "score": 5})
    assert resp.status_code == 422


def test_visa_research_requires_citations(client):
    visa = _visa_category(client)
    lima, _ = _two_peru_locations(client)
    resp = client.post(
        "/api/v1/research",
        json={"location_id": lima["id"], "category_id": visa["id"], "content": "x", "source": "general knowledge"},
    )
    assert resp.status_code == 422


def test_new_country_is_created_on_demand_and_unknown_rejected(client):
    resp = client.post("/api/v1/locations", json={"name": "Suva", "country": "Fiji"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["country_code"] == "FJ"
    assert {"code": "FJ", "name": "Fiji", "parent_code": None} in client.get("/api/v1/countries").json()

    pr = client.post("/api/v1/locations", json={"name": "San Juan", "country": "Puerto Rico"}).json()
    assert pr["country_code"] == "PR"
    countries = {c["code"]: c for c in client.get("/api/v1/countries").json()}
    assert countries["PR"]["parent_code"] == "US"

    assert client.post("/api/v1/locations", json={"name": "Atlantis", "country": "Atlantis"}).status_code == 422


def test_location_score_rows_for_country_categories_are_rejected(db_session):
    import pytest

    from relocation.models import Category, Location, Score

    visa = db_session.query(Category).filter_by(key="visa").one()
    lima = db_session.query(Location).filter_by(name="Lima").one()
    db_session.add(Score(location_id=lima.id, category_id=visa.id, score=5))
    with pytest.raises(ValueError, match="per country"):
        db_session.commit()
    db_session.rollback()


# --- Phase 3: named users, generic rankings, derived categories ---


def test_users_have_display_names(client):
    users = client.get("/api/v1/users").json()
    assert [(u["name"], u["display_name"]) for u in users] == [("partner_a", "Partner A"), ("partner_b", "Partner B")]


def test_rankings_are_keyed_by_user_id(client):
    users = client.get("/api/v1/users").json()
    loc_id, cat_id = _first_ids(client)
    client.post("/api/v1/scores", json={"location_id": loc_id, "category_id": cat_id, "score": 8})

    rankings = client.get("/api/v1/rankings").json()
    row = next(r for r in rankings if r["location_id"] == loc_id)
    assert set(row["user_scores"]) == {str(u["id"]) for u in users}
    assert row["scored_categories"] == 1 and 0 < row["coverage"] < 1
    detail = row["details"][0]
    assert set(detail["weights"]) == {str(u["id"]) for u in users}

    partner_a_view = client.get("/api/v1/rankings?user=partner_a").json()
    rob_id = str(users[0]["id"])
    rob_row = next(r for r in partner_a_view if r["location_id"] == loc_id)
    assert rob_row["overall_score"] == rob_row["user_scores"][rob_id]
    assert client.get("/api/v1/rankings?user=nobody").status_code == 404


def test_llm_scores_for_derived_categories_are_rejected(client):
    loc_id = client.get("/api/v1/locations").json()[0]["id"]
    swim = next(c for c in client.get("/api/v1/categories").json() if c["key"] == "swimming")
    resp = client.post(
        "/api/v1/scores", json={"location_id": loc_id, "category_id": swim["id"], "score": 5, "method": "llm"}
    )
    assert resp.status_code == 422
    # A manual override is allowed.
    ok = client.post("/api/v1/scores", json={"location_id": loc_id, "category_id": swim["id"], "score": 5})
    assert ok.status_code == 201
