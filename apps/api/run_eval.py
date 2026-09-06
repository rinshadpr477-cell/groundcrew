"""Evaluation harness. Measures three things against real, derivable ground
truth already present in our own data — nothing fabricated:
1. Retrieval relevance (label-overlap proxy — true duplicate detection would
   need issue comments, which the Issues API doesn't include).
2. Router category accuracy vs. maintainer-applied GitHub labels.
3. End-to-end draft/critic approval rate, attempts, and latency."""

import os
import sys
import time

from dotenv import load_dotenv
from sqlalchemy import select

from agent_pipeline import ROUTER_SYSTEM_PROMPT, run_triage
from db import SessionLocal
from llm_client import chat_json
from models import EvalRun, Issue
from retrieval import retrieve_similar_issues

load_dotenv()

REPO_OWNER = os.getenv("REPO_OWNER", "colinhacks")
REPO_NAME = os.getenv("REPO_NAME", "zod")
REPO = f"{REPO_OWNER}/{REPO_NAME}"
LLM_MODEL = os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

LABEL_TO_CATEGORY = {
    "bug": "bug",
    "question": "question",
    "enhancement": "feature_request",
    "feature": "feature_request",
}


def category_from_labels(labels: list[str]) -> str | None:
    for label in labels:
        mapped = LABEL_TO_CATEGORY.get(label.lower())
        if mapped:
            return mapped
    return None


def eval_retrieval_relevance(sample_size: int = 100) -> dict:
    session = SessionLocal()
    try:
        issues = session.scalars(
            select(Issue)
            .where(Issue.repo == REPO, Issue.is_pull_request.is_(False))
            .order_by(Issue.number.desc())
        ).all()
    finally:
        session.close()

    labeled_issues = [i for i in issues if i.labels][:sample_size]
    if not labeled_issues:
        return {"any_relevant_at_5": None, "count": 0}

    hits = 0
    for issue in labeled_issues:
        query_text = f"{issue.title}\n\n{issue.body or ''}"
        similar = retrieve_similar_issues(query_text, top_k=5, exclude_number=issue.number)
        similar_numbers = [s["number"] for s in similar]

        lookup = SessionLocal()
        try:
            similar_full = lookup.scalars(
                select(Issue).where(Issue.repo == REPO, Issue.number.in_(similar_numbers))
            ).all()
        finally:
            lookup.close()

        query_labels = {label.lower() for label in issue.labels}
        if any(query_labels.intersection(label.lower() for label in s.labels) for s in similar_full):
            hits += 1

    return {"any_relevant_at_5": hits / len(labeled_issues), "count": len(labeled_issues)}


def eval_router_accuracy(sample_size: int = 40) -> dict:
    session = SessionLocal()
    try:
        issues = session.scalars(
            select(Issue)
            .where(Issue.repo == REPO, Issue.is_pull_request.is_(False))
            .order_by(Issue.number.desc())
        ).all()
    finally:
        session.close()

    labeled = []
    for issue in issues:
        ground_truth = category_from_labels(issue.labels or [])
        if ground_truth:
            labeled.append((issue, ground_truth))
        if len(labeled) >= sample_size:
            break

    if not labeled:
        return {"accuracy": None, "count": 0}

    correct = 0
    for issue, ground_truth in labeled:
        issue_text = f"{issue.title}\n\n{issue.body or ''}"
        prediction = chat_json(ROUTER_SYSTEM_PROMPT, issue_text)
        if prediction.get("category") == ground_truth:
            correct += 1

    return {"accuracy": correct / len(labeled), "count": len(labeled)}


def eval_pipeline_faithfulness(sample_size: int) -> dict:
    session = SessionLocal()
    try:
        issues = session.scalars(
            select(Issue)
            .where(Issue.repo == REPO, Issue.is_pull_request.is_(False), Issue.state == "closed")
            .order_by(Issue.number.desc())
            .limit(sample_size)
        ).all()
    finally:
        session.close()

    approvals = 0
    total_attempts = 0
    total_time = 0.0

    for issue in issues:
        start = time.monotonic()
        summary = run_triage(issue.number, verbose=False)
        elapsed = time.monotonic() - start

        total_time += elapsed
        total_attempts += summary["attempts"]
        if summary["status"] == "approved":
            approvals += 1

        print(f"  #{issue.number}: {summary['status']} in {summary['attempts']} attempt(s), {elapsed:.1f}s")

    count = len(issues)
    return {
        "approval_rate": approvals / count if count else None,
        "avg_attempts": total_attempts / count if count else None,
        "avg_latency_seconds": total_time / count if count else None,
        "count": count,
    }


def run_full_eval(pipeline_sample_size: int) -> None:
    print("=== Retrieval relevance@5 (label-overlap proxy) ===")
    retrieval_result = eval_retrieval_relevance()
    print(f"  {retrieval_result}\n")

    print("=== Router category accuracy (vs. real GitHub labels) ===")
    router_result = eval_router_accuracy()
    print(f"  {router_result}\n")

    print(f"=== Full pipeline approval rate ({pipeline_sample_size} issues, real LLM calls — this takes a while) ===")
    pipeline_result = eval_pipeline_faithfulness(pipeline_sample_size)
    print(f"  {pipeline_result}\n")

    eval_run = EvalRun(
        repo=REPO,
        llm_model=LLM_MODEL,
        retrieval_relevance_at_5=retrieval_result["any_relevant_at_5"],
        retrieval_eval_count=retrieval_result["count"],
        category_accuracy=router_result["accuracy"],
        category_eval_count=router_result["count"],
        approval_rate=pipeline_result["approval_rate"],
        avg_attempts=pipeline_result["avg_attempts"],
        avg_latency_seconds=pipeline_result["avg_latency_seconds"],
        pipeline_eval_count=pipeline_result["count"],
        details={"retrieval": retrieval_result, "router": router_result, "pipeline": pipeline_result},
    )

    session = SessionLocal()
    try:
        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)
        run_id = eval_run.id
    finally:
        session.close()

    print(f"=== Eval run saved as eval_runs.id={run_id} ===")


if __name__ == "__main__":
    pipeline_sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    run_full_eval(pipeline_sample_size)