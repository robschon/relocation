from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import User
from relocation.schemas import UserOut

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.name).all()
