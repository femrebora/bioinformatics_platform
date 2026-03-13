import { useState, useEffect, useRef } from "react";
import type { PresignResponse, EstimateResponse, Tier } from "../types/job";
import { fetchEstimate, createCheckoutSession } from "../api/client";

export interface TierConfirmProps {
  presign: PresignResponse;
  filename: string;
  pipelineId: string | null;
  storageKeyR2?: string | null;
  workflowConfig?: unknown | null;
  /** Pre-fill sample count from canvas (e.g. SampleSheetNode row count). */
  initialNSamples?: number;
  onConfirm: (tier: Tier, estimatedCostUsd: number) => void; // kept for compat
  onCancel: () => void;
}

const TIER_COLORS: Record<Tier, string> = {
  small:  "#16a34a",
  medium: "#d97706",
  large:  "#dc2626",
};

const TIER_LABELS: Record<Tier, string> = {
  small:  "Small",
  medium: "Medium",
  large:  "Large",
};

export function TierConfirm({ presign, filename, pipelineId, storageKeyR2, workflowConfig, initialNSamples, onCancel }: TierConfirmProps) {
  const [nSamples, setNSamples]     = useState(initialNSamples ?? 1);
  const [jobName, setJobName]       = useState("");
  const [estimate, setEstimate]     = useState<EstimateResponse | null>(null);
  const [loading, setLoading]       = useState(false);
  const [paying, setPaying]         = useState(false);
  const [payError, setPayError]     = useState<string | null>(null);
  const debounceRef                 = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Only re-estimate when a pipeline is selected — null means generic,
  // which already has the correct presign-based estimate.
  useEffect(() => {
    if (!pipelineId) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const est = await fetchEstimate(pipelineId, nSamples);
        setEstimate(est);
      } catch {
        setEstimate(null);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [nSamples, pipelineId]);

  const displayedCost = estimate?.estimated_cost_usd ?? presign.estimated_cost_usd;
  const displayedTier = (estimate?.tier ?? presign.recommended_tier) as Tier;
  const displayedRationale = estimate?.rationale ?? presign.tier_rationale;
  const color = TIER_COLORS[displayedTier];

  async function handleConfirm() {
    setPayError(null);
    setPaying(true);
    try {
      const ext = filename.split(".").pop()?.toLowerCase() ?? "";
      const fileType = ext === "bam" ? "bam" : "fastq";
      const { checkout_url } = await createCheckoutSession(
        presign.storage_key,
        fileType,
        displayedTier,
        displayedCost,
        pipelineId,
        nSamples,
        storageKeyR2,
        workflowConfig,
        jobName.trim() || null,
      );
      window.location.href = checkout_url;
    } catch {
      setPayError("Could not start payment. Please try again.");
      setPaying(false);
    }
  }

  return (
    <div style={styles.wrapper}>
      <h2 style={styles.title}>Confirm Pipeline Run</h2>

      <div style={styles.card}>
        {/* Job name */}
        <div style={styles.row}>
          <span style={styles.label}>Job name <span style={styles.hint}>(optional)</span></span>
          <input
            value={jobName}
            onChange={(e) => setJobName(e.target.value)}
            placeholder="e.g. Patient-001 rnaseq"
            maxLength={200}
            style={{ flex: 1, marginLeft: 12, padding: "5px 10px", borderRadius: 7, border: "1px solid #d1d5db", fontSize: 13, color: "#111827", outline: "none" }}
          />
        </div>

        {/* File */}
        <div style={styles.row}>
          <span style={styles.label}>File</span>
          <span style={styles.value}>{filename}</span>
        </div>

        {/* Pipeline */}
        {pipelineId && (
          <div style={styles.row}>
            <span style={styles.label}>Pipeline</span>
            <span style={{ ...styles.value, fontFamily: "monospace", fontSize: 13 }}>
              {pipelineId}
            </span>
          </div>
        )}
        {estimate?.pipeline_description && (
          <div style={styles.row}>
            <span style={styles.label}>Description</span>
            <span style={{ ...styles.value, color: "#6b7280", fontSize: 12 }}>
              {estimate.pipeline_description}
            </span>
          </div>
        )}

        {/* Number of samples — only shown when a named pipeline is selected */}
        {pipelineId && (
          <div style={styles.row}>
            <span style={styles.label}>
              Samples
              <span style={styles.hint}>  biological samples in this run</span>
            </span>
            <div style={styles.stepper}>
              <button
                style={styles.stepBtn}
                onClick={() => setNSamples((n) => Math.max(1, n - 1))}
                disabled={nSamples <= 1}
              >−</button>
              <span style={styles.stepVal}>{nSamples}</span>
              <button
                style={styles.stepBtn}
                onClick={() => setNSamples((n) => Math.min(9999, n + 1))}
              >+</button>
            </div>
          </div>
        )}

        {/* Estimated runtime */}
        {estimate && pipelineId && (
          <div style={styles.row}>
            <span style={styles.label}>Est. runtime</span>
            <span style={{ ...styles.value, color: "#6b7280" }}>
              ~{estimate.estimated_hours} hrs on {estimate.instance_type}
            </span>
          </div>
        )}

        {/* Tier badge */}
        <div style={styles.row}>
          <span style={styles.label}>Compute tier</span>
          <span style={{ ...styles.badge, background: loading ? "#9ca3af" : color }}>
            {loading ? "…" : TIER_LABELS[displayedTier]}
          </span>
        </div>

        {/* Rationale */}
        <div style={{ ...styles.row, alignItems: "flex-start" }}>
          <span style={styles.label}>Breakdown</span>
          <span style={{ ...styles.value, color: "#6b7280", fontSize: 12, maxWidth: 260 }}>
            {loading ? "Recalculating…" : displayedRationale}
          </span>
        </div>

        {/* Cost */}
        <div style={{ ...styles.row, ...styles.costRow }}>
          <span style={styles.label}>Estimated cost</span>
          <span style={{ ...styles.cost, opacity: loading ? 0.4 : 1 }}>
            ${displayedCost.toFixed(2)}
          </span>
        </div>
      </div>

      {payError && (
        <div style={{ color: "#dc2626", fontSize: 13, marginTop: 8, textAlign: "right" }}>
          {payError}
        </div>
      )}

      <div style={styles.actions}>
        <button style={styles.cancelBtn} onClick={onCancel} disabled={paying}>Cancel</button>
        <button style={styles.runBtn} onClick={handleConfirm} disabled={loading || paying}>
          {paying ? "Redirecting to payment…" : loading ? "Calculating…" : "Pay & Run →"}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 500, margin: "0 auto" },
  title:   { fontSize: 22, fontWeight: 700, marginBottom: 20 },
  card: {
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  row:      { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 },
  costRow:  { borderTop: "1px solid #f3f4f6", paddingTop: 14, marginTop: 4 },
  label:    { color: "#6b7280", fontSize: 13, flexShrink: 0 },
  hint:     { fontSize: 11, color: "#9ca3af", fontStyle: "italic" },
  value:    { color: "#111827", fontSize: 14, textAlign: "right", wordBreak: "break-all" },
  badge: {
    color: "#fff", fontSize: 13, fontWeight: 600,
    padding: "3px 10px", borderRadius: 9999,
    transition: "background 0.2s",
  },
  cost: { fontSize: 24, fontWeight: 700, color: "#111827", transition: "opacity 0.2s" },
  stepper: { display: "flex", alignItems: "center", gap: 8 },
  stepBtn: {
    width: 28, height: 28, borderRadius: 6,
    border: "1px solid #d1d5db", background: "#f9fafb",
    cursor: "pointer", fontSize: 16, lineHeight: 1,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontWeight: 700,
  },
  stepVal: { fontSize: 15, fontWeight: 600, minWidth: 28, textAlign: "center" },
  actions: { display: "flex", gap: 12, marginTop: 24, justifyContent: "flex-end" },
  cancelBtn: {
    padding: "10px 20px", borderRadius: 8,
    border: "1px solid #d1d5db", background: "#fff",
    cursor: "pointer", fontSize: 14, fontWeight: 500,
  },
  runBtn: {
    padding: "10px 24px", borderRadius: 8, border: "none",
    background: "#2563eb", color: "#fff",
    cursor: "pointer", fontSize: 14, fontWeight: 600,
  },
};
