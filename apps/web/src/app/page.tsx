import { QueueItem } from "./QueueItem";

export interface TriageResult {
  id: number;
  repo: string;
  issue_number: number;
  issue_title: string;
  category: string;
  router_confidence: number;
  similar_issue_numbers: number[];
  attempts: number;
  suggested_reply: string;
  cited_issue_numbers: number[];
  critic_approved: boolean;
  critic_problems: string[];
  critic_confidence: number;
  status: string;
  human_decision: string | null;
  timings: {
    router_seconds?: number;
    retrieval_seconds?: number;
    attempts?: { attempt: number; draft_seconds: number; critic_seconds: number }[];
    total_seconds?: number;
  } | null;
  created_at: string;
}

interface EvalSummary {
  llm_model: string;
  retrieval_relevance_at_5: number | null;
  category_accuracy: number | null;
  approval_rate: number | null;
  avg_latency_seconds: number | null;
  pipeline_eval_count: number;
  created_at: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getQueue(): Promise<TriageResult[]> {
  const response = await fetch(`${API_URL}/triage/queue`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load the review queue (${response.status})`);
  }
  return response.json();
}

async function getLatestEval(): Promise<EvalSummary | null> {
  try {
    const response = await fetch(`${API_URL}/eval/latest`, { cache: "no-store" });
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div className="text-2xl font-semibold text-slate-50">{value}</div>
      <div className="mt-1 text-xs uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

export default async function QueuePage() {
  let items: TriageResult[] = [];
  let loadError: string | null = null;
  try {
    items = await getQueue();
  } catch (err) {
    loadError = err instanceof Error ? err.message : "Something went wrong loading the queue.";
  }
  const evalSummary = await getLatestEval();

  const pendingCount = items.filter((i) => i.status === "needs_review" && !i.human_decision).length;
  const approvedCount = items.filter((i) => i.status === "approved").length;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-4 py-10">
        <div className="mb-8">
          <div className="flex items-center gap-2 text-sm font-medium text-indigo-400">
            <span className="h-2 w-2 rounded-full bg-indigo-400" />
            Groundcrew
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
            Autonomous issue triage
          </h1>
          <p className="mt-2 max-w-xl text-sm text-slate-400">
            Router → retrieval → draft → critic pipeline running against real GitHub issues.
            Anything the critic can&apos;t verify lands here for a human to decide.
          </p>
        </div>

        {evalSummary && (
          <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard
              label="Approval rate"
              value={evalSummary.approval_rate != null ? `${Math.round(evalSummary.approval_rate * 100)}%` : "—"}
            />
            <StatCard
              label="Router accuracy"
              value={evalSummary.category_accuracy != null ? `${Math.round(evalSummary.category_accuracy * 100)}%` : "—"}
            />
            <StatCard
              label="Retrieval@5"
              value={evalSummary.retrieval_relevance_at_5 != null ? evalSummary.retrieval_relevance_at_5.toFixed(2) : "—"}
            />
            <StatCard
              label="Avg latency"
              value={evalSummary.avg_latency_seconds != null ? `${evalSummary.avg_latency_seconds.toFixed(0)}s` : "—"}
            />
          </div>
        )}

        <div className="mb-4 flex items-center gap-4 text-sm text-slate-400">
          <span>{items.length} total</span>
          <span className="text-amber-400">{pendingCount} pending review</span>
          <span className="text-emerald-400">{approvedCount} approved</span>
        </div>

        {loadError && (
          <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-300">
            Couldn&apos;t reach the API: {loadError}. Is the FastAPI server running on port 8000?
          </p>
        )}
        {!loadError && items.length === 0 && (
          <p className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-6 text-center text-sm text-slate-500">
            Nothing triaged yet. Run <code className="text-slate-300">python agent_pipeline.py &lt;issue_number&gt;</code> to see one here.
          </p>
        )}

        <ul className="flex flex-col gap-4">
          {items.map((item) => (
            <QueueItem key={item.id} item={item} />
          ))}
        </ul>
      </div>
    </main>
  );
}