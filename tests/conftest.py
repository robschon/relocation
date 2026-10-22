import os
import tempfile
from pathlib import Path

# Point the app at a throwaway database BEFORE anything imports relocation.config,
# so no test (or app startup inside TestClient) can touch data/relocation.db.
_TEST_DB = Path(tempfile.mkdtemp(prefix="relocation-tests-")) / "test.db"
os.environ["RELOCATION_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from relocation.database import Base, enable_sqlite_foreign_keys, get_db  # noqa: E402
from relocation.seed import seed_database  # noqa: E402


@pytest.fixture(autouse=True)
def _no_llm_usage_logging(monkeypatch):
    """Never write llm_calls rows to the real database from tests."""
    monkeypatch.setenv("RELOCATION_LLM_USAGE_LOG", "0")


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = enable_sqlite_foreign_keys(
        create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_database(session)
    yield session
    session.close()


@pytest.fixture
def client(db_session, monkeypatch):
    """FastAPI test client with overridden DB dependency."""
    import relocation.api.app as app_module
    from relocation.api.app import app

    monkeypatch.setenv("RELOCATION_AUTO_ENRICH_NEW_LOCATIONS", "0")
    # Tests use an in-memory DB via get_db; skip startup work on the (throwaway) app DB.
    monkeypatch.setattr(app_module, "startup", lambda: None)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
