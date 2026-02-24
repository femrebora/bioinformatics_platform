import type { Job } from "../types/job";

interface Props {
  job: Job;
  onReset: () => void;
}

export function ResultTable({ job, onReset }: Props) {
  const result = job.result;

  if (!result) return null;

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>HLA Typing Results</h2>

      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Gene</th>
            <th style={styles.th}>Allele 1</th>
            <th style={styles.th}>Allele 2</th>
          </tr>
        </thead>
        <tbody>
          {(result.hla_alleles ?? []).map((row) => (
            <tr key={row.gene} style={styles.tr}>
              <td style={{ ...styles.td, fontWeight: 600 }}>{row.gene}</td>
              <td style={styles.td}>
                <code style={styles.allele}>{row.allele_1}</code>
              </td>
              <td style={styles.td}>
                <code style={styles.allele}>{row.allele_2}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={styles.meta}>
        <span>Instance: <strong>{result.instance_type}</strong></span>
        <span>Runtime: <strong>{result.runtime_seconds}s</strong></span>
        <span>Cost: <strong>${job.estimated_cost_usd.toFixed(2)}</strong></span>
      </div>

      <button style={styles.resetBtn} onClick={onReset}>
        Run Another Analysis
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 560, margin: "0 auto" },
  title: { fontSize: 22, fontWeight: 700, marginBottom: 20 },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "#fff",
    borderRadius: 10,
    overflow: "hidden",
    border: "1px solid #e5e7eb",
  },
  th: {
    background: "#f9fafb",
    padding: "12px 16px",
    textAlign: "left",
    fontSize: 13,
    fontWeight: 600,
    color: "#6b7280",
    borderBottom: "1px solid #e5e7eb",
  },
  tr: { borderBottom: "1px solid #f3f4f6" },
  td: { padding: "12px 16px", fontSize: 14 },
  allele: {
    fontFamily: "monospace",
    background: "#eff6ff",
    color: "#1d4ed8",
    padding: "2px 8px",
    borderRadius: 6,
    fontSize: 13,
  },
  meta: {
    display: "flex",
    gap: 24,
    marginTop: 16,
    fontSize: 13,
    color: "#6b7280",
  },
  resetBtn: {
    marginTop: 24,
    padding: "10px 24px",
    borderRadius: 8,
    border: "none",
    background: "#2563eb",
    color: "#fff",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
  },
};
