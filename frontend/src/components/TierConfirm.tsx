import type { PresignResponse, Tier } from "../types/job";

export interface TierConfirmProps {
  presign: PresignResponse;
  filename: string;
  onConfirm: (tier: Tier, estimatedCostUsd: number) => void;
  onCancel: () => void;
}

const TIER_COLORS: Record<Tier, string> = {
  small: "#16a34a",
  medium: "#d97706",
  large: "#dc2626",
};

const TIER_LABELS: Record<Tier, string> = {
  small: "Small",
  medium: "Medium",
  large: "Large",
};

export function TierConfirm({ presign, filename, onConfirm, onCancel }: TierConfirmProps) {
  const tier = presign.recommended_tier;
  const color = TIER_COLORS[tier];

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>Confirm Pipeline Run</h2>

      <div style={styles.card}>
        <div style={styles.row}>
          <span style={styles.label}>File</span>
          <span style={styles.value}>{filename}</span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Tier</span>
          <span style={{ ...styles.badge, background: color }}>
            {TIER_LABELS[tier]}
          </span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Rationale</span>
          <span style={styles.value}>{presign.tier_rationale}</span>
        </div>
        <div style={{ ...styles.row, ...styles.costRow }}>
          <span style={styles.label}>Estimated cost</span>
          <span style={styles.cost}>${presign.estimated_cost_usd.toFixed(2)}</span>
        </div>
      </div>

      <div style={styles.actions}>
        <button style={styles.cancelBtn} onClick={onCancel}>
          Cancel
        </button>
        <button
          style={styles.runBtn}
          onClick={() => onConfirm(tier, presign.estimated_cost_usd)}
        >
          Run Pipeline
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 480, margin: "0 auto" },
  title: { fontSize: 22, fontWeight: 700, marginBottom: 20 },
  card: {
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  row: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 },
  costRow: { borderTop: "1px solid #f3f4f6", paddingTop: 14, marginTop: 4 },
  label: { color: "#6b7280", fontSize: 14, flexShrink: 0 },
  value: { color: "#111827", fontSize: 14, textAlign: "right", wordBreak: "break-all" },
  badge: {
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    padding: "3px 10px",
    borderRadius: 9999,
  },
  cost: { fontSize: 22, fontWeight: 700, color: "#111827" },
  actions: { display: "flex", gap: 12, marginTop: 24, justifyContent: "flex-end" },
  cancelBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid #d1d5db",
    background: "#fff",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 500,
  },
  runBtn: {
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
