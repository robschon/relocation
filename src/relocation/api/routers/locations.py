from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Location
from relocation.schemas import LocationCreate, LocationOut, LocationUpdate

router = APIRouter(tags=["locations"])


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
def create_location(data: LocationCreate, db: Session = Depends(get_db)):
    loc = Location(**data.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
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
