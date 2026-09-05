"""Embeds every non-PR issue from Postgres and upserts it into Qdrant.
Safe to re-run — points are upserted by issue number, not duplicated."""

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sqlalchemy import select

from db import SessionLocal
from embeddings import VECTOR_SIZE, embed_texts
from models import Issue

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REPO_OWNER = os.getenv("REPO_OWNER", "colinhacks")
REPO_NAME = os.getenv("REPO_NAME", "zod")
COLLECTION_NAME = f"{REPO_OWNER}_{REPO_NAME}_issues"

BATCH_SIZE = 32


def build_text(issue: Issue) -> str:
    body = issue.body or ""
    return f"{issue.title}\n\n{body}"[:4000]


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def run() -> None:
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client)

    session = SessionLocal()
    try:
        repo_full_name = f"{REPO_OWNER}/{REPO_NAME}"
        issues = session.scalars(
            select(Issue).where(Issue.repo == repo_full_name, Issue.is_pull_request.is_(False))
        ).all()
    finally:
        session.close()

    print(f"Embedding {len(issues)} issues (pull requests excluded)...")

    for start in range(0, len(issues), BATCH_SIZE):
        batch = issues[start : start + BATCH_SIZE]
        texts = [build_text(issue) for issue in batch]
        vectors = embed_texts(texts)

        points = [
            PointStruct(
                id=issue.number,
                vector=vector,
                payload={
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "html_url": issue.html_url,
                    "labels": issue.labels,
                },
            )
            for issue, vector in zip(batch, vectors)
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=points)

        if (start // BATCH_SIZE) % 10 == 0:
            print(f"...{start + len(batch)}/{len(issues)} embedded")

    print(f"Done. {len(issues)} issues indexed into Qdrant collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    run()