import os
import time
from typing import Iterator

import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN is not set — check apps/api/.env")

API_BASE = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def fetch_issues(owner: str, repo: str, state: str = "all", per_page: int = 100) -> Iterator[dict]:
    """Yield every issue (GitHub mixes pull requests into this endpoint too)
    for a repo, oldest first, following pagination and backing off on rate limits."""
    url = f"{API_BASE}/repos/{owner}/{repo}/issues"
    params = {"state": state, "per_page": per_page, "sort": "created", "direction": "asc"}

    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        while url:
            response = client.get(url, params=params)

            if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                reset_at = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait_seconds = max(reset_at - time.time(), 1)
                print(f"Rate limited — waiting {wait_seconds:.0f}s for reset.")
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            for issue in response.json():
                yield issue

            url = response.links.get("next", {}).get("url")
            params = None