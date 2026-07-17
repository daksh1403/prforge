import { useEffect, useState } from "react";
import { Run, listRuns, solve, approve, getRun } from "./api";

export default function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = () => listRuns().then(setRuns);
  useEffect(() => { refresh(); }, []);

  const onSolve = async () => {
    if (!url) return;
    setBusy(true);
    await solve(url, true);
    setUrl("");
    await refresh();
    setBusy(false);
  };

  const onSelect = async (id: string) => setSelected(await getRun(id));
  const onApprove = async (id: string) => { await approve(id); setSelected(await getRun(id)); refresh(); };

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 1100, margin: "0 auto", padding: 24 }}>
      <h1 style={{ color: "#0891b2" }}>🔨 PRForge Dashboard</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/issues/42"
          style={{ flex: 1, padding: 8 }}
        />
        <button onClick={onSolve} disabled={busy} style={{ padding: "8px 16px" }}>
          {busy ? "Solving..." : "Solve (dry-run)"}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <div>
          <h2>Runs</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>
                <th style={{ padding: 6 }}>ID</th><th>Status</th><th>Edits</th><th>Tests</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} onClick={() => onSelect(r.id)} style={{ cursor: "pointer", borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: 6 }}>{r.id}</td>
                  <td>{r.status}</td>
                  <td>{r.edits_applied}</td>
                  <td>{r.test_pass === null ? "-" : r.test_pass ? "✅" : "❌"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h2>Detail</h2>
          {selected ? (
            <div>
              <p><b>Issue:</b> {selected.issue_url}</p>
              <p><b>Iterations:</b> {selected.iterations} · <b>Edits:</b> {selected.edits_applied}</p>
              <p><b>Approved:</b> {selected.approved ? "yes" : "no"}</p>
              {!selected.approved && (
                <button onClick={() => onApprove(selected.id)}>Approve</button>
              )}
              <pre style={{ background: "#0b1021", color: "#e5e7eb", padding: 12, overflow: "auto", maxHeight: 400 }}>
                {selected.diff || "(no diff)"}
              </pre>
            </div>
          ) : <p>Select a run.</p>}
        </div>
      </div>
    </div>
  );
}
