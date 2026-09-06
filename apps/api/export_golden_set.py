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
        ).all()

    labeled = [i for i in issues if i.labels]
    unlabeled = [i for i in issues if not i.labels]

    # Prioritize labeled issues — that's what the retrieval-relevance eval actually needs —
    # then pad with unlabeled ones so the corpus is still large enough for meaningful search.
    selected = labeled[:SAMPLE_SIZE]
    remaining_slots = SAMPLE_SIZE - len(selected)
    if remaining_slots > 0:
        selected += unlabeled[:remaining_slots]

    records = [{"repo": issue.repo, "raw": issue.raw_json} for issue in selected]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f)

    print(f"Exported {len(records)} issues ({len(labeled[:SAMPLE_SIZE])} labeled) to {OUTPUT_PATH}")


if __name__ == "__main__":
    run()