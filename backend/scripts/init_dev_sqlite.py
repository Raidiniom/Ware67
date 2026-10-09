"""Create every table in a local SQLite file for development, so you can work
without touching the shared MySQL database.

Run from backend/, with DATABASE_URL in backend/.env set to:

    DATABASE_URL=sqlite:///./db.sqlite3

    python scripts/init_dev_sqlite.py

(db.sqlite3 is already gitignored.) Running it again is safe: it only creates
tables that don't exist yet. Delete db.sqlite3 to start over.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402,F401 - registers all SQLAlchemy models
from app.core.config import settings  # noqa: E402
from app.db.base_class import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


def main() -> int:
    # Never run this against the shared MySQL database.
    if not settings.DATABASE_URL.startswith("sqlite"):
        print("DATABASE_URL is not SQLite; refusing to touch it. See the docstring.")
        return 1
    Base.metadata.create_all(engine)
    print(f"Tables ready in {settings.DATABASE_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
