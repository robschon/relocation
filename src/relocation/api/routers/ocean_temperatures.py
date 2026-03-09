from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Location, OceanTemperatureMonthly
from relocation.schemas import OceanTemperatureMonthlyOut

router = APIRouter(tags=["ocean_temperatures"])


def _apply_filters(
    query,
    *,
    location_id: Optional[int],
    baseline_start_year: Optional[int],
    baseline_end_year: Optional[int],
    source_dataset: Optional[str],
):
    if location_id is not None:
        query = query.filter(OceanTemperatureMonthly.location_id == location_id)
    if baseline_start_year is not None:
        query = query.filter(OceanTemperatureMonthly.baseline_start_year == baseline_start_year)
    if baseline_end_year is not None:
        query = query.filter(OceanTemperatureMonthly.baseline_end_year == baseline_end_year)
    if source_dataset:
        query = query.filter(OceanTemperatureMonthly.source_dataset == source_dataset)
    return query


@router.get("/ocean-temperatures", response_model=list[OceanTemperatureMonthlyOut])
def list_ocean_temperatures(
    location_id: Optional[int] = None,
    baseline_start_year: Optional[int] = None,
    baseline_end_year: Optional[int] = None,
    source_dataset: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(OceanTemperatureMonthly)
    query = _apply_filters(
        query,
        location_id=location_id,
        baseline_start_year=baseline_start_year,
        baseline_end_year=baseline_end_year,
        source_dataset=source_dataset,
    )
    return query.order_by(
        OceanTemperatureMonthly.location_id.asc(),
        OceanTemperatureMonthly.baseline_end_year.desc(),
        OceanTemperatureMonthly.month.asc(),
    ).all()


@router.get(
    "/locations/{location_id}/ocean-temperatures",
    response_model=list[OceanTemperatureMonthlyOut],
)
def get_location_ocean_temperatures(
    location_id: int,
    baseline_start_year: Optional[int] = None,
    baseline_end_year: Optional[int] = None,
    source_dataset: Optional[str] = None,
    db: Session = Depends(get_db),
):
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(404, "Location not found")

    query = db.query(OceanTemperatureMonthly)
    query = _apply_filters(
        query,
        location_id=location_id,
        baseline_start_year=baseline_start_year,
        baseline_end_year=baseline_end_year,
        source_dataset=source_dataset,
    )
    return query.order_by(
        OceanTemperatureMonthly.baseline_end_year.desc(),
        OceanTemperatureMonthly.month.asc(),
    ).all()
