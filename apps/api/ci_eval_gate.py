"""CI eval gate: runs only the retrieval-relevance metric (no LLM calls needed) against
the checked-in golden set, and fails the build if it regresses below a baseline. The
LLM-dependent metrics (router accuracy, pipeline approval) are intentionally NOT run here
— they'd need a paid API call or a local model on every single push, which isn't something
CI should spend money or minutes on for every commit. Those stay manual/periodic instead,
via `python run_eval.py`.

NOTE: the first time this runs in CI, check the printed score in the Actions log and set
BASELINE_THRESHOLD below it with some margin — the golden set is a smaller corpus than
your full local database, so this score won't exactly match your local eval_runs history."""

import sys

from run_eval import eval_retrieval_relevance

BASELINE_THRESHOLD = 0.65  # measured baseline on the golden set: 0.82 (2026-09); some margin for normal noise

def main() -> None:
    result = eval_retrieval_relevance(sample_size=100)
    score = result["any_relevant_at_5"]
    print(f"Retrieval relevance@5: {score} (threshold: {BASELINE_THRESHOLD}, count={result['count']})")
    if score is None:
        print("FAILED: no labeled issues found to evaluate against.")
        sys.exit(1)
    if score < BASELINE_THRESHOLD:
        print("FAILED: retrieval relevance regressed below the baseline threshold.")
        sys.exit(1)
    print("PASSED.")


if __name__ == "__main__":
    main()