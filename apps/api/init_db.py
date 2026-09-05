"""Creates any tables defined in models.py that don't exist yet. Safe to re-run."""

from db import Base, engine
import models  # noqa: F401 — registers all models on Base before create_all

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created (or already existed).")