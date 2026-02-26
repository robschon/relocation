from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from relocation.database import get_db
from relocation.models import ProfileResponse
from relocation.profile_builder.formatter import format_profile
from relocation.profile_builder.questions import QUESTIONS
from relocation.schemas import ProfileResponseCreate, ProfileResponseOut

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=list[ProfileResponseOut])
def get_profile(db: Session = Depends(get_db)):
    return db.query(ProfileResponse).order_by(ProfileResponse.section, ProfileResponse.id).all()


@router.post("/profile", response_model=ProfileResponseOut, status_code=201)
def upsert_profile_response(data: ProfileResponseCreate, db: Session = Depends(get_db)):
    """Create or update a profile response by question_key."""
    existing = db.query(ProfileResponse).filter_by(question_key=data.question_key).first()
    if existing:
        existing.answer = data.answer
        db.commit()
        db.refresh(existing)
        return existing

    # Find the question definition to get section and question text
    q_def = next((q for q in QUESTIONS if q.key == data.question_key), None)
    if not q_def:
        # Allow arbitrary keys
        entry = ProfileResponse(
            section="Custom",
            question_key=data.question_key,
            question=data.question_key,
            answer=data.answer,
        )
    else:
        entry = ProfileResponse(
            section=q_def.section,
            question_key=data.question_key,
            question=q_def.question,
            answer=data.answer,
        )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/profile/export", response_class=PlainTextResponse)
def export_profile(db: Session = Depends(get_db)):
    """Export the profile as formatted markdown."""
    return format_profile(db)
