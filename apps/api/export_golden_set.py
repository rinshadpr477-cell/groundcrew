"""Exports a sample of already-ingested, closed issues (with their raw GitHub JSON) to a
JSON file that gets checked into the repo. This lets CI evaluate retrieval quality against
a deterministic, real dataset without hitting the live GitHub API or needing your full
local backfill. Run this locally whenever you want to refresh the golden set (e.g. after
ingesting more history) — it isn't run automatically."""

import json

from sqlalchemy import select

from db import SessionLocal
from models import Issue

SAMPLE_SIZE = 500
OUTPUT_PATH = "golden_set.json"


def run() -> None:
    with SessionLocal() as session:
        issues = session.scalars(
            select(Issue)
            .where(Issue.is_pull_request.is_(False), Issue.state == "closed")
            .order_by(Issue.number.desc())
            .limit(SAMPLE_SIZE)
        ).all()
        records = [{"repo": issue.repo, "raw": issue.raw_json} for issue in issues]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f)

    print(f"Exported {len(records)} issues to {OUTPUT_PATH}")


if __name__ == "__main__":
    run()