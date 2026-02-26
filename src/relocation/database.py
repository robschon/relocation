from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from relocation.config import DATA_DIR, DATABASE_URL


class Base(DeclarativeBase):
    pass


connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Yield a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from relocation import models  # noqa: F401 — registers models with Base

    Base.metadata.create_all(bind=engine)
