def _category_id(client, name: str) -> int:
    categories = client.get("/api/v1/categories").json()
    for category in categories:
        if category["name"] == name:
            return category["id"]
    raise AssertionError(f"Missing category {name}")


def _location_id(client) -> int:
    locations = client.get("/api/v1/locations").json()
    return locations[0]["id"]


def test_tax_research_rejects_general_knowledge(client):
    resp = client.post(
        "/api/v1/research",
        json={
            "location_id": _location_id(client),
            "category_id": _category_id(client, "Tax implications"),
            "content": "Tax summary",
            "source": "General knowledge as of 2024",
            "source_urls": ["https://example.gov/tax"],
            "source_checked_at": "2026-03-06",
            "verification_status": "verified",
            "confidence": 0.8,
        },
    )
    assert resp.status_code == 422


def test_tax_research_requires_citations(client):
    resp = client.post(
        "/api/v1/research",
        json={
            "location_id": _location_id(client),
            "category_id": _category_id(client, "Tax implications"),
            "content": "Tax summary",
            "source": "Government tax publication cross-checked March 2026",
            "verification_status": "verified",
            "confidence": 0.8,
        },
    )
    assert resp.status_code == 422


def test_tax_research_accepts_verified_payload(client):
    resp = client.post(
        "/api/v1/research",
        json={
            "location_id": _location_id(client),
            "category_id": _category_id(client, "Tax implications"),
            "content": "Tax summary",
            "source": "Government tax publication cross-checked March 2026",
            "source_urls": ["https://example.gov/tax"],
            "source_checked_at": "2026-03-06",
            "source_published_at": "2026-01-01",
            "verification_status": "verified",
            "confidence": 0.82,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["verification_status"] == "verified"
    assert body["source_urls"] == ["https://example.gov/tax"]


def test_visa_requires_source_urls(client):
    resp = client.post(
        "/api/v1/visa",
        json={
            "country": "Portugal",
            "visa_type": "D7",
            "verification_status": "needs_review",
            "source_checked_at": "2026-03-06",
        },
    )
    assert resp.status_code == 422


def test_visa_accepts_verified_payload(client):
    resp = client.post(
        "/api/v1/visa",
        json={
            "country": "Portugal",
            "visa_type": "D7",
            "source_urls": ["https://example.gov/visa"],
            "source_checked_at": "2026-03-06",
            "source_published_at": "2026-02-10",
            "verification_status": "verified",
            "confidence": 0.74,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["verification_status"] == "verified"
    assert body["source_checked_at"] == "2026-03-06"
