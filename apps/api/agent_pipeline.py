"""Core triage pipeline: router -> retrieval -> draft -> critique -> revise loop.
Persists every run to Postgres. Runnable from the CLI, or imported by the API."""

import json
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from db import SessionLocal
from llm_client import chat_json
from models import Issue, TriageResult
from retrieval import retrieve_similar_issues

ROUTER_SYSTEM_PROMPT = """You are a fast triage classifier for GitHub issues on an open-source
TypeScript validation library called zod. Given an issue's title and body, classify it.

Respond with ONLY a JSON object, no other text, matching this shape:
{"category": "bug" | "question" | "feature_request" | "other", "confidence": 0.0-1.0}
"""

DRAFT_SYSTEM_PROMPT = """You are drafting a helpful first response to a GitHub issue on zod,
a TypeScript validation library. You are given the new issue and a list of similar past issues
that were already resolved. Use ONLY the provided past issues as your source of truth — do not
invent information you were not given.

Respond with ONLY a JSON object, no other text, matching this shape:
{
  "likely_duplicate_of": [issue numbers you believe this duplicates, or empty list],
  "suggested_reply": "a short, helpful reply citing specific past issue numbers, e.g. 'This looks similar to #123, where...'",
  "cited_issue_numbers": [issue numbers actually referenced in suggested_reply]
}
"""

CRITIC_SYSTEM_PROMPT = """You are a careful reviewer checking a drafted GitHub issue response
for factual accuracy before it reaches a human. You are given the draft reply and the actual
past-issue summaries it was allowed to cite.

Your ONLY job is to check whether every specific claim, issue number, or fact stated in the
draft reply is actually supported by the provided sources. Do NOT flag the reply for being
incomplete, for not mentioning additional sources, or for style choices — only flag genuine
factual errors or information that was invented and is not present in the sources.

Respond with ONLY a JSON object, no other text, matching this shape:
{"approved": true/false, "problems": ["list of any UNSUPPORTED or FABRICATED claims found — not missing citations"], "confidence": 0.0-1.0}
"""

MAX_REVISIONS = 2


def run_triage(issue_number: int, verbose: bool = True) -> dict:
    session = SessionLocal()
    try:
        issue = session.scalars(select(Issue).where(Issue.number == issue_number)).one_or_none()
    finally:
        session.close()

    if issue is None:
        raise ValueError(f"Issue #{issue_number} not found in the local database.")

    issue_text = f"{issue.title}\n\n{issue.body or ''}"
    if verbose:
        print(f"=== New issue #{issue.number}: {issue.title} ===\n")

    router_result = chat_json(ROUTER_SYSTEM_PROMPT, issue_text)
    if verbose:
        print(f"[Router] {router_result}\n")

    similar = retrieve_similar_issues(issue_text, top_k=5, exclude_number=issue.number)
    if verbose:
        print("[Retrieved similar issues]")
        for s in similar:
            print(f"  #{s['number']} (score={s['score']:.3f}) {s['title']}")
        print()

    similar_numbers = [s["number"] for s in similar]
    lookup_session = SessionLocal()
    try:
        similar_full = lookup_session.scalars(
            select(Issue).where(Issue.repo == issue.repo, Issue.number.in_(similar_numbers))
        ).all()
    finally:
        lookup_session.close()
    body_by_number = {i.number: (i.body or "") for i in similar_full}

    similar_context = "\n\n".join(
        f"#{s['number']}: {s['title']}\n{body_by_number.get(s['number'], '')[:500]}"
        for s in similar
    )

    revision_notes = None
    draft: dict = {}
    critique: dict = {}
    attempts = 0

    for attempt in range(1, MAX_REVISIONS + 2):
        attempts = attempt
        if revision_notes is None:
            draft_input = f"NEW ISSUE:\n{issue_text}\n\nSIMILAR PAST ISSUES:\n{similar_context}"
        else:
            draft_input = (
                f"NEW ISSUE:\n{issue_text}\n\nSIMILAR PAST ISSUES:\n{similar_context}\n\n"
                "YOUR PREVIOUS DRAFT WAS REJECTED FOR THESE REASONS — fix them:\n"
                + "\n".join(f"- {p}" for p in revision_notes)
            )

        draft = chat_json(DRAFT_SYSTEM_PROMPT, draft_input)
        if verbose:
            print(f"[Draft attempt {attempt}] {json.dumps(draft, indent=2)}\n")

        critic_input = f"DRAFT REPLY:\n{draft['suggested_reply']}\n\nALLOWED SOURCES:\n{similar_context}"
        critique = chat_json(CRITIC_SYSTEM_PROMPT, critic_input)
        if verbose:
            print(f"[Critic attempt {attempt}] {critique}\n")

        if critique.get("approved"):
            break
        revision_notes = critique.get("problems", [])

    status = "approved" if critique.get("approved") else "needs_review"

    result = TriageResult(
        repo=issue.repo,
        issue_number=issue.number,
        issue_title=issue.title,
        category=router_result.get("category", "other"),
        router_confidence=float(router_result.get("confidence", 0.0)),
        similar_issue_numbers=similar_numbers,
        attempts=attempts,
        suggested_reply=draft.get("suggested_reply", ""),
        cited_issue_numbers=draft.get("cited_issue_numbers", []),
        critic_approved=bool(critique.get("approved", False)),
        critic_problems=critique.get("problems", []),
        critic_confidence=float(critique.get("confidence", 0.0)),
        status=status,
          created_at=datetime.now(timezone.utc),
    )

    save_session = SessionLocal()
    try:
        save_session.add(result)
        save_session.commit()
        save_session.refresh(result)
        result_id = result.id
    finally:
        save_session.close()

    if verbose:
        verdict = "APPROVED" if status == "approved" else "STILL FLAGGED after revisions"
        print(f"=== Verdict: {verdict} — saved as triage_results.id={result_id} ===")

    return {
        "id": result_id,
        "issue_number": issue.number,
        "status": status,
        "category": router_result.get("category"),
        "suggested_reply": draft.get("suggested_reply"),
        "critic_problems": critique.get("problems", []),
        "attempts": attempts,
    }


if __name__ == "__main__":
    issue_number = int(sys.argv[1]) if len(sys.argv) > 1 else 2888
    run_triage(issue_number)