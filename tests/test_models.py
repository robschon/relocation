from relocation.models import Category, Location, Score, User, Weight


def test_seed_data_present(db_session):
    """Verify seed data was created correctly."""
    users = db_session.query(User).all()
    assert len(users) == 2
    assert {(u.name, u.display_name) for u in users} == {("partner_a", "Partner A"), ("partner_b", "Partner B")}

    categories = db_session.query(Category).all()
    assert len(categories) == 15

    locations = db_session.query(Location).all()
    assert len(locations) == 4
    names = {loc.name for loc in locations}
    assert "Osa Peninsula" in names
    assert "Lima" in names

    weights = db_session.query(Weight).all()
    assert len(weights) == 30  # 2 users * 15 categories


def test_score_creation(db_session):
    """Test creating a score with constraints."""
    loc = db_session.query(Location).filter_by(name="Lima").one()
    cat = db_session.query(Category).first()

    score = Score(location_id=loc.id, category_id=cat.id, score=7, notes="Test")
    db_session.add(score)
    db_session.commit()

    assert score.id is not None
    assert score.score == 7
    assert score.notes == "Test"


def test_location_cascade_delete(db_session):
    """Deleting a location should cascade to scores."""
    loc = db_session.query(Location).filter_by(name="Lima").one()
    cat = db_session.query(Category).first()

    score = Score(location_id=loc.id, category_id=cat.id, score=5)
    db_session.add(score)
    db_session.commit()

    db_session.delete(loc)
    db_session.commit()

    assert db_session.query(Score).filter_by(location_id=loc.id).count() == 0


def test_tests_never_use_the_real_database():
    from relocation.config import DATA_DIR, DATABASE_URL

    assert str(DATA_DIR / "relocation.db") not in DATABASE_URL
