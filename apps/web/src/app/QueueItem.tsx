"use client";

import { useState } from "react";
import type { TriageResult } from "./page";

const CATEGORY_STYLES: Record<string, string> = {
  bug: "bg-red-500/10 text-red-300 border-red-500/30",
  question: "bg-blue-500/10 text-blue-300 border-blue-500/30",
  feature_request: "bg-purple-500/10 text-purple-300 border-purple-500/30",
  other: "bg-slate-500/10 text-slate-300 border-slate-500/30",
};

function githubUrl(repo: string, issueNumber: number): string {
  return `https://github.com/${repo}/issues/${issueNumber}`;
}

export function QueueItem({ item }: { item: TriageResult }) {
  const [decision, setDecision] = useState<string | null>(item.human_decision);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  async function recordDecision(newDecision: "approved" | "rejected") {
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/triage/${item.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: newDecision }),
      });
      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      setDecision(newDecision);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  const categoryStyle = CATEGORY_STYLES[item.category] ?? CATEGORY_STYLES.other;
  const isPending = item.status === "needs_review" && !decision;
  const issueLink = githubUrl(item.repo, item.issue_number);

  return (
    <li className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <a href={issueLink} target="_blank" rel="noreferrer" className="text-sm font-medium text-slate-200 hover:text-indigo-400">
            #{item.issue_number} {item.issue_title}
          </a>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${categoryStyle}`}>
              {item.category}
            </span>
            <span className="text-xs text-slate-500">
              router confidence {Math.round(item.router_confidence * 100)}%
            </span>
          </div>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
            isPending
              ? "bg-amber-500/10 text-amber-300"
              : item.status === "approved"
                ? "bg-emerald-500/10 text-emerald-300"
                : "bg-slate-500/10 text-slate-300"
          }`}
        >
          {isPending ? "needs review" : item.status}
        </span>
      </div>

      <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
        {item.suggested_reply}
      </p>

      {item.cited_issue_numbers.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {item.cited_issue_numbers.map((n) => {
            const citedLink = githubUrl(item.repo, n);
            return (
              <a key={n} href={citedLink} target="_blank" rel="noreferrer" className="rounded-md border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-xs text-slate-400 hover:border-indigo-500 hover:text-indigo-300">
                cites #{n}
              </a>
            );
          })}
        </div>
      )}

      {item.critic_problems.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-amber-400">
            {item.critic_problems.length} issue{item.critic_problems.length > 1 ? "s" : ""} flagged by critic
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-400">
            {item.critic_problems.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-3">
        <div className="flex flex-wrap gap-3 text-xs text-slate-500">
          <span>{item.attempts} attempt{item.attempts > 1 ? "s" : ""}</span>
          {item.timings?.total_seconds != null && <span>{item.timings.total_seconds.toFixed(1)}s total</span>}
          {item.timings?.router_seconds != null && <span>router {item.timings.router_seconds.toFixed(1)}s</span>}
          {item.timings?.retrieval_seconds != null && <span>retrieval {item.timings.retrieval_seconds.toFixed(1)}s</span>}
        </div>

        {decision ? (
          <span className="text-xs font-medium text-slate-400">Marked {decision}</span>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => recordDecision("approved")}
              disabled={submitting}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => recordDecision("rejected")}
              disabled={submitting}
              className="rounded-md bg-red-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </li>
  );
}