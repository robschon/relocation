import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from relocation.countries import normalize_country_fields
from relocation.database import get_db
from relocation.export_markdown import build_markdown
from relocation.models import DEFAULT_PROVIDER, Location
from relocation.schemas import (
    LocationCandidateSearchOut,
    LocationCreate,
    LocationOut,
    LocationUpdate,
)
from relocation.services.location_candidates import search_location_candidates
from relocation.services.new_location_enrichment import run_location_post_create_pipeline
from relocation.services.research_versions import current_research_location_ids
from relocation.services.scoring import get_fully_scored_location_ids

router = APIRouter(tags=["locations"])
def _with_research_flag(db: Session, locations: list[Location]) -> list[Location]:
    current = current_research_location_ids(db)
    for loc in locations:
        loc.research_current = loc.id in current  # read by LocationOut
    return locations


@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    fully_scored_only: bool = False,
    current_research_only: bool = False,
    provider: str = DEFAULT_PROVIDER,
    db: Session = Depends(get_db),
):
    """List locations. current_research_only hides locations with research from an older pipeline version."""
    query = db.query(Location)
    if fully_scored_only:
        fully_scored_location_ids = get_fully_scored_location_ids(db, provider=provider)
        if not fully_scored_location_ids:
            return []
        query = query.filter(Location.id.in_(fully_scored_location_ids))
    locations = _with_research_flag(db, query.order_by(Location.name).all())
    if current_research_only:
        locations = [loc for loc in locations if loc.research_current]
    return locations


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
    return _with_research_flag(db, [loc])[0]


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
    if not payload["country_code"]:
        raise HTTPException(status_code=422, detail=f"Unknown country '{data.country}'. Use a country name or ISO code.")

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
        if not updates["country_code"]:
            raise HTTPException(status_code=422, detail="Unknown country. Use a country name or ISO code.")

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
    # Built from the database, so it is always current and never depends on research/*.md filenames.
    _path, content = build_markdown(db, loc)
    return content
