"use client";

import { useState } from "react";
import type { TriageResult } from "./page";

export function QueueItem({ item }: { item: TriageResult }) {
  const [decision, setDecision] = useState<string | null>(item.human_decision);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function recordDecision(newDecision: "approved" | "rejected") {
    setSubmitting(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/triage/${item.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: newDecision }),
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }

      setDecision(newDecision);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save decision.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <li className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-medium">
          #{item.issue_number}: {item.issue_title}
        </h2>
        <span className="whitespace-nowrap rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
          {item.category}
        </span>
      </div>

      <p className="mt-3 text-sm text-gray-700">{item.suggested_reply}</p>

      {item.critic_problems.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm text-amber-700">
            Critic flagged {item.critic_problems.length} issue{item.critic_problems.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {item.critic_problems.map((problem, i) => (
              <li key={i} className="text-sm text-gray-500">{problem}</li>
            ))}
          </ul>
        </details>
      )}

      <p className="mt-2 text-xs text-gray-400">
        {item.attempts} attempt{item.attempts === 1 ? "" : "s"} · critic confidence {item.critic_confidence.toFixed(2)}
      </p>

      <div className="mt-3 flex items-center gap-2">
        {decision === null ? (
          <>
            <button
              onClick={() => recordDecision("approved")}
              disabled={submitting}
              className="rounded-md border border-green-600 bg-green-50 px-3 py-1.5 text-sm text-green-800 hover:bg-green-100 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => recordDecision("rejected")}
              disabled={submitting}
              className="rounded-md border border-red-600 bg-red-50 px-3 py-1.5 text-sm text-red-800 hover:bg-red-100 disabled:opacity-50"
            >
              Reject
            </button>
          </>
        ) : (
          <span className={`text-sm font-semibold ${decision === "approved" ? "text-green-700" : "text-red-700"}`}>
            Marked {decision}
          </span>
        )}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </li>
  );
}