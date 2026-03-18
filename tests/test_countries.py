from relocation.countries import country_matches_query, normalize_country_fields


def test_normalize_country_fields_converts_usa_to_united_states():
    country, country_code = normalize_country_fields(country="USA")
    assert country == "United States"
    assert country_code == "US"


def test_normalize_country_fields_preserves_custom_bucket_without_code():
    country, country_code = normalize_country_fields(country="US Territories")
    assert country == "US Territories"
    assert country_code is None


def test_country_matches_query_uses_country_code_aliases():
    assert country_matches_query(
        country="United States",
        country_code="US",
        query="USA",
    )
