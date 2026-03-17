from __future__ import annotations

import re
from collections.abc import Iterable

import httpx

OPEN_METEO_GEOCODE_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_GEOCODE_API_URL = "https://nominatim.openstreetmap.org/search"
COUNTRY_NAME_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "espana": "Spain",
    "españa": "Spain",
}
MAX_RESULTS = 8
NOMINATIM_USER_AGENT = "relocation-planner/0.1"


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


def _tokens(values: Iterable[str | None]) -> set[str]:
    out: set[str] = set()
    for value in values:
        normalized = _normalize(value)
        if not normalized:
            continue
        out.update(token for token in re.split(r"[^a-z0-9]+", normalized) if token)
    return out


def _candidate_queries(name: str, country: str, region: str | None) -> list[str]:
    canonical_country = _query_country(country)
    cleaned_name = _clean_location_name(name)
    region_variants = _region_variants(region, canonical_country)
    queries: list[str] = []

    for region_variant in region_variants:
        for query in [
            ", ".join(part for part in [cleaned_name, region_variant, canonical_country] if part),
            ", ".join(part for part in [cleaned_name, canonical_country] if part),
            cleaned_name,
        ]:
            query = query.strip()
            if query and query not in queries:
                queries.append(query)

    return queries


def _region_variants(region: str | None, country: str | None) -> list[str | None]:
    variants: list[str | None] = []

    def add(value: str | None) -> None:
        if value is None:
            if None not in variants:
                variants.append(None)
            return
        text = value.strip()
        if text and text not in variants:
            variants.append(text)

    add(region)

    region_norm = _normalize(region)
    country_norm = _normalized_country(country)
    if country_norm == "spain":
        if "tenerife" in region_norm:
            add("Santa Cruz de Tenerife")
            add("Canary Islands")
        if "gran canaria" in region_norm:
            add("Las Palmas")
            add("Canary Islands")

    if not variants:
        variants.append(None)
    return variants


def _region_match(region: str | None, result: dict) -> bool:
    if not region:
        return True

    region_norm = _normalize(region)
    fields = [
        result.get("admin1"),
        result.get("admin2"),
        result.get("admin3"),
        result.get("name"),
        result.get("display_name"),
    ]
    normalized_fields = {_normalize(value) for value in fields if value}
    if region_norm in normalized_fields:
        return True

    region_tokens = _tokens([region])
    result_tokens = _tokens(fields)
    return bool(region_tokens & result_tokens)


def _region_score(region: str | None, result: dict) -> int:
    if not region:
        return 0

    region_norm = _normalize(region)
    fields = [
        result.get("admin1"),
        result.get("admin2"),
        result.get("admin3"),
        result.get("name"),
        result.get("display_name"),
    ]
    normalized_fields = {_normalize(value) for value in fields if value}
    if region_norm in normalized_fields:
        return 25

    region_tokens = _tokens([region])
    result_tokens = _tokens(fields)
    overlap = region_tokens & result_tokens
    if overlap:
        return 10 + min(10, len(overlap) * 2)
    return -20


def _candidate_score(name: str, country: str, region: str | None, result: dict) -> int:
    score = 0
    if _normalized_country(result.get("country")) == _normalized_country(country):
        score += 100

    clean_name = _normalize(_clean_location_name(name))
    result_name = _normalize(_clean_location_name(result.get("name") or ""))
    if clean_name == result_name:
        score += 40
    elif clean_name and clean_name in result_name:
        score += 20

    score += _region_score(region, result)

    feature_code = str(result.get("feature_code") or "")
    if feature_code.startswith("PPL"):
        score += 5
    elif result.get("provider") == "nominatim":
        score += 2
    return score


def _display_name(result: dict) -> str:
    parts: list[str] = []
    for value in [result.get("name"), result.get("admin2"), result.get("admin1"), result.get("country")]:
        text = str(value or "").strip()
        if text and text not in parts:
            parts.append(text)
    return ", ".join(parts)


def _first_display_segment(display_name: str | None) -> str:
    text = str(display_name or "").strip()
    if not text:
        return ""
    return text.split(",")[0].strip()


def _fetch_open_meteo_candidates(client: httpx.Client, query: str) -> list[dict]:
    response = client.get(
        OPEN_METEO_GEOCODE_API_URL,
        params={
            "name": query,
            "count": 10,
            "language": "en",
            "format": "json",
        },
    )
    response.raise_for_status()
    payload = response.json()

    out: list[dict] = []
    for result in payload.get("results") or []:
        latitude = float(result["latitude"])
        longitude = float(result["longitude"])
        normalized = {
            "name": str(result.get("name") or "").strip(),
            "display_name": "",
            "country": str(result.get("country") or "").strip() or None,
            "admin1": str(result.get("admin1") or "").strip() or None,
            "admin2": str(result.get("admin2") or "").strip() or None,
            "admin3": str(result.get("admin3") or "").strip() or None,
            "latitude": latitude,
            "longitude": longitude,
            "population": int(result.get("population") or 0) or None,
            "feature_code": str(result.get("feature_code") or "").strip() or None,
            "provider": "open-meteo",
        }
        normalized["display_name"] = _display_name(normalized)
        out.append(normalized)
    return out


def _fetch_nominatim_candidates(client: httpx.Client, query: str) -> list[dict]:
    response = client.get(
        NOMINATIM_GEOCODE_API_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 10,
        },
        headers={"User-Agent": NOMINATIM_USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()

    out: list[dict] = []
    for result in payload or []:
        address = result.get("address") or {}
        latitude = float(result["lat"])
        longitude = float(result["lon"])
        normalized = {
            "name": str(
                result.get("name")
                or address.get("village")
                or address.get("town")
                or address.get("city")
                or _first_display_segment(result.get("display_name"))
            ).strip(),
            "display_name": str(result.get("display_name") or "").strip(),
            "country": str(address.get("country") or "").strip() or None,
            "admin1": str(address.get("state") or address.get("region") or "").strip() or None,
            "admin2": str(address.get("county") or "").strip() or None,
            "admin3": str(
                address.get("municipality")
                or address.get("city_district")
                or address.get("suburb")
                or ""
            ).strip()
            or None,
            "latitude": latitude,
            "longitude": longitude,
            "population": None,
            "feature_code": str(result.get("type") or "").strip() or None,
            "provider": "nominatim",
        }
        out.append(normalized)
    return out


def _collect_candidates(
    *,
    client: httpx.Client,
    name: str,
    country: str,
    region: str | None,
    queries: list[str],
    provider_name: str,
    fetcher,
) -> list[dict]:
    country_norm = _normalized_country(country)
    candidates: list[dict] = []

    for query in queries:
        for result in fetcher(client, query):
            if country_norm and _normalized_country(result.get("country")) != country_norm:
                continue
            candidate = {
                **result,
                "region": result.get("admin1"),
                "query": query,
            }
            candidate["region_match"] = _region_match(region, candidate)
            candidate["score"] = _candidate_score(name, country, region, candidate)
            candidate["provider"] = provider_name
            candidates.append(candidate)
    return candidates


def _dedupe_and_sort(candidates: list[dict]) -> list[dict]:
    best_by_key: dict[tuple[str, float, float], dict] = {}
    for candidate in candidates:
        key = (
            _normalize(candidate.get("name")),
            round(float(candidate["latitude"]), 5),
            round(float(candidate["longitude"]), 5),
        )
        previous = best_by_key.get(key)
        if previous is None or (
            candidate["score"],
            candidate.get("population") or 0,
        ) > (
            previous["score"],
            previous.get("population") or 0,
        ):
            best_by_key[key] = candidate

    deduped = list(best_by_key.values())
    deduped.sort(
        key=lambda candidate: (
            candidate["score"],
            candidate.get("population") or 0,
        ),
        reverse=True,
    )
    return deduped[:MAX_RESULTS]


def search_location_candidates(*, name: str, country: str, region: str | None = None) -> dict:
    queries = _candidate_queries(name, country, region)
    warnings: list[str] = []

    with httpx.Client(timeout=20.0) as client:
        open_meteo_candidates = _collect_candidates(
            client=client,
            name=name,
            country=country,
            region=region,
            queries=queries,
            provider_name="open-meteo",
            fetcher=_fetch_open_meteo_candidates,
        )

        all_candidates = list(open_meteo_candidates)
        need_fallback = not open_meteo_candidates or (
            bool(region) and not any(candidate["region_match"] for candidate in open_meteo_candidates)
        )

        if need_fallback:
            nominatim_candidates = _collect_candidates(
                client=client,
                name=name,
                country=country,
                region=region,
                queries=queries,
                provider_name="nominatim",
                fetcher=_fetch_nominatim_candidates,
            )
            if nominatim_candidates:
                all_candidates.extend(nominatim_candidates)
                warnings.append("Primary geocoder returned no strong regional match; showing fallback results from OpenStreetMap Nominatim too.")

    candidates = _dedupe_and_sort(all_candidates)

    if region and candidates and not any(candidate["region_match"] for candidate in candidates):
        warnings.append(
            f'No candidates matched the requested region "{region}". Results below may refer to same-name places elsewhere.'
        )

    if not candidates:
        warnings.append("No geocoder returned a usable match. Enter confirmed coordinates manually.")

    return {"candidates": candidates, "warnings": warnings}
