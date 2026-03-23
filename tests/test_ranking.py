from relocation.models import Category, Location, Score, User, Weight
from relocation.services.ranking import compute_rankings


def test_ranking_basic(db_session):
    """Test basic ranking computation."""
    loc = db_session.query(Location).filter_by(name="Lima").one()
    cat = db_session.query(Category).filter_by(sort_order=1).one()

    score = Score(location_id=loc.id, category_id=cat.id, score=8)
    db_session.add(score)
    db_session.commit()

    rankings = compute_rankings(db_session)
    assert len(rankings) == 4

    # Lima should be first (only one with scores)
    assert rankings[0].location_name == "Lima"
    assert rankings[0].overall_score > 0


def test_ranking_with_custom_weights(db_session):
    """Test that custom weights affect rankings."""
    loc1 = db_session.query(Location).filter_by(name="Lima").one()
    loc2 = db_session.query(Location).filter_by(name="Fremantle").one()
    cat1 = db_session.query(Category).filter_by(sort_order=1).one()  # Cost of living
    cat2 = db_session.query(Category).filter_by(sort_order=2).one()  # Climate

    # Lima: high cost score, low climate
    db_session.add(Score(location_id=loc1.id, category_id=cat1.id, score=9))
    db_session.add(Score(location_id=loc1.id, category_id=cat2.id, score=3))
    # Fremantle: low cost, high climate
    db_session.add(Score(location_id=loc2.id, category_id=cat1.id, score=3))
    db_session.add(Score(location_id=loc2.id, category_id=cat2.id, score=9))

    husband = db_session.query(User).filter_by(name="husband").one()

    # Husband cares a lot about cost
    cost_weight = db_session.query(Weight).filter_by(user_id=husband.id, category_id=cat1.id).one()
    cost_weight.weight = 10
    climate_weight = db_session.query(Weight).filter_by(user_id=husband.id, category_id=cat2.id).one()
    climate_weight.weight = 1
    db_session.commit()

    rankings = compute_rankings(db_session, user="husband")
    scored = [r for r in rankings if r.overall_score > 0]

    # Lima should win for husband (high cost score * high cost weight)
    assert scored[0].location_name == "Lima"
    assert scored[0].husband_score > scored[1].husband_score


def test_ranking_combined(db_session):
    """Test combined ranking averages both users."""
    loc = db_session.query(Location).filter_by(name="Lima").one()
    cat = db_session.query(Category).filter_by(sort_order=1).one()

    db_session.add(Score(location_id=loc.id, category_id=cat.id, score=8))

    husband = db_session.query(User).filter_by(name="husband").one()
    wife = db_session.query(User).filter_by(name="wife").one()

    h_weight = db_session.query(Weight).filter_by(user_id=husband.id, category_id=cat.id).one()
    w_weight = db_session.query(Weight).filter_by(user_id=wife.id, category_id=cat.id).one()
    h_weight.weight = 10
    w_weight.weight = 2
    db_session.commit()

    rankings = compute_rankings(db_session)
    lima = next(r for r in rankings if r.location_name == "Lima")

    # Husband score = 8*10/10 = 8.0, Wife score = 8*2/2 = 8.0
    # Combined = (8+8)/2 = 8.0
    assert lima.husband_score == 8.0
    assert lima.wife_score == 8.0
    assert lima.overall_score == 8.0


def test_ranking_fully_scored_only(db_session):
    lima = db_session.query(Location).filter_by(name="Lima").one()
    fremantle = db_session.query(Location).filter_by(name="Fremantle").one()
    categories = db_session.query(Category).order_by(Category.sort_order).all()

    for category in categories:
        db_session.add(Score(location_id=lima.id, category_id=category.id, score=8))

    db_session.add(Score(location_id=fremantle.id, category_id=categories[0].id, score=6))
    db_session.commit()

    rankings = compute_rankings(db_session, fully_scored_only=True)

    assert [ranking.location_name for ranking in rankings] == ["Lima"]
    assert len(rankings[0].details) == len(categories)
