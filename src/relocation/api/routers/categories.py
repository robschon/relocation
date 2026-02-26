from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import Category
from relocation.schemas import CategoryOut

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.sort_order).all()
