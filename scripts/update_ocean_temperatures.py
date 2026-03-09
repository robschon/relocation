"""Fetch and persist monthly ocean temperature climatology for locations.

Usage:
    UV_CACHE_DIR=.uv-cache uv run python scripts/update_ocean_temperatures.py
    UV_CACHE_DIR=.uv-cache uv run python scripts/update_ocean_temperatures.py --location "Porto"
"""

from __future__ import annotations

import argparse
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

import httpx
from sqlalchemy import func, or_

from relocation.database import SessionLocal, init_db
from relocation.models import Location, OceanTemperatureMonthly

GEOCODE_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"
SOURCE_DATASET = "open-meteo-marine-era5-ocean"
DEFAULT_LOOKBACK_YEARS = 10
COUNTRY_NAME_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
}
LOCATION_COORDINATE_OVERRIDES: dict[str, tuple[float, float]] = {
    "Esperanza, Vieques": (18.0971, -65.4710),
    "Ilha Grande": (-23.1439, -44.2392),
    "Osa Peninsula": (8.7012, -83.6497),
    "Pipa": (-6.2308, -35.0523),
    "Providencia": (13.3530, -81.3749),
    "Puerto Ángel": (15.6650, -96.4870),
    "Rincón": (18.3402, -67.2499),
    "Todos Santos / Cerritos": (23.4300, -110.2100),
    "Valletta / Sliema": (35.9078, 14.5138),
}


@dataclass
class MonthlyStats:
    avg_temp_c: float
    min_temp_c: float
    max_temp_c: float
    sample_count: int


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def _normalized_country(value: str | None) -> str:
    normalized = _normalize(value)
    return _normalize(COUNTRY_NAME_ALIASES.get(normalized, value or ""))


def _query_country(value: str | None) -> str:
    normalized = _normalize(value)
    return COUNTRY_NAME_ALIASES.get(normalized, (value or "").strip())


def _clean_location_name(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", value)
    cleaned = cleaned.replace("/", " ").replace(",", " ")
    return " ".join(cleaned.split())


def _pick_geocode_result(location: Location, results: list[dict]) -> dict | None:
    if not results:
        return None

    country_norm = _normalized_country(location.country)
    region_norm = _normalize(location.region)
    name_norm = _normalize(_clean_location_name(location.name))
    country_matched = [
        result
        for result in results
        if _normalized_country(result.get("country")) == country_norm
    ]
    if country_norm and not country_matched:
        return None

    return max(
        country_matched or results,
        key=lambda result: _result_score(
            location,
            result,
            country_norm=country_norm,
            region_norm=region_norm,
            name_norm=name_norm,
        ),
    )


def _result_score(
    location: Location,  # noqa: ARG001 - kept for readability at call-site
    result: dict,
    *,
    country_norm: str,
    region_norm: str,
    name_norm: str,
) -> tuple[int, int]:
    value = 0
    if _normalized_country(result.get("country")) == country_norm:
        value += 100
    result_name = _normalize(_clean_location_name(result.get("name") or ""))
    if result_name == name_norm:
        value += 40
    if region_norm:
        admin1_norm = _normalize(result.get("admin1"))
        if admin1_norm == region_norm:
            value += 25
        elif admin1_norm:
            value -= 30
    population = int(result.get("population") or 0)
    return value, population


def _candidate_names(name: str) -> list[str]:
    names: list[str] = []

    def add(value: str | None) -> None:
        text = (value or "").strip()
        if text and text not in names:
            names.append(text)

    cleaned = _clean_location_name(name)
    add(name)
    add(cleaned)

    outer = re.sub(r"\([^)]*\)", " ", name).strip()
    add(_clean_location_name(outer))

    for inner in re.findall(r"\(([^)]*)\)", name):
        add(inner)
        add(_clean_location_name(inner))
        for part in inner.split("/"):
            add(_clean_location_name(part))

    for part in re.split(r"[/,]", cleaned):
        add(_clean_location_name(part))

    return names


def _request_json_with_retry(
    client: httpx.Client,
    *,
    url: str,
    params: dict,
    max_attempts: int = 6,
) -> tuple[dict, str]:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(url, params=params)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait_seconds = min(20, 2 ** (attempt - 1))
            time.sleep(wait_seconds)
            continue

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                wait_seconds = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                wait_seconds = 2 ** attempt
            time.sleep(min(60.0, wait_seconds))
            continue

        if 500 <= response.status_code < 600:
            time.sleep(min(20.0, 2 ** attempt))
            continue

        response.raise_for_status()
        return response.json(), str(response.url)

    if last_error:
        raise RuntimeError(f"Request failed after retries: {last_error}") from last_error
    raise RuntimeError("Request failed after retries due to repeated HTTP errors.")


def _geocode_location(client: httpx.Client, location: Location) -> tuple[float, float]:
    override = LOCATION_COORDINATE_OVERRIDES.get(location.name)
    if override:
        return override

    canonical_country = _query_country(location.country)
    name_candidates = _candidate_names(location.name)
    queries: list[str] = []
    for candidate_name in name_candidates:
        for query in [
            ", ".join(part for part in [candidate_name, location.region, canonical_country] if part),
            ", ".join(part for part in [candidate_name, canonical_country] if part),
            candidate_name,
        ]:
            query = query.strip()
            if query and query not in queries:
                queries.append(query)

    country_norm = _normalized_country(location.country)
    region_norm = _normalize(location.region)
    name_norm = _normalize(_clean_location_name(location.name))
    best_result: dict | None = None
    best_score: tuple[int, int] | None = None

    for query in queries:
        payload, _ = _request_json_with_retry(
            client,
            url=GEOCODE_API_URL,
            params={
                "name": query,
                "count": 10,
                "language": "en",
                "format": "json",
            },
        )
        chosen = _pick_geocode_result(location, payload.get("results") or [])
        if chosen:
            score = _result_score(
                location,
                chosen,
                country_norm=country_norm,
                region_norm=region_norm,
                name_norm=name_norm,
            )
            if best_score is None or score > best_score:
                best_result = chosen
                best_score = score

    if best_result:
        return float(best_result["latitude"]), float(best_result["longitude"])
    raise RuntimeError(f"No geocoding match found for {location.name} ({location.country})")


def _fetch_marine_hourly_sst(
    client: httpx.Client,
    *,
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
) -> tuple[dict, str]:
    return _request_json_with_retry(
        client,
        url=MARINE_API_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "sea_surface_temperature",
            "temperature_unit": "celsius",
            "timezone": "UTC",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "cell_selection": "sea",
        },
    )


def _aggregate_monthly(data: dict) -> dict[int, MonthlyStats]:
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    temperatures = hourly.get("sea_surface_temperature") or []
    if not times or not temperatures:
        raise RuntimeError("Marine API returned no hourly sea surface temperature values.")
    if len(times) != len(temperatures):
        raise RuntimeError("Marine API returned mismatched time/value arrays.")

    buckets: dict[int, list[float]] = defaultdict(list)
    for day_str, value in zip(times, temperatures, strict=True):
        if value is None:
            continue
        temp = float(value)
        # Keep only physically plausible SST values.
        if temp < -2 or temp > 40:
            continue
        month = datetime.fromisoformat(day_str).month
        buckets[month].append(temp)

    stats: dict[int, MonthlyStats] = {}
    for month in range(1, 13):
        values = buckets.get(month) or []
        if not values:
            raise RuntimeError(f"No sea surface temperature samples for month {month}.")
        stats[month] = MonthlyStats(
            avg_temp_c=round(sum(values) / len(values), 2),
            min_temp_c=round(min(values), 2),
            max_temp_c=round(max(values), 2),
            sample_count=len(values),
        )
    return stats


def _quality_flag(
    *,
    min_samples: int,
    grid_distance_km: float | None,
    used_nearest_sea_search: bool,
) -> str:
    flags: list[str] = []
    if min_samples < 1500:
        flags.append("sparse")
    if grid_distance_km is not None and grid_distance_km > 75:
        flags.append("far_grid_cell")
    if used_nearest_sea_search:
        flags.append("nearest_sea_search")
    return ",".join(flags) if flags else "ok"


def _upsert_monthly_rows(
    *,
    location: Location,
    monthly: dict[int, MonthlyStats],
    baseline_start_year: int,
    baseline_end_year: int,
    source_url: str,
    grid_lat: float | None,
    grid_lon: float | None,
    grid_distance_km: float | None,
    used_nearest_sea_search: bool,
    source_checked_at: date,
) -> tuple[int, int]:
    inserted = 0
    updated = 0

    with SessionLocal() as session:
        existing = {
            row.month: row
            for row in session.query(OceanTemperatureMonthly)
            .filter(
                OceanTemperatureMonthly.location_id == location.id,
                OceanTemperatureMonthly.baseline_start_year == baseline_start_year,
                OceanTemperatureMonthly.baseline_end_year == baseline_end_year,
                OceanTemperatureMonthly.source_dataset == SOURCE_DATASET,
            )
            .all()
        }
        min_samples = min(stat.sample_count for stat in monthly.values())
        quality = _quality_flag(
            min_samples=min_samples,
            grid_distance_km=grid_distance_km,
            used_nearest_sea_search=used_nearest_sea_search,
        )

        for month, stat in monthly.items():
            record = existing.get(month)
            if record:
                record.avg_temp_c = stat.avg_temp_c
                record.min_temp_c = stat.min_temp_c
                record.max_temp_c = stat.max_temp_c
                record.sample_count = stat.sample_count
                record.source_url = source_url
                record.source_checked_at = source_checked_at
                record.grid_lat = grid_lat
                record.grid_lon = grid_lon
                record.grid_distance_km = grid_distance_km
                record.quality_flag = quality
                updated += 1
            else:
                session.add(
                    OceanTemperatureMonthly(
                        location_id=location.id,
                        month=month,
                        avg_temp_c=stat.avg_temp_c,
                        min_temp_c=stat.min_temp_c,
                        max_temp_c=stat.max_temp_c,
                        sample_count=stat.sample_count,
                        baseline_start_year=baseline_start_year,
                        baseline_end_year=baseline_end_year,
                        source_dataset=SOURCE_DATASET,
                        source_url=source_url,
                        source_checked_at=source_checked_at,
                        grid_lat=grid_lat,
                        grid_lon=grid_lon,
                        grid_distance_km=grid_distance_km,
                        quality_flag=quality,
                    )
                )
                inserted += 1

        session.commit()
    return inserted, updated


def _update_location_coordinates(location_id: int, latitude: float, longitude: float) -> None:
    with SessionLocal() as session:
        db_location = session.get(Location, location_id)
        if not db_location:
            return
        db_location.latitude = latitude
        db_location.longitude = longitude
        session.commit()


def _find_nearest_sea_data(
    client: httpx.Client,
    *,
    origin_lat: float,
    origin_lon: float,
    start_date: date,
    end_date: date,
) -> tuple[dict, dict[int, MonthlyStats], str]:
    # Expand around the location until a complete month-by-month SST series is found.
    radii_deg = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0]
    directions = [
        (0.0, 1.0),
        (1.0, 0.0),
        (0.0, -1.0),
        (-1.0, 0.0),
        (1.0, 1.0),
        (1.0, -1.0),
        (-1.0, 1.0),
        (-1.0, -1.0),
    ]

    for radius in radii_deg:
        for d_lat, d_lon in directions:
            candidate_lat = max(-89.5, min(89.5, origin_lat + (d_lat * radius)))
            candidate_lon = origin_lon + (d_lon * radius)
            if candidate_lon > 180:
                candidate_lon -= 360
            if candidate_lon < -180:
                candidate_lon += 360
            try:
                marine_data, source_url = _fetch_marine_hourly_sst(
                    client,
                    latitude=candidate_lat,
                    longitude=candidate_lon,
                    start_date=start_date,
                    end_date=end_date,
                )
                monthly = _aggregate_monthly(marine_data)
                return marine_data, monthly, source_url
            except Exception:  # noqa: BLE001
                continue

    raise RuntimeError("Unable to find nearby sea coordinates with complete monthly SST data.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch monthly ocean temperatures for all (or selected) locations."
    )
    parser.add_argument(
        "--location-id",
        action="append",
        type=int,
        help="Exact location id to process. Repeat for multiple ids.",
    )
    parser.add_argument(
        "--location",
        action="append",
        help="Exact location name to process. Repeat for multiple names.",
    )
    parser.add_argument("--baseline-start-year", type=int, default=None)
    parser.add_argument("--baseline-end-year", type=int, default=None)
    parser.add_argument(
        "--refresh-coordinates",
        action="store_true",
        help="Re-geocode coordinates even when location already has latitude/longitude.",
    )
    parser.add_argument(
        "--only-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Process only locations without a full 12-month baseline for the chosen window/source.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=2.0,
        help="Sleep interval between locations to reduce upstream rate-limit errors.",
    )
    parser.add_argument("--max-locations", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    today = date.today()
    baseline_end_year = args.baseline_end_year or (today.year - 1)
    baseline_start_year = args.baseline_start_year or (baseline_end_year - (DEFAULT_LOOKBACK_YEARS - 1))
    if baseline_start_year > baseline_end_year:
        raise SystemExit("baseline_start_year cannot be greater than baseline_end_year")

    start_date = date(baseline_start_year, 1, 1)
    end_date = date(baseline_end_year, 12, 31)
    print(
        f"[info] baseline={baseline_start_year}-{baseline_end_year} "
        f"window={start_date.isoformat()}..{end_date.isoformat()}"
    )

    init_db()
    with SessionLocal() as session:
        query = session.query(Location).order_by(Location.name.asc())
        if args.location_id:
            query = query.filter(Location.id.in_(args.location_id))
        if args.location:
            predicates = [Location.name.ilike(name.strip()) for name in args.location]
            query = query.filter(or_(*predicates))
        locations = query.all()

        if args.only_missing:
            complete_location_ids = {
                location_id
                for location_id, row_count in (
                    session.query(
                        OceanTemperatureMonthly.location_id,
                        func.count(OceanTemperatureMonthly.id),
                    )
                    .filter(
                        OceanTemperatureMonthly.baseline_start_year == baseline_start_year,
                        OceanTemperatureMonthly.baseline_end_year == baseline_end_year,
                        OceanTemperatureMonthly.source_dataset == SOURCE_DATASET,
                    )
                    .group_by(OceanTemperatureMonthly.location_id)
                    .all()
                )
                if row_count >= 12
            }
            locations = [location for location in locations if location.id not in complete_location_ids]

    if args.max_locations is not None:
        locations = locations[: args.max_locations]

    if not locations:
        print("[warn] no locations matched filters")
        return 1

    inserted_total = 0
    updated_total = 0
    failures: list[str] = []

    with httpx.Client(timeout=45.0) as client:
        for idx, location in enumerate(locations, start=1):
            print(f"[{idx}/{len(locations)}] {location.name} ({location.country})")
            try:
                latitude = location.latitude
                longitude = location.longitude
                if args.refresh_coordinates or latitude is None or longitude is None:
                    latitude, longitude = _geocode_location(client, location)
                    _update_location_coordinates(location.id, latitude, longitude)
                    print(f"  [coords] {latitude:.4f}, {longitude:.4f}")
                if latitude is None or longitude is None:
                    raise RuntimeError("Location has no coordinates after geocoding step.")

                marine_data, source_url = _fetch_marine_hourly_sst(
                    client,
                    latitude=latitude,
                    longitude=longitude,
                    start_date=start_date,
                    end_date=end_date,
                )
                used_nearest_sea_search = False
                try:
                    monthly = _aggregate_monthly(marine_data)
                except RuntimeError:
                    marine_data, monthly, source_url = _find_nearest_sea_data(
                        client,
                        origin_lat=latitude,
                        origin_lon=longitude,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    used_nearest_sea_search = True
                grid_lat = float(marine_data["latitude"]) if marine_data.get("latitude") is not None else None
                grid_lon = float(marine_data["longitude"]) if marine_data.get("longitude") is not None else None
                grid_distance_km = (
                    round(_haversine_km(latitude, longitude, grid_lat, grid_lon), 2)
                    if grid_lat is not None and grid_lon is not None
                    else None
                )

                inserted, updated = _upsert_monthly_rows(
                    location=location,
                    monthly=monthly,
                    baseline_start_year=baseline_start_year,
                    baseline_end_year=baseline_end_year,
                    source_url=source_url,
                    grid_lat=grid_lat,
                    grid_lon=grid_lon,
                    grid_distance_km=grid_distance_km,
                    used_nearest_sea_search=used_nearest_sea_search,
                    source_checked_at=today,
                )
                inserted_total += inserted
                updated_total += updated
                print(
                    f"  [ok] rows inserted={inserted} updated={updated} "
                    f"grid_distance_km={grid_distance_km if grid_distance_km is not None else 'n/a'}"
                )
            except Exception as exc:  # noqa: BLE001
                message = f"{location.name} ({location.country}): {exc}"
                failures.append(message)
                print(f"  [error] {message}")
            finally:
                if args.request_interval_seconds > 0:
                    time.sleep(args.request_interval_seconds)

    print(
        f"[done] processed={len(locations)} inserted={inserted_total} updated={updated_total} "
        f"failed={len(failures)}"
    )
    if failures:
        print("[failures]")
        for message in failures:
            print(f"  - {message}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
