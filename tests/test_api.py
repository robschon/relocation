def test_list_locations(client):
    resp = client.get("/api/v1/locations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    names = {loc["name"] for loc in data}
    assert "Lima" in names


def test_create_location(client):
    resp = client.post("/api/v1/locations", json={
        "name": "Lisbon",
        "country": "Portugal",
        "region": "Europe",
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Lisbon"

    resp = client.get("/api/v1/locations")
    assert len(resp.json()) == 5


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
    })

    assert resp.status_code == 201
    assert calls == [resp.json()["id"]]


def test_list_categories(client):
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200
    assert len(resp.json()) == 14


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
