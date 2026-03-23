from sqlalchemy import func
from sqlalchemy.orm import Session

from relocation.models import Category, Location, Score


def get_fully_scored_location_ids(session: Session) -> set[int]:
    category_count = session.query(func.count(Category.id)).scalar() or 0
    if category_count == 0:
        return {
            location_id
            for (location_id,) in session.query(Location.id).all()
        }

    return {
        location_id
        for (location_id,) in (
            session.query(Score.location_id)
            .group_by(Score.location_id)
            .having(func.count(Score.category_id) == category_count)
            .all()
        )
    }
