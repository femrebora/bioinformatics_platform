import type { Job } from "../types/job";

interface Props {
  job: Job | null;
}

const STAGE_PROGRESS: Record<string, number> = {
  pending: 5,
  ec2_starting: 25,
  hla_running: 65,
  done: 100,
};

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued — waiting for worker…",
  ec2_starting: "Starting compute instance…",
  hla_running: "Running HLA-HD…",
  done: "Complete",
};

function getProgress(job: Job | null): number {
  if (!job) return 0;
  if (job.status === "completed") return 100;
  if (job.status === "failed") return 100;
  if (job.stage && STAGE_PROGRESS[job.stage] !== undefined) {
    return STAGE_PROGRESS[job.stage];
  }
  return STAGE_PROGRESS[job.status] ?? 5;
}

function getLabel(job: Job | null): string {
  if (!job) return "Initialising…";
  if (job.status === "failed") return `Failed: ${job.error ?? "Unknown error"}`;
  if (job.stage && STAGE_LABELS[job.stage]) return STAGE_LABELS[job.stage];
  return STAGE_LABELS[job.status] ?? "Processing…";
}

export function JobProgress({ job }: Props) {
  const progress = getProgress(job);
  const label = getLabel(job);
  const failed = job?.status === "failed";

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>Pipeline Running</h2>

      <div style={styles.barOuter}>
        <div
          style={{
            ...styles.barInner,
            width: `${progress}%`,
            background: failed ? "#dc2626" : "#2563eb",
            transition: "width 0.5s ease",
          }}
        />
      </div>

      <p style={{ ...styles.label, color: failed ? "#dc2626" : "#374151" }}>
        {label}
      </p>

      {job && (
        <p style={styles.meta}>
          Job ID: <code style={styles.code}>{job.job_id}</code>
        </p>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 480, margin: "0 auto", textAlign: "center" },
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
};
