from relocation.services.beach_accessibility import (
    base_score_from_distance_km,
    compute_beach_accessibility_score,
    fallback_score_from_ocean_distance_km,
)


def test_base_score_from_distance_km_thresholds():
    assert base_score_from_distance_km(0.2) == 10
    assert base_score_from_distance_km(1.0) == 9
    assert base_score_from_distance_km(2.0) == 8
    assert base_score_from_distance_km(4.0) == 7
    assert base_score_from_distance_km(8.0) == 6
    assert base_score_from_distance_km(15.0) == 4
    assert base_score_from_distance_km(25.0) == 3
    assert base_score_from_distance_km(40.0) == 2
    assert base_score_from_distance_km(60.0) == 0
    assert base_score_from_distance_km(None) == 0


def test_compute_beach_accessibility_score_density_bonus():
    score = compute_beach_accessibility_score(
        nearest_public_km=2.2,
        public_within_10_km=6,
        public_within_20_km=13,
        has_private_only=False,
    )
    assert score == 10


def test_compute_beach_accessibility_score_sparse_penalty():
    score = compute_beach_accessibility_score(
        nearest_public_km=12.0,
        public_within_10_km=0,
        public_within_20_km=1,
        has_private_only=False,
    )
    assert score == 3


def test_compute_beach_accessibility_score_private_only_penalty():
    score = compute_beach_accessibility_score(
        nearest_public_km=None,
        public_within_10_km=0,
        public_within_20_km=0,
        has_private_only=True,
    )
    assert score == 0


def test_fallback_score_from_ocean_distance_km():
    assert fallback_score_from_ocean_distance_km(0.3) == 8
    assert fallback_score_from_ocean_distance_km(30.0) == 1
    assert fallback_score_from_ocean_distance_km(70.0) == 0


def _beach_script():
    from relocation.enrichment import beach

    return beach


def test_overpass_query_uses_bounding_box_not_around():
    script = _beach_script()
    query = script._overpass_query(38.7, -9.4, 20.0)
    assert "around" not in query
    assert 'nwr["natural"="beach"]' in query
    south, west, north, east = script._bounding_box(38.7, -9.4, 20.0)
    assert south < 38.7 < north and west < -9.4 < east
    # ~20 km each way
    assert 0.17 < north - 38.7 < 0.19


def test_beaches_within_drops_box_corners_and_splits_private():
    script = _beach_script()
    elements = [
        {"type": "node", "lat": 38.70, "lon": -9.40, "tags": {}},  # 0 km, public
        {"type": "node", "lat": 38.75, "lon": -9.40, "tags": {"access": "private"}},  # ~5.6 km, private
        {"type": "way", "center": {"lat": 38.88, "lon": -9.17}, "tags": {}},  # box corner, ~28 km: dropped
    ]
    public, private = script._beaches_within(elements, 38.70, -9.40, 20.0)
    assert len(public) == 1 and public[0] < 0.1
    assert private == 1
