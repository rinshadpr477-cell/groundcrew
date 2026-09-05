import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from embeddings import embed_texts

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REPO_OWNER = os.getenv("REPO_OWNER", "colinhacks")
REPO_NAME = os.getenv("REPO_NAME", "zod")
COLLECTION_NAME = f"{REPO_OWNER}_{REPO_NAME}_issues"

_client = QdrantClient(url=QDRANT_URL)


def retrieve_similar_issues(query_text: str, top_k: int = 5, exclude_number: int | None = None) -> list[dict]:
    [vector] = embed_texts([query_text])

    results = _client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=top_k + (1 if exclude_number else 0),
    ).points

    similar = []
    for point in results:
        payload = point.payload
        if exclude_number and payload["number"] == exclude_number:
            continue
        similar.append({**payload, "score": point.score})

    return similar[:top_k]