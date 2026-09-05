"""Quick manual sanity check: embed a query and see the nearest indexed issues."""

import os
import sys

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from embeddings import embed_texts

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REPO_OWNER = os.getenv("REPO_OWNER", "colinhacks")
REPO_NAME = os.getenv("REPO_NAME", "zod")
COLLECTION_NAME = f"{REPO_OWNER}_{REPO_NAME}_issues"


def main() -> None:
    query = " ".join(sys.argv[1:]) or "z.string().email() validation not working for some emails"
    print(f"Query: {query!r}\n")

    [vector] = embed_texts([query])

    client = QdrantClient(url=QDRANT_URL)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=5,
    ).points

    for rank, point in enumerate(results, start=1):
        payload = point.payload
        print(f"{rank}. [#{payload['number']}] ({payload['state']}) score={point.score:.3f}")
        print(f"   {payload['title']}")
        print(f"   {payload['html_url']}\n")


if __name__ == "__main__":
    main()