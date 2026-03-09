import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Location
from relocation.schemas import LocationCreate, LocationOut, LocationUpdate
from relocation.services.new_location_enrichment import run_location_post_create_pipeline

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
def list_locations(db: Session = Depends(get_db)):
    return db.query(Location).order_by(Location.name).all()


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
    loc = Location(**data.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    background_tasks.add_task(run_location_post_create_pipeline, loc.id)
    return loc


@router.put("/locations/{location_id}", response_model=LocationOut)
def update_location(location_id: int, data: LocationUpdate, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    for key, val in data.model_dump(exclude_unset=True).items():
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
