export interface Run {
  id: string;
  issue_url: string;
  dry_run: boolean;
  status: string;
  approved: boolean;
  iterations: number;
  edits_applied: number;
  test_pass: boolean | null;
  diff: string;
  pr_url: string;
  error: string | null;
  created_at: number;
}

const base = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";

export async function listRuns(): Promise<Run[]> {
  const r = await fetch(`${base}/api/runs`);
  const data = await r.json();
  return data.runs ?? [];
}

export async function getRun(id: string): Promise<Run> {
  const r = await fetch(`${base}/api/runs/${id}`);
  return r.json();
}

export async function solve(issueUrl: string, dryRun: boolean): Promise<Run> {
  const r = await fetch(`${base}/api/solve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ issue_url: issueUrl, dry_run: dryRun }),
  });
  return r.json();
}

export async function approve(id: string): Promise<Run> {
  const r = await fetch(`${base}/api/runs/${id}/approve`, { method: "POST" });
  return r.json();
}
