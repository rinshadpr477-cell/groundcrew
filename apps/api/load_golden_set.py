"""Loads the checked-in golden_set.json into Postgres. Used by CI (and available locally)
so evaluation doesn't depend on live GitHub API access or rate limits."""

import json

from db import Base, SessionLocal, engine
from ingest_backfill import upsert_issue
import models  # noqa: F401 — registers models on Base before create_all

INPUT_PATH = "golden_set.json"


def run() -> None:
    Base.metadata.create_all(bind=engine)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    session = SessionLocal()
    try:
        for i, record in enumerate(records, start=1):
            upsert_issue(session, record["repo"], record["raw"])
            if i % 50 == 0:
                session.commit()
        session.commit()
    finally:
        session.close()

    print(f"Loaded {len(records)} issues from {INPUT_PATH}")


if __name__ == "__main__":
    run()