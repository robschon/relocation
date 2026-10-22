from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Country
from relocation.schemas import CountryOut

router = APIRouter(tags=["countries"])


@router.get("/countries", response_model=list[CountryOut])
def list_countries(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.name).all()
