import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_URL = os.environ.get(
    "RELOCATION_DATABASE_URL",
    f"sqlite:///{DATA_DIR / 'relocation.db'}",
)
