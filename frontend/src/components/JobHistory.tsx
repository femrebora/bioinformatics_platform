import { useState, useEffect } from "react";
import { listJobs } from "../api/client";
import type { JobListItem, JobStatus } from "../types/job";

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60)  return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60)  return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7)   return `${days}d ago`;
  return d.toLocaleDateString();
}

const STATUS_STYLE: Record<JobStatus, { bg: string; text: string }> = {
  pending:   { bg: "#fef9c3", text: "#854d0e" },
  running:   { bg: "#dbeafe", text: "#1d4ed8" },
  completed: { bg: "#dcfce7", text: "#15803d" },
  failed:    { bg: "#fee2e2", text: "#b91c1c" },
};

function StatusBadge({ status }: { status: JobStatus }) {
  const s = STATUS_STYLE[status] ?? { bg: "#f3f4f6", text: "#374151" };
  return (
    <span style={{ padding: "2px 9px", borderRadius: 20, fontSize: 11, fontWeight: 700, background: s.bg, color: s.text }}>
      {status}
    </span>
  );
}

export function JobHistory() {
  const [jobs, setJobs]     = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listJobs()
      .then((data) => { if (!cancelled) { setJobs(data); setLoading(false); } })
      .catch((e) => { if (!cancelled) { setError(String(e?.message ?? e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, []);

  return (
    <div style={s.page}>
      <div style={s.header}>
        <h2 style={s.title}>Job History</h2>
        <button
          onClick={() => {
            setLoading(true);
            listJobs()
              .then((data) => { setJobs(data); setLoading(false); })
              .catch((e) => { setError(String(e?.message ?? e)); setLoading(false); });
          }}
          style={s.refreshBtn}
        >
          ↻ Refresh
        </button>
      </div>

      {loading && <div style={s.hint}>Loading…</div>}
      {error   && <div style={{ ...s.hint, color: "#dc2626" }}>Error: {error}</div>}

      {!loading && !error && jobs.length === 0 && (
        <div style={s.hint}>No jobs yet. Run a pipeline from the Pipeline Builder.</div>
      )}

      {!loading && jobs.length > 0 && (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr style={s.headRow}>
                {["Status", "Pipeline", "Tier", "Est. Cost", "Created"].map((h) => (
                  <th key={h} style={s.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id} style={s.bodyRow}>
                  <td style={s.td}><StatusBadge status={job.status} /></td>
                  <td style={s.td}>
                    {job.pipeline_id
                      ? <span style={{ fontSize: 12, color: "#374151", fontFamily: "monospace" }}>{job.pipeline_id}</span>
                      : <span style={{ fontSize: 12, color: "#6b7280" }}>HLA typing</span>
                    }
                  </td>
                  <td style={s.td}>
                    <span style={{ fontSize: 12, color: "#374151", textTransform: "capitalize" as const }}>{job.tier}</span>
                  </td>
                  <td style={s.td}>
                    <span style={{ fontSize: 12, color: "#374151" }}>${job.estimated_cost_usd.toFixed(2)}</span>
                  </td>
                  <td style={s.td}>
                    <span style={{ fontSize: 12, color: "#6b7280" }} title={new Date(job.created_at).toLocaleString()}>
                      {formatDate(job.created_at)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 900,
    margin: "48px auto",
    padding: "0 24px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    marginBottom: 20,
    gap: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    margin: 0,
    flex: 1,
  },
  refreshBtn: {
    padding: "6px 14px",
    borderRadius: 7,
    border: "1px solid #d1d5db",
    background: "#fff",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    color: "#374151",
  },
  hint: {
    fontSize: 14,
    color: "#6b7280",
    textAlign: "center",
    padding: "48px 0",
  },
  tableWrap: {
    background: "#fff",
    borderRadius: 10,
    border: "1px solid #e5e7eb",
    overflow: "hidden",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  headRow: {
    background: "#f9fafb",
  },
  th: {
    padding: "10px 16px",
    textAlign: "left",
    fontSize: 11,
    fontWeight: 700,
    color: "#6b7280",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    borderBottom: "1px solid #e5e7eb",
  },
  bodyRow: {
    borderBottom: "1px solid #f3f4f6",
  },
  td: {
    padding: "11px 16px",
  },
};
