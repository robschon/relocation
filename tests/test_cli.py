"""Tests for CLI commands using Typer's CliRunner."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner

from relocation.database import Base
from relocation.seed import seed_database

runner = CliRunner()

# All modules that import SessionLocal and need patching
_SESSION_LOCAL_TARGETS = [
    "relocation.cli.main.SessionLocal",
    "relocation.cli.locations.SessionLocal",
    "relocation.cli.categories.SessionLocal",
    "relocation.cli.scores.SessionLocal",
    "relocation.cli.weights.SessionLocal",
    "relocation.cli.research.SessionLocal",
    "relocation.cli.pros_cons.SessionLocal",
    "relocation.cli.visa.SessionLocal",
    "relocation.cli.rank.SessionLocal",
    "relocation.cli.profile.SessionLocal",
]


@pytest.fixture
def cli_session():
    """Create an in-memory DB and patch SessionLocal everywhere in the CLI."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    seed_database(session)
    session.close()

    # Patch SessionLocal in every CLI module to use the test engine
    patches = [patch(target, TestSession) for target in _SESSION_LOCAL_TARGETS]
    for p in patches:
        p.start()
    yield TestSession
    for p in patches:
        p.stop()


@pytest.fixture
def app():
    from relocation.cli.main import app

    return app


# --- Init ---


def test_init(app, cli_session):
    # init is already seeded; running again should succeed idempotently
    with patch("relocation.cli.main.init_db"):
        result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Database initialized" in result.output


# --- Locations ---


def test_location_list(app, cli_session):
    result = runner.invoke(app, ["location", "list"])
    assert result.exit_code == 0
    assert "Lima" in result.output
    assert "Fremantle" in result.output
    assert "Osa Peninsula" in result.output
    assert "Baja Peninsula" in result.output


def test_location_add(app, cli_session):
    result = runner.invoke(app, ["location", "add", "Lisbon", "Portugal", "--region", "Europe"])
    assert result.exit_code == 0
    assert "Lisbon" in result.output
    assert "Portugal" in result.output

    # Verify it appears in list
    result = runner.invoke(app, ["location", "list"])
    assert "Lisbon" in result.output


def test_location_show_by_name(app, cli_session):
    result = runner.invoke(app, ["location", "show", "Lima"])
    assert result.exit_code == 0
    assert "Lima" in result.output
    assert "Peru" in result.output


def test_location_show_by_id(app, cli_session):
    result = runner.invoke(app, ["location", "show", "1"])
    assert result.exit_code == 0


def test_location_remove(app, cli_session):
    result = runner.invoke(app, ["location", "remove", "Lima", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output

    # Verify it's gone
    result = runner.invoke(app, ["location", "list"])
    assert "Lima" not in result.output


def test_location_show_not_found(app, cli_session):
    result = runner.invoke(app, ["location", "show", "Atlantis"])
    assert result.exit_code != 0


# --- Categories ---


def test_category_list(app, cli_session):
    result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0
    assert "Cost of living" in result.output
    assert "Climate" in result.output
    assert "Healthcare" in result.output


# --- Scores ---


def test_score_set_and_list(app, cli_session):
    result = runner.invoke(app, ["score", "set", "Lima", "cost of living", "7", "--notes", "Affordable"])
    assert result.exit_code == 0
    assert "Lima" in result.output
    assert "7" in result.output

    result = runner.invoke(app, ["score", "list", "--location", "Lima"])
    assert result.exit_code == 0
    assert "7" in result.output


def test_score_update(app, cli_session):
    runner.invoke(app, ["score", "set", "Lima", "cost of living", "7"])
    result = runner.invoke(app, ["score", "set", "Lima", "cost of living", "9"])
    assert result.exit_code == 0
    assert "Updated" in result.output
    assert "9" in result.output


def test_score_invalid_range(app, cli_session):
    result = runner.invoke(app, ["score", "set", "Lima", "cost of living", "11"])
    assert result.exit_code != 0


def test_score_matrix(app, cli_session):
    runner.invoke(app, ["score", "set", "Lima", "cost of living", "7"])
    result = runner.invoke(app, ["score", "matrix"])
    assert result.exit_code == 0
    assert "Score Matrix" in result.output
    assert "7" in result.output


# --- Weights ---


def test_weight_set_and_list(app, cli_session):
    result = runner.invoke(app, ["weight", "set", "husband", "cost of living", "8"])
    assert result.exit_code == 0
    assert "Updated" in result.output  # Already seeded at 5

    result = runner.invoke(app, ["weight", "list", "--user", "husband"])
    assert result.exit_code == 0
    assert "8" in result.output


def test_weight_invalid_range(app, cli_session):
    result = runner.invoke(app, ["weight", "set", "husband", "cost of living", "11"])
    assert result.exit_code != 0


def test_weight_invalid_user(app, cli_session):
    result = runner.invoke(app, ["weight", "set", "nobody", "cost of living", "5"])
    assert result.exit_code != 0


def test_weight_matrix(app, cli_session):
    result = runner.invoke(app, ["weight", "matrix"])
    assert result.exit_code == 0
    assert "Husband" in result.output
    assert "Wife" in result.output


# --- Research ---


def test_research_add_and_list(app, cli_session):
    result = runner.invoke(app, ["research", "add", "Lima", "--content", "Great food scene"])
    assert result.exit_code == 0
    assert "Lima" in result.output

    result = runner.invoke(app, ["research", "list", "--location", "Lima"])
    assert result.exit_code == 0
    assert "Great food scene" in result.output


def test_research_show(app, cli_session):
    runner.invoke(app, ["research", "add", "Lima", "--content", "Detailed research content here"])
    result = runner.invoke(app, ["research", "show", "1"])
    assert result.exit_code == 0
    assert "Detailed research content here" in result.output


def test_research_remove(app, cli_session):
    runner.invoke(app, ["research", "add", "Lima", "--content", "Temp note"])
    result = runner.invoke(app, ["research", "remove", "1"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_research_with_category(app, cli_session):
    result = runner.invoke(
        app,
        ["research", "add", "Lima", "--content", "Cheap rent", "--category", "cost of living", "--source", "Numbeo"],
    )
    assert result.exit_code == 0


# --- Pros/Cons ---


def test_pros_cons_add_and_list(app, cli_session):
    runner.invoke(app, ["pros-cons", "add-pro", "Lima", "Amazing food"])
    runner.invoke(app, ["pros-cons", "add-con", "Lima", "Air pollution"])

    result = runner.invoke(app, ["pros-cons", "list", "--location", "Lima"])
    assert result.exit_code == 0
    assert "Amazing food" in result.output
    assert "Air pollution" in result.output


def test_pros_cons_with_category(app, cli_session):
    result = runner.invoke(app, ["pros-cons", "add-pro", "Lima", "World class cuisine", "--category", "food"])
    assert result.exit_code == 0
    assert "Lima" in result.output


def test_pros_cons_remove(app, cli_session):
    runner.invoke(app, ["pros-cons", "add-pro", "Lima", "Temp pro"])
    result = runner.invoke(app, ["pros-cons", "remove", "1"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


# --- Visa ---


def test_visa_add_and_list(app, cli_session):
    result = runner.invoke(
        app,
        ["visa", "add", "Peru", "Rentista Visa", "--desc", "Income-based visa", "--timeline", "3-6 months"],
    )
    assert result.exit_code == 0
    assert "Peru" in result.output

    result = runner.invoke(app, ["visa", "list"])
    assert result.exit_code == 0
    assert "Peru" in result.output
    assert "Rentista" in result.output


def test_visa_list_filter(app, cli_session):
    runner.invoke(app, ["visa", "add", "Peru", "Rentista Visa"])
    runner.invoke(app, ["visa", "add", "Mexico", "Temporary Resident"])

    result = runner.invoke(app, ["visa", "list", "--country", "Peru"])
    assert result.exit_code == 0
    assert "Peru" in result.output
    assert "Mexico" not in result.output


def test_visa_show(app, cli_session):
    runner.invoke(
        app,
        ["visa", "add", "Peru", "Rentista Visa", "--desc", "Income visa", "--cost", "$500", "--notes", "Renewable"],
    )
    result = runner.invoke(app, ["visa", "show", "1"])
    assert result.exit_code == 0
    assert "Peru" in result.output
    assert "$500" in result.output
    assert "Renewable" in result.output


def test_visa_show_not_found(app, cli_session):
    result = runner.invoke(app, ["visa", "show", "999"])
    assert result.exit_code != 0


# --- Rankings ---


def test_rank_default(app, cli_session):
    # Set some scores so ranking is meaningful
    runner.invoke(app, ["score", "set", "Lima", "cost of living", "8"])
    runner.invoke(app, ["score", "set", "Fremantle", "cost of living", "5"])

    result = runner.invoke(app, ["rank"])
    assert result.exit_code == 0
    assert "Lima" in result.output
    assert "Fremantle" in result.output


def test_rank_by_user(app, cli_session):
    runner.invoke(app, ["score", "set", "Lima", "cost of living", "8"])
    result = runner.invoke(app, ["rank", "--user", "husband"])
    assert result.exit_code == 0
    assert "Husband" in result.output


def test_rank_detailed(app, cli_session):
    runner.invoke(app, ["score", "set", "Lima", "cost of living", "8"])
    result = runner.invoke(app, ["rank", "--detailed"])
    assert result.exit_code == 0
    assert "Cost of living" in result.output


def test_rank_invalid_user(app, cli_session):
    result = runner.invoke(app, ["rank", "--user", "nobody"])
    assert result.exit_code != 0


# --- Profile ---


def test_profile_show_empty(app, cli_session):
    result = runner.invoke(app, ["profile", "show"])
    assert result.exit_code == 0
    assert "No profile data" in result.output


def test_profile_export_empty(app, cli_session):
    result = runner.invoke(app, ["profile", "export"])
    assert result.exit_code == 0


# --- Integration: end-to-end workflow ---


def test_full_workflow(app, cli_session):
    """Test a realistic workflow: add location, set scores, set weights, rank."""
    # Add a new location
    runner.invoke(app, ["location", "add", "Lisbon", "Portugal"])

    # Set scores for two locations
    runner.invoke(app, ["score", "set", "Lisbon", "cost of living", "6"])
    runner.invoke(app, ["score", "set", "Lisbon", "climate", "9"])
    runner.invoke(app, ["score", "set", "Lima", "cost of living", "8"])
    runner.invoke(app, ["score", "set", "Lima", "climate", "6"])

    # Adjust weights
    runner.invoke(app, ["weight", "set", "husband", "climate", "9"])
    runner.invoke(app, ["weight", "set", "wife", "cost of living", "8"])

    # Add pros/cons
    runner.invoke(app, ["pros-cons", "add-pro", "Lisbon", "Beautiful city"])
    runner.invoke(app, ["pros-cons", "add-con", "Lisbon", "Getting expensive"])

    # Add research
    runner.invoke(app, ["research", "add", "Lisbon", "--content", "Good healthcare system"])

    # Add visa info
    runner.invoke(app, ["visa", "add", "Portugal", "D7 Visa", "--desc", "Passive income visa"])

    # Check rankings
    result = runner.invoke(app, ["rank", "--detailed"])
    assert result.exit_code == 0
    assert "Lisbon" in result.output
    assert "Lima" in result.output

    # Show location with all data
    result = runner.invoke(app, ["location", "show", "Lisbon"])
    assert result.exit_code == 0
    assert "Beautiful city" in result.output
    assert "Getting expensive" in result.output
