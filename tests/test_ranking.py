from relocation.models import CountryScore, Category, Location, Score, User, Weight
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

    partner_a = db_session.query(User).filter_by(name="partner_a").one()

    # Partner A cares a lot about cost
    cost_weight = db_session.query(Weight).filter_by(user_id=partner_a.id, category_id=cat1.id).one()
    cost_weight.weight = 10
    climate_weight = db_session.query(Weight).filter_by(user_id=partner_a.id, category_id=cat2.id).one()
    climate_weight.weight = 1
    db_session.commit()

    rankings = compute_rankings(db_session, user="partner_a")
    scored = [r for r in rankings if r.overall_score > 0]

    # Lima should win for Partner A (high cost score * high cost weight)
    assert scored[0].location_name == "Lima"
    assert scored[0].user_scores[partner_a.id] > scored[1].user_scores[partner_a.id]


def test_ranking_combined(db_session):
    """Test combined ranking averages both users."""
    loc = db_session.query(Location).filter_by(name="Lima").one()
    cat = db_session.query(Category).filter_by(sort_order=1).one()

    db_session.add(Score(location_id=loc.id, category_id=cat.id, score=8))

    partner_a = db_session.query(User).filter_by(name="partner_a").one()
    partner_b = db_session.query(User).filter_by(name="partner_b").one()

    h_weight = db_session.query(Weight).filter_by(user_id=partner_a.id, category_id=cat.id).one()
    w_weight = db_session.query(Weight).filter_by(user_id=partner_b.id, category_id=cat.id).one()
    h_weight.weight = 10
    w_weight.weight = 2
    db_session.commit()

    rankings = compute_rankings(db_session)
    lima = next(r for r in rankings if r.location_name == "Lima")

    # Partner A's score = 8*10/10 = 8.0, Partner B's = 8*2/2 = 8.0
    # Combined = (8+8)/2 = 8.0
    assert lima.user_scores[partner_a.id] == 8.0
    assert lima.user_scores[partner_b.id] == 8.0
    assert lima.overall_score == 8.0


def test_ranking_fully_scored_only(db_session):
    lima = db_session.query(Location).filter_by(name="Lima").one()
    fremantle = db_session.query(Location).filter_by(name="Fremantle").one()
    categories = db_session.query(Category).order_by(Category.sort_order).all()

    for category in categories:
        if category.scope == "country":
            db_session.add(CountryScore(country_code=lima.country_code, category_id=category.id, score=8))
        else:
            db_session.add(Score(location_id=lima.id, category_id=category.id, score=8))

    db_session.add(Score(location_id=fremantle.id, category_id=categories[0].id, score=6))
    db_session.commit()

    rankings = compute_rankings(db_session, fully_scored_only=True)

    assert [ranking.location_name for ranking in rankings] == ["Lima"]
    assert len(rankings[0].details) == len(categories)


def test_ranking_coverage_and_unknown_user(db_session):
    import pytest

    lima = db_session.query(Location).filter_by(name="Lima").one()
    food = db_session.query(Category).filter_by(key="food").one()
    db_session.add(Score(location_id=lima.id, category_id=food.id, score=9))
    db_session.commit()

    ranking = next(r for r in compute_rankings(db_session) if r.location_name == "Lima")
    total = db_session.query(Category).count()
    assert (ranking.scored_categories, ranking.total_categories) == (1, total)
    assert ranking.coverage == 1 / total

    with pytest.raises(ValueError):
        compute_rankings(db_session, user="nobody")


def test_derived_scores_serve_every_provider_and_manual_wins(db_session):
    from relocation.services.derived_scores import write_derived_score
    from relocation.services.effective_scores import effective_scores

    lima = db_session.query(Location).filter_by(name="Lima").one()
    swim = db_session.query(Category).filter_by(key="swimming").one()
    db_session.add(Score(location_id=lima.id, category_id=swim.id, score=3, method="manual", provider="openai"))
    db_session.commit()
    assert write_derived_score(db_session, location_id=lima.id, category_id=swim.id, score=8, notes="x") == "kept_manual"

    db_session.query(Score).filter_by(location_id=lima.id, category_id=swim.id).delete()
    db_session.commit()
    assert write_derived_score(db_session, location_id=lima.id, category_id=swim.id, score=8, notes="x") == "created"
    db_session.commit()

    for provider in ("openai", "gemini"):
        rows = [s for s in effective_scores(db_session, provider=provider, location_id=lima.id) if s.category_id == swim.id]
        assert [(r.score, r.method) for r in rows] == [(8, "derived")]


def test_llm_scores_rejected_for_derived_categories(db_session):
    import pytest

    lima = db_session.query(Location).filter_by(name="Lima").one()
    swim = db_session.query(Category).filter_by(key="swimming").one()
    db_session.add(Score(location_id=lima.id, category_id=swim.id, score=5, method="llm"))
    with pytest.raises(ValueError, match="computed from data"):
        db_session.commit()
    db_session.rollback()
