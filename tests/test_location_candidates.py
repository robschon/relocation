from relocation.services import location_candidates as service


class DummyClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_search_location_candidates_uses_fallback_provider_when_primary_has_no_region_match(monkeypatch):
    monkeypatch.setattr(service.httpx, "Client", lambda **kwargs: DummyClient())
    monkeypatch.setattr(
        service,
        "_fetch_open_meteo_candidates",
        lambda client, query: [  # noqa: ARG005
            {
                "name": "San Andrés",
                "display_name": "San Andrés, La Rioja, Spain",
                "country": "Spain",
                "admin1": "La Rioja",
                "admin2": "La Rioja",
                "admin3": "Lumbreras",
                "latitude": 42.09399,
                "longitude": -2.58458,
                "population": None,
                "feature_code": "PPL",
                "provider": "open-meteo",
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "_fetch_nominatim_candidates",
        lambda client, query: [  # noqa: ARG005
            {
                "name": "San Andres",
                "display_name": "San Andres, Santa Cruz de Tenerife, Canarias, Espana",
                "country": "Spain",
                "admin1": "Canary Islands",
                "admin2": "Santa Cruz de Tenerife",
                "admin3": "Santa Cruz de Tenerife",
                "latitude": 28.5033,
                "longitude": -16.1969,
                "population": None,
                "feature_code": "village",
                "provider": "nominatim",
            }
        ],
    )

    result = service.search_location_candidates(name="San Andrés", country="Spain", region="Tenerife")

    assert len(result["candidates"]) == 2
    assert any(candidate["provider"] == "nominatim" and candidate["region_match"] for candidate in result["candidates"])
    assert any("fallback results" in warning for warning in result["warnings"])


def test_search_location_candidates_warns_when_all_matches_conflict_with_region(monkeypatch):
    monkeypatch.setattr(service.httpx, "Client", lambda **kwargs: DummyClient())
    monkeypatch.setattr(
        service,
        "_fetch_open_meteo_candidates",
        lambda client, query: [  # noqa: ARG005
            {
                "name": "San Andrés",
                "display_name": "San Andrés, La Rioja, Spain",
                "country": "Spain",
                "admin1": "La Rioja",
                "admin2": "La Rioja",
                "admin3": "Lumbreras",
                "latitude": 42.09399,
                "longitude": -2.58458,
                "population": None,
                "feature_code": "PPL",
                "provider": "open-meteo",
            }
        ],
    )
    monkeypatch.setattr(service, "_fetch_nominatim_candidates", lambda client, query: [])  # noqa: ARG005

    result = service.search_location_candidates(name="San Andrés", country="Spain", region="Tenerife")

    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["region_match"] is False
    assert any("No candidates matched the requested region" in warning for warning in result["warnings"])
