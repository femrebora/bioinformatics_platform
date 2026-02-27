import { useState, useEffect, useRef, useCallback } from "react";
import { cancelJob, getJobLogs } from "../api/client";
import type { Job } from "../types/job";

interface Props {
  job: Job | null;
  onCancelled?: () => void;
}

const STAGE_PROGRESS: Record<string, number> = {
  pending: 5,
  ec2_starting: 25,
  hla_running: 65,
  pipeline_running: 50,
  snakemake_running: 75,
  done: 100,
};

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued — waiting for worker…",
  ec2_starting: "Starting compute instance…",
  hla_running: "Running HLA-HD…",
  pipeline_running: "Running Nextflow pipeline…",
  snakemake_running: "Running Snakemake workflow…",
  done: "Complete",
};

const STATUS_PROGRESS: Record<string, number> = {
  pending: 5,
  running: 30,
  completed: 100,
  failed: 100,
  cancelled: 100,
};

const STAGE_LABELS_MIXED: Record<string, string> = {
  pipeline_running: "Phase 1 of 2 — Running Nextflow pipeline…",
  snakemake_running: "Phase 2 of 2 — Running Snakemake workflow…",
};

function getProgress(job: Job | null): number {
  if (!job) return 0;
  if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") return 100;
  if (job.stage && STAGE_PROGRESS[job.stage] !== undefined) {
    return STAGE_PROGRESS[job.stage];
  }
  return STATUS_PROGRESS[job.status] ?? 5;
}

function getLabel(job: Job | null): string {
  if (!job) return "Initialising…";
  if (job.status === "cancelled") return "Job cancelled.";
  if (job.status === "failed") return `Failed: ${job.error ?? "Unknown error"}`;
  if (job.stage) {
    if (job.pipeline_id === "mixed" && STAGE_LABELS_MIXED[job.stage]) {
      return STAGE_LABELS_MIXED[job.stage];
    }
    if (STAGE_LABELS[job.stage]) return STAGE_LABELS[job.stage];
  }
  return STAGE_LABELS[job.status] ?? "Processing…";
}

const LOG_POLL_MS = 1500;
const MAX_DISPLAY_LINES = 200;

export function JobProgress({ job, onCancelled }: Props) {
  const [cancelling, setCancelling] = useState(false);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const offsetRef = useRef(0);
  const logEndRef = useRef<HTMLDivElement>(null);
  const progress = getProgress(job);
  const label = getLabel(job);
  const failed = job?.status === "failed";
  const cancelled = job?.status === "cancelled";
  const isActive = job && (job.status === "pending" || job.status === "running");
  const isDone = job && (job.status === "completed" || job.status === "failed" || job.status === "cancelled");

  // Poll for log lines while job is active or until done
  const pollLogs = useCallback(async () => {
    if (!job?.job_id) return;
    try {
      const resp = await getJobLogs(job.job_id, offsetRef.current);
      if (resp.lines.length > 0) {
        setLogLines((prev) => {
          const merged = [...prev, ...resp.lines];
          return merged.slice(-MAX_DISPLAY_LINES);
        });
        offsetRef.current = resp.next_offset;
      }
    } catch {
      // non-fatal — log polling failures are silently ignored
    }
  }, [job?.job_id]);

  useEffect(() => {
    if (!job?.job_id) return;
    // Reset when job changes
    offsetRef.current = 0;
    setLogLines([]);

    pollLogs();
    if (isDone) return;

    const interval = setInterval(pollLogs, LOG_POLL_MS);
    return () => clearInterval(interval);
  }, [job?.job_id, isDone, pollLogs]);

  // Auto-scroll log pane to bottom when new lines arrive
  useEffect(() => {
    if (showLogs && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logLines, showLogs]);

  async function handleCancel() {
    if (!job || !isActive) return;
    setCancelling(true);
    try {
      await cancelJob(job.job_id);
      onCancelled?.();
    } catch {
      setCancelling(false);
    }
  }

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>Pipeline Running</h2>

      <div style={styles.barOuter}>
        <div
          style={{
            ...styles.barInner,
            width: `${progress}%`,
            background: cancelled ? "#6b7280" : failed ? "#dc2626" : "#2563eb",
            transition: "width 0.5s ease",
          }}
        />
      </div>

      <p style={{ ...styles.label, color: cancelled ? "#6b7280" : failed ? "#dc2626" : "#374151" }}>
        {label}
      </p>

      {job && (
        <p style={styles.meta}>
          Job ID: <code style={styles.code}>{job.job_id}</code>
        </p>
      )}

      {/* Log toggle button — shown once there are lines or job is active */}
      {(logLines.length > 0 || isActive) && (
        <button
          onClick={() => setShowLogs((v) => !v)}
          style={styles.logsToggle}
        >
          {showLogs ? "Hide logs" : `Show logs${logLines.length ? ` (${logLines.length})` : ""}`}
        </button>
      )}

      {/* Terminal-style log pane */}
      {showLogs && (
        <div style={styles.logPane}>
          {logLines.length === 0 ? (
            <span style={styles.logEmpty}>Waiting for log output…</span>
          ) : (
            logLines.map((line, i) => (
              <div key={i} style={styles.logLine}>{line}</div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      )}

      {isActive && (
        <button
          onClick={handleCancel}
          disabled={cancelling}
          style={styles.cancelBtn}
        >
          {cancelling ? "Cancelling…" : "Cancel Job"}
        </button>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 560, margin: "0 auto", textAlign: "center" },
  title: { fontSize: 22, fontWeight: 700, marginBottom: 24 },
  barOuter: {
    height: 16,
    background: "#e5e7eb",
    borderRadius: 9999,
    overflow: "hidden",
  },
  barInner: {
    height: "100%",
    borderRadius: 9999,
  },
  label: { marginTop: 16, fontSize: 15 },
  meta: { color: "#9ca3af", fontSize: 12, marginTop: 8 },
  code: { fontFamily: "monospace", background: "#f3f4f6", padding: "2px 6px", borderRadius: 4 },
  logsToggle: {
    marginTop: 14,
    padding: "5px 14px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    background: "#f9fafb",
    color: "#374151",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
  },
  logPane: {
    marginTop: 10,
    background: "#0f172a",
    borderRadius: 8,
    padding: "12px 14px",
    maxHeight: 240,
    overflowY: "auto",
    textAlign: "left",
    fontFamily: "monospace",
    fontSize: 12,
    lineHeight: 1.6,
    border: "1px solid #1e293b",
  },
  logLine: {
    color: "#94a3b8",
    wordBreak: "break-all",
    whiteSpace: "pre-wrap",
  },
  logEmpty: {
    color: "#475569",
    fontStyle: "italic",
  },
  cancelBtn: {
    marginTop: 20,
    padding: "8px 20px",
    borderRadius: 7,
    border: "1px solid #fca5a5",
    background: "#fff",
    color: "#dc2626",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
};
