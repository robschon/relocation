"""Visa/residency info per country: validation and atomic replacement."""

from __future__ import annotations

from sqlalchemy.orm import Session

from relocation.models import DEFAULT_PROVIDER, VisaInfo
from relocation.services.errors import ValidationFailed


def validate_visa_evidence(info: VisaInfo) -> None:
    if not info.source_urls:
        raise ValidationFailed("Visa entries require at least one source URL.")
    if not info.source_checked_at:
        raise ValidationFailed("Visa entries require source_checked_at.")
    if info.verification_status == "verified" and info.confidence is None:
        raise ValidationFailed("Verified visa entries require confidence between 0 and 1.")


def replace_country_visa(
    db: Session,
    *,
    country: str,
    country_code: str,
    entries: list[dict],
    provider: str = DEFAULT_PROVIDER,
    run_id: int | None = None,
) -> list[VisaInfo]:
    """Replace a country's visa rows for this provider in one transaction (all or nothing)."""
    new_rows = [
        VisaInfo(**{**entry, "country": country, "country_code": country_code, "provider": provider, "run_id": run_id})
        for entry in entries
    ]
    for row in new_rows:
        validate_visa_evidence(row)
    if not new_rows:
        raise ValidationFailed(f"No usable visa entries for {country}.")
    db.query(VisaInfo).filter(VisaInfo.country_code == country_code, VisaInfo.provider == provider).delete(
        synchronize_session=False
    )
    db.add_all(new_rows)
    db.commit()
    return new_rows
