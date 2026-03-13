import { useState, useEffect } from "react";
import { Handle, Position } from "@xyflow/react";
import { getCompletedJobs } from "../../api/client";
import type { JobListItem } from "../../types/job";

interface AssessmentNodeData {
  label?: string;
  sourceJobId?: string;
  [key: string]: unknown;
}

interface AssessmentNodeProps {
  id: string;
  data: AssessmentNodeData;
  selected?: boolean;
}

export function AssessmentNode({ id, data, selected }: AssessmentNodeProps) {
  const label = data.label ?? "Mutation Assessment";
  const [sarekJobs, setSarekJobs] = useState<JobListItem[]>([]);

  useEffect(() => {
    getCompletedJobs()
      .then((jobs) => setSarekJobs(jobs.filter((j) => j.pipeline_id === "sarek")))
      .catch(() => undefined);
  }, []);

  function handleSourceJobChange(jobId: string) {
    window.dispatchEvent(
      new CustomEvent("assessmentNodeUpdate", { detail: { nodeId: id, sourceJobId: jobId } })
    );
  }

  const selectedJob = sarekJobs.find((j) => j.job_id === data.sourceJobId);
  const hasSource = Boolean(data.sourceJobId);

  return (
    <div
      style={{
        border: `2px solid ${selected ? "#b45309" : "#d97706"}`,
        borderRadius: 8,
        background: "#fffbeb",
        minWidth: 210,
        boxShadow: selected ? "0 0 0 3px #fde68a" : "0 1px 4px rgba(0,0,0,0.10)",
      }}
    >
      {/* Header */}
      <div
        style={{
          background: "#d97706",
          borderRadius: "6px 6px 0 0",
          padding: "6px 10px",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span style={{ fontSize: 13 }}>🔬</span>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: 12, flex: 1 }}>{label}</span>
      </div>

      {/* Body */}
      <div style={{ padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ fontSize: 10, color: "#92400e", lineHeight: 1.4 }}>
          ClinVar · CancerHotspots · dbSNP annotation + PDF report
        </div>

        {/* Source job selector */}
        <div>
          <div style={{ fontSize: 9, fontWeight: 600, color: "#6b7280", marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Sarek source job
          </div>
          {sarekJobs.length === 0 ? (
            <div style={{ fontSize: 10, color: "#9ca3af", fontStyle: "italic" }}>
              No completed sarek jobs yet
            </div>
          ) : (
            <select
              value={data.sourceJobId ?? ""}
              onChange={(e) => handleSourceJobChange(e.target.value)}
              style={{
                width: "100%",
                fontSize: 10,
                padding: "3px 5px",
                borderRadius: 4,
                border: `1px solid ${hasSource ? "#d97706" : "#e5e7eb"}`,
                background: "#fff",
                color: "#374151",
                cursor: "pointer",
              }}
            >
              <option value="">— select sarek job —</option>
              {sarekJobs.map((j) => (
                <option key={j.job_id} value={j.job_id}>
                  {j.job_name ?? j.job_id.slice(0, 8)} ({new Date(j.created_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          )}
          {selectedJob && (
            <div style={{ fontSize: 9, color: "#d97706", marginTop: 2 }}>
              ✓ {selectedJob.job_name ?? selectedJob.job_id.slice(0, 8)}
            </div>
          )}
          {!hasSource && sarekJobs.length > 0 && (
            <div style={{ fontSize: 9, color: "#ef4444", marginTop: 2 }}>
              Select a sarek job to enable run
            </div>
          )}
        </div>
      </div>

      {/* Input handle — receives from sarek nfc-out-results */}
      <Handle
        type="target"
        position={Position.Left}
        id="assessment-in"
        style={{ background: "#d97706", width: 10, height: 10, border: "2px solid #fff" }}
      />

      {/* Output handle — connects to Results node */}
      <Handle
        type="source"
        position={Position.Right}
        id="assessment-out"
        style={{ background: "#d97706", width: 10, height: 10, border: "2px solid #fff" }}
      />
    </div>
  );
}
