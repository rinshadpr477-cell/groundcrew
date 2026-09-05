import { QueueItem } from "./QueueItem";

export interface TriageResult {
  id: number;
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
  created_at: string;
}

async function getQueue(): Promise<TriageResult[]> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/triage/queue`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Failed to load the review queue (${response.status})`);
  }

  return response.json();
}

export default async function QueuePage() {
  let items: TriageResult[] = [];
  let loadError: string | null = null;

  try {
    items = await getQueue();
  } catch (err) {
    loadError = err instanceof Error ? err.message : "Something went wrong loading the queue.";
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-semibold">Groundcrew review queue</h1>
      <p className="mt-1 text-sm text-gray-500">
        Issues the critic couldn&apos;t fully verify — needs a human look before anything gets posted.
      </p>

      {loadError && (
        <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Couldn&apos;t reach the API: {loadError}. Is the FastAPI server running on port 8000?
        </p>
      )}

      {!loadError && items.length === 0 && (
        <p className="mt-6 text-sm text-gray-500">Nothing waiting for review right now.</p>
      )}

      <ul className="mt-6 flex flex-col gap-4">
        {items.map((item) => (
          <QueueItem key={item.id} item={item} />
        ))}
      </ul>
    </main>
  );
}