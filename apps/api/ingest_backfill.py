"""Backfills every issue from the configured repo into Postgres.
Safe to re-run — existing issues get updated, not duplicated."""

import os

from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db import Base, SessionLocal, engine
from github_client import fetch_issues
from models import Issue

load_dotenv()

REPO_OWNER = os.getenv("REPO_OWNER", "colinhacks")
REPO_NAME = os.getenv("REPO_NAME", "zod")


def upsert_issue(session, repo_full_name: str, raw: dict) -> None:
    stmt = pg_insert(Issue).values(
        repo=repo_full_name,
        number=raw["number"],
        github_id=raw["id"],
        title=raw["title"],
        body=raw.get("body"),
        state=raw["state"],
        is_pull_request="pull_request" in raw,
        labels=[label["name"] for label in raw.get("labels", [])],
        html_url=raw["html_url"],
        github_created_at=raw["created_at"],
        github_closed_at=raw.get("closed_at"),
        raw_json=raw,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_issue_repo_number",
        set_={
            "title": stmt.excluded.title,
            "body": stmt.excluded.body,
            "state": stmt.excluded.state,
            "labels": stmt.excluded.labels,
            "github_closed_at": stmt.excluded.github_closed_at,
            "raw_json": stmt.excluded.raw_json,
        },
    )
    session.execute(stmt)


def run() -> None:
    Base.metadata.create_all(bind=engine)
    repo_full_name = f"{REPO_OWNER}/{REPO_NAME}"

    session = SessionLocal()
    count = 0
    try:
        for raw_issue in fetch_issues(REPO_OWNER, REPO_NAME):
            upsert_issue(session, repo_full_name, raw_issue)
            count += 1
            if count % 50 == 0:
                session.commit()
                print(f"...{count} issues ingested so far")
        session.commit()
    finally:
        session.close()

    print(f"Done. {count} issues (including PRs) ingested for {repo_full_name}.")


if __name__ == "__main__":
    run()