from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.countries import country_matches_query, normalize_country_fields
from relocation.database import get_db
from relocation.models import VisaInfo
from relocation.schemas import VisaCreate, VisaOut, VisaUpdate
from relocation.services.visa import validate_visa_evidence

router = APIRouter(tags=["visa"])


@router.get("/visa", response_model=list[VisaOut])
def list_visa(country: Optional[str] = None, provider: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(VisaInfo)
    if provider:
        query = query.filter(VisaInfo.provider == provider)
    entries = query.order_by(VisaInfo.country, VisaInfo.visa_type).all()
    if not country:
        return entries
    return [
        entry
        for entry in entries
        if country_matches_query(
            country=entry.country,
            country_code=entry.country_code,
            query=country,
        )
    ]


@router.get("/visa/{visa_id}", response_model=VisaOut)
def get_visa(visa_id: int, db: Session = Depends(get_db)):
    info = db.get(VisaInfo, visa_id)
    if not info:
        raise HTTPException(404, "Visa info not found")
    return info


@router.post("/visa", response_model=VisaOut, status_code=201)
def create_visa(data: VisaCreate, db: Session = Depends(get_db)):
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

    info = VisaInfo(**payload)
    validate_visa_evidence(info)
    db.add(info)
    db.commit()
    db.refresh(info)
    return info


@router.put("/visa/{visa_id}", response_model=VisaOut)
def update_visa(visa_id: int, data: VisaUpdate, db: Session = Depends(get_db)):
    info = db.get(VisaInfo, visa_id)
    if not info:
        raise HTTPException(404, "Visa info not found")

    updates = data.model_dump(exclude_unset=True)
    if "country" in updates or "country_code" in updates:
        try:
            updates["country"], updates["country_code"] = normalize_country_fields(
                country=updates.get("country", info.country),
                country_code=updates.get("country_code", info.country_code),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not updates["country_code"]:
            raise HTTPException(status_code=422, detail="Unknown country. Use a country name or ISO code.")

    for key, val in updates.items():
        setattr(info, key, val)
    validate_visa_evidence(info)
    db.commit()
    db.refresh(info)
    return info


@router.delete("/visa/{visa_id}", status_code=204)
def delete_visa(visa_id: int, db: Session = Depends(get_db)):
    info = db.get(VisaInfo, visa_id)
    if not info:
        raise HTTPException(404, "Visa info not found")
    db.delete(info)
    db.commit()
