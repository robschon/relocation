"""Write research evidence while keeping exactly one current row per subject/category/provider.

The subject is a location, or a country for country-scope categories. Rules that
apply to every writer (API, CLI, pipeline) live here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from relocation.models import Category, Research
from relocation.services.errors import ValidationFailed
from relocation.services.subjects import resolve_subject


def validate_cited_research(category: Category | None, fields: dict) -> None:
    """Categories with requires_citation (visa, tax) need dated, sourced, non-'general knowledge' evidence."""
    if category is None or not category.requires_citation:
        return
    source = (fields.get("source") or "").strip().lower()
    if not source:
        raise ValidationFailed(f"{category.name} research requires a source summary with dated citations.")
    if "general knowledge" in source:
        raise ValidationFailed(f"{category.name} research cannot use 'general knowledge' as source basis.")
    if not fields.get("source_urls"):
        raise ValidationFailed(f"{category.name} research requires at least one source URL.")
    if not fields.get("source_checked_at"):
        raise ValidationFailed(f"{category.name} research requires source_checked_at.")
    if fields.get("confidence") is None:
        raise ValidationFailed(f"{category.name} research requires a confidence score between 0 and 1.")
    if fields.get("verification_status") == "stale":
        raise ValidationFailed(f"New {category.name} research cannot be created with stale verification status.")


def _same_slot(db: Session, entry: Research):
    """Rows for the same subject (location, or country for country-scope rows), category and provider."""
    if entry.location_id is not None:
        subject = Research.location_id == entry.location_id
    else:
        subject = (Research.location_id.is_(None)) & (Research.country_code == entry.country_code)
    return db.query(Research).filter(
        subject,
        Research.category_id.is_(None) if entry.category_id is None else Research.category_id == entry.category_id,
        Research.provider == entry.provider,
        Research.id != entry.id,
    )


def add_research(db: Session, **fields) -> Research:
    """Insert a new current research row; earlier rows for the same slot become history."""
    entry = Research(**fields, is_current=True)
    _same_slot(db, entry).filter(Research.is_current.is_(True)).update(
        {Research.is_current: False}, synchronize_session=False
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_research(db: Session, fields: dict) -> Research:
    """Validate and store research, routing country-scope categories to the location's country."""
    subject = resolve_subject(
        db,
        category_id=fields.get("category_id"),
        location_id=fields.get("location_id"),
        country_code=fields.get("country_code"),
    )
    validate_cited_research(subject.category, fields)
    return add_research(db, **{**fields, "location_id": subject.location_id, "country_code": subject.country_code})


def delete_research(db: Session, entry: Research) -> None:
    """Delete a research row; if it was current, the newest remaining row for its slot takes over."""
    was_current = entry.is_current
    successor = _same_slot(db, entry).order_by(Research.id.desc()).first() if was_current else None
    db.delete(entry)
    db.flush()
    if successor is not None:
        successor.is_current = True
    db.commit()
