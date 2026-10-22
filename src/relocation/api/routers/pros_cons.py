from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import ProCon
from relocation.schemas import ProConCreate, ProConOut

router = APIRouter(tags=["pros_cons"])


@router.get("/pros-cons", response_model=list[ProConOut])
def list_pros_cons(
    location_id: Optional[int] = None,
    type: Optional[str] = None,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ProCon)
    if location_id:
        query = query.filter(ProCon.location_id == location_id)
    if provider:
        query = query.filter(ProCon.provider == provider)
    if type:
        query = query.filter(ProCon.type == type)
    return query.all()


@router.get("/locations/{location_id}/pros-cons", response_model=list[ProConOut])
def get_location_pros_cons(location_id: int, db: Session = Depends(get_db)):
    return db.query(ProCon).filter(ProCon.location_id == location_id).all()


@router.post("/pros-cons", response_model=ProConOut, status_code=201)
def create_pro_con(data: ProConCreate, db: Session = Depends(get_db)):
    item = ProCon(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/pros-cons/{item_id}", status_code=204)
def delete_pro_con(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ProCon, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
