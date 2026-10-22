from relocation.countries import country_matches_query, normalize_country_fields


def test_normalize_country_fields_converts_usa_to_united_states():
    country, country_code = normalize_country_fields(country="USA")
    assert country == "United States"
    assert country_code == "US"


def test_unknown_country_has_no_code():
    country, country_code = normalize_country_fields(country="US Territories")
    assert country == "US Territories"
    assert country_code is None


def test_iso_fallback_resolves_countries_outside_curated_list():
    assert normalize_country_fields(country="Fiji") == ("Fiji", "FJ")
    assert normalize_country_fields(country_code="lk") == ("Sri Lanka", "LK")
    assert normalize_country_fields(country="Slovenia") == ("Slovenia", "SI")


def test_puerto_rico_is_its_own_jurisdiction():
    assert normalize_country_fields(country="Puerto Rico") == ("Puerto Rico", "PR")


def test_country_matches_query_uses_country_code_aliases():
    assert country_matches_query(
        country="United States",
        country_code="US",
        query="USA",
    )
