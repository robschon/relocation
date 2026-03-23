import re
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from relocation.countries import normalize_country_fields
from relocation.database import get_db
from relocation.models import Location
from relocation.schemas import (
    LocationCandidateSearchOut,
    LocationCreate,
    LocationOut,
    LocationUpdate,
)
from relocation.services.location_candidates import search_location_candidates
from relocation.services.new_location_enrichment import run_location_post_create_pipeline
from relocation.services.scoring import get_fully_scored_location_ids

router = APIRouter(tags=["locations"])
PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESEARCH_DIR = PROJECT_ROOT / "research"


def _slugify(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def _find_research_doc_path(location: Location) -> Path | None:
    primary = RESEARCH_DIR / f"{_slugify(location.name)}-{_slugify(location.country)}.md"
    if primary.exists():
        return primary

    prefix = f"{_slugify(location.name)}-"
    matches = sorted(
        RESEARCH_DIR.glob(f"{prefix}*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    fully_scored_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Location)
    if fully_scored_only:
        fully_scored_location_ids = get_fully_scored_location_ids(db)
        if not fully_scored_location_ids:
            return []
        query = query.filter(Location.id.in_(fully_scored_location_ids))
    return query.order_by(Location.name).all()


@router.get("/location-candidates", response_model=LocationCandidateSearchOut)
def list_location_candidates(name: str, country: str, region: str | None = None):
    try:
        return search_location_candidates(name=name, country=country, region=region)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Location lookup failed: {exc}") from exc


@router.get("/locations/{location_id}", response_model=LocationOut)
def get_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    return loc


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(
    data: LocationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = data.model_dump()
    try:
        payload["country"], payload["country_code"] = normalize_country_fields(
            country=payload.get("country"),
            country_code=payload.get("country_code"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    loc = Location(**payload)
    db.add(loc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f'Location "{data.name}" in {data.country} already exists.',
        ) from exc
    db.refresh(loc)
    if loc.latitude is not None and loc.longitude is not None:
        background_tasks.add_task(run_location_post_create_pipeline, loc.id)
    return loc


@router.put("/locations/{location_id}", response_model=LocationOut)
def update_location(location_id: int, data: LocationUpdate, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Location not found")

    updates = data.model_dump(exclude_unset=True)
    if "country" in updates or "country_code" in updates:
        try:
            updates["country"], updates["country_code"] = normalize_country_fields(
                country=updates.get("country", loc.country),
                country_code=updates.get("country_code", loc.country_code),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    for key, val in updates.items():
        setattr(loc, key, val)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/locations/{location_id}", status_code=204)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    db.delete(loc)
    db.commit()


@router.get("/locations/{location_id}/research-markdown", response_class=PlainTextResponse)
def export_location_research_markdown(location_id: int, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    doc_path = _find_research_doc_path(loc)
    if not doc_path:
        raise HTTPException(
            status_code=404,
            detail=f"Research markdown file not found for {loc.name} ({loc.country}).",
        )

    return doc_path.read_text(encoding="utf-8")
