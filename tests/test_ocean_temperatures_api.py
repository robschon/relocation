from datetime import date

from relocation.models import OceanTemperatureMonthly


def test_location_ocean_temperatures_empty(client):
    locations = client.get("/api/v1/locations").json()
    loc_id = locations[0]["id"]

    resp = client.get(f"/api/v1/locations/{loc_id}/ocean-temperatures")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_ocean_temperatures_with_filters(client, db_session):
    locations = client.get("/api/v1/locations").json()
    first_loc = locations[0]["id"]
    second_loc = locations[1]["id"]

    db_session.add_all(
        [
            OceanTemperatureMonthly(
                location_id=first_loc,
                month=1,
                avg_temp_c=20.4,
                min_temp_c=18.1,
                max_temp_c=22.7,
                sample_count=310,
                baseline_start_year=2016,
                baseline_end_year=2025,
                source_dataset="open-meteo-marine-era5-ocean",
                source_url="https://marine-api.open-meteo.com/v1/marine?...",
                source_checked_at=date(2026, 3, 8),
                grid_lat=-12.0,
                grid_lon=-77.2,
                grid_distance_km=3.2,
                quality_flag="ok",
            ),
            OceanTemperatureMonthly(
                location_id=second_loc,
                month=1,
                avg_temp_c=24.9,
                min_temp_c=23.2,
                max_temp_c=26.3,
                sample_count=310,
                baseline_start_year=2016,
                baseline_end_year=2025,
                source_dataset="open-meteo-marine-era5-ocean",
                source_url="https://marine-api.open-meteo.com/v1/marine?...",
                source_checked_at=date(2026, 3, 8),
                grid_lat=41.1,
                grid_lon=-8.7,
                grid_distance_km=2.8,
                quality_flag="ok",
            ),
        ]
    )
    db_session.commit()

    resp = client.get(
        f"/api/v1/ocean-temperatures?location_id={first_loc}&baseline_end_year=2025"
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 1
    assert payload[0]["location_id"] == first_loc
    assert payload[0]["month"] == 1
    assert payload[0]["avg_temp_c"] == 20.4
