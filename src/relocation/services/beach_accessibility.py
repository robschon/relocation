from __future__ import annotations


def _clamp_score(score: int) -> int:
    return max(0, min(10, score))


def base_score_from_distance_km(distance_km: float | None) -> int:
    """Map nearest public-beach distance to a 0-10 accessibility score."""
    if distance_km is None:
        return 0
    if distance_km <= 0.5:
        return 10
    if distance_km <= 1.5:
        return 9
    if distance_km <= 3:
        return 8
    if distance_km <= 5:
        return 7
    if distance_km <= 10:
        return 6
    if distance_km <= 20:
        return 4
    if distance_km <= 30:
        return 3
    if distance_km <= 50:
        return 2
    return 0


def compute_beach_accessibility_score(
    *,
    nearest_public_km: float | None,
    public_within_10_km: int,
    public_within_20_km: int,
    has_private_only: bool,
) -> int:
    """
    Compute a final beach accessibility score from nearest-beach distance and density.

    This intentionally rewards both proximity and option density, while penalizing
    places where nearby mapped beaches are mostly private.
    """
    score = base_score_from_distance_km(nearest_public_km)

    if public_within_10_km >= 5:
        score += 1
    elif public_within_10_km == 0 and nearest_public_km is not None and nearest_public_km > 5:
        score -= 1

    if public_within_20_km >= 12:
        score += 1

    if has_private_only and nearest_public_km is None:
        score -= 2

    return _clamp_score(score)


def fallback_score_from_ocean_distance_km(distance_km: float) -> int:
    """
    Fallback score using nearest sea-grid distance from ocean temperature data.

    We subtract 2 points because distance-to-sea is a weaker proxy than explicit
    public-beach mapping.
    """
    return _clamp_score(base_score_from_distance_km(distance_km) - 2)
