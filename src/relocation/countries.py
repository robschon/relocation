from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pycountry


@dataclass(frozen=True)
class CountryResolution:
    display_name: str | None
    country_code: str | None


COUNTRY_NAME_BY_CODE = {
    "AL": "Albania",
    "AU": "Australia",
    "BZ": "Belize",
    "BR": "Brazil",
    "CV": "Cabo Verde",
    "CL": "Chile",
    "CO": "Colombia",
    "CU": "Cuba",
    "CR": "Costa Rica",
    "CZ": "Czechia",
    "HR": "Croatia",
    "CW": "Curaçao",
    "CY": "Cyprus",
    "DO": "Dominican Republic",
    "EC": "Ecuador",
    "FR": "France",
    "GB": "United Kingdom",
    "GP": "Guadeloupe",
    "GR": "Greece",
    "GY": "Guyana",
    "HN": "Honduras",
    "ID": "Indonesia",
    "IN": "India",
    "IT": "Italy",
    "LK": "Sri Lanka",
    "ME": "Montenegro",
    "MG": "Madagascar",
    "MT": "Malta",
    "MU": "Mauritius",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NI": "Nicaragua",
    "NZ": "New Zealand",
    "PA": "Panama",
    "PE": "Peru",
    "PH": "Philippines",
    "PR": "Puerto Rico",
    "PT": "Portugal",
    "SG": "Singapore",
    "SI": "Slovenia",
    "ES": "Spain",
    "TH": "Thailand",
    "TT": "Trinidad and Tobago",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "US": "United States",
    "UY": "Uruguay",
    "VN": "Vietnam",
    "ZA": "South Africa",
}

COUNTRY_CODE_ALIASES = {
    "britain": "GB",
    "cape verde": "CV",
    "czech republic": "CZ",
    "curacao": "CW",
    "england": "GB",
    "españa": "ES",
    "espana": "ES",
    "great britain": "GB",
    "scotland": "GB",
    "u k": "GB",
    "u s": "US",
    "u s a": "US",
    "uk": "GB",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "viet nam": "VN",
    "wales": "GB",
}

# Jurisdictions that sit under another country (informational; e.g. Puerto Rico under the US).
PARENT_COUNTRY_CODE = {
    "PR": "US",
    "GP": "FR",
    "CW": "NL",
}

# Places a U.S. citizen can live without any visa or residency permit.
US_CITIZEN_HOME_JURISDICTIONS = {"US", "PR"}


def normalize_country_key(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text.casefold())
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_country_code(value: str | None) -> str | None:
    code = str(value or "").strip().upper()
    return code or None


def country_name_from_code(value: str | None) -> str | None:
    """Display name for an ISO alpha-2 code: our curated names first, then ISO 3166 (pycountry)."""
    code = normalize_country_code(value)
    if not code:
        return None
    if code in COUNTRY_NAME_BY_CODE:
        return COUNTRY_NAME_BY_CODE[code]
    record = pycountry.countries.get(alpha_2=code)
    if record is None:
        return None
    return getattr(record, "common_name", None) or record.name


def _iso_lookup(name: str) -> str | None:
    try:
        return pycountry.countries.lookup(name).alpha_2
    except LookupError:
        return None


def resolve_country(
    country: str | None = None,
    country_code: str | None = None,
) -> CountryResolution:
    normalized_code = normalize_country_code(country_code)
    raw_country = " ".join(str(country or "").strip().split()) or None

    if normalized_code:
        display_name = country_name_from_code(normalized_code)
        if display_name is None:
            raise ValueError(f"Unsupported country code: {normalized_code}")
        if raw_country:
            resolved_country = resolve_country(country=raw_country)
            if (
                resolved_country.country_code
                and resolved_country.country_code != normalized_code
            ):
                raise ValueError(
                    f"Country '{raw_country}' does not match country code '{normalized_code}'."
                )
        return CountryResolution(display_name=display_name, country_code=normalized_code)

    if not raw_country:
        return CountryResolution(display_name=None, country_code=None)

    guessed_code = normalize_country_code(raw_country)
    if guessed_code and len(guessed_code) == 2 and country_name_from_code(guessed_code):
        return CountryResolution(
            display_name=country_name_from_code(guessed_code),
            country_code=guessed_code,
        )

    normalized_country = normalize_country_key(raw_country)

    code = COUNTRY_CODE_ALIASES.get(normalized_country)
    if code:
        return CountryResolution(
            display_name=COUNTRY_NAME_BY_CODE[code],
            country_code=code,
        )

    for canonical_code, canonical_name in COUNTRY_NAME_BY_CODE.items():
        if normalize_country_key(canonical_name) == normalized_country:
            return CountryResolution(
                display_name=canonical_name,
                country_code=canonical_code,
            )

    iso_code = _iso_lookup(raw_country)
    if iso_code:
        return CountryResolution(display_name=country_name_from_code(iso_code), country_code=iso_code)

    return CountryResolution(display_name=raw_country, country_code=None)


def normalize_country_fields(
    country: str | None = None,
    country_code: str | None = None,
) -> tuple[str | None, str | None]:
    resolved = resolve_country(country=country, country_code=country_code)
    return resolved.display_name, resolved.country_code


def country_matches_query(
    *,
    country: str | None,
    country_code: str | None,
    query: str | None,
) -> bool:
    normalized_query = normalize_country_key(query)
    if not normalized_query:
        return True

    resolved_query = resolve_country(country=query)
    record_country = normalize_country_key(country)
    record_code = normalize_country_code(country_code)

    if resolved_query.country_code and record_code == resolved_query.country_code:
        return True

    if resolved_query.display_name:
        resolved_name = normalize_country_key(resolved_query.display_name)
        if record_country == resolved_name:
            return True

    return normalized_query in record_country
