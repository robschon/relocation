from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import VisaInfo
from relocation.schemas import VisaCreate, VisaOut, VisaUpdate

router = APIRouter(tags=["visa"])


@router.get("/visa", response_model=list[VisaOut])
def list_visa(country: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(VisaInfo)
    if country:
        query = query.filter(VisaInfo.country.ilike(f"%{country}%"))
    return query.order_by(VisaInfo.country, VisaInfo.visa_type).all()


@router.get("/visa/{visa_id}", response_model=VisaOut)
def get_visa(visa_id: int, db: Session = Depends(get_db)):
    info = db.get(VisaInfo, visa_id)
    if not info:
        raise HTTPException(404, "Visa info not found")
    return info


@router.post("/visa", response_model=VisaOut, status_code=201)
def create_visa(data: VisaCreate, db: Session = Depends(get_db)):
    info = VisaInfo(**data.model_dump())
    db.add(info)
    db.commit()
    db.refresh(info)
    return info


@router.put("/visa/{visa_id}", response_model=VisaOut)
def update_visa(visa_id: int, data: VisaUpdate, db: Session = Depends(get_db)):
    info = db.get(VisaInfo, visa_id)
    if not info:
        raise HTTPException(404, "Visa info not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(info, key, val)
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
