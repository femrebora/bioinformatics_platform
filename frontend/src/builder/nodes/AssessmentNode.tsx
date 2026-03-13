import { Handle, Position } from "@xyflow/react";

interface AssessmentNodeData {
  label?: string;
  [key: string]: unknown;
}

interface AssessmentNodeProps {
  data: AssessmentNodeData;
  selected?: boolean;
}

export function AssessmentNode({ data, selected }: AssessmentNodeProps) {
  const label = data.label ?? "Mutation Assessment";

  return (
    <div
      style={{
        border: `2px solid ${selected ? "#b45309" : "#d97706"}`,
        borderRadius: 8,
        background: "#fffbeb",
        minWidth: 180,
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
        <span style={{ color: "#fff", fontWeight: 700, fontSize: 12, flex: 1 }}>
          {label}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            background: "#92400e",
            color: "#fef3c7",
            borderRadius: 8,
            padding: "1px 6px",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Coming Soon
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: "8px 10px" }}>
        <div style={{ fontSize: 11, color: "#92400e" }}>
          Cross-reference variants against ClinVar, OncoKB, and other mutation databases.
        </div>
      </div>

      {/* Input handle — receives VCF / results from sarek */}
      <Handle
        type="target"
        position={Position.Left}
        id="result-in"
        style={{
          background: "#d97706",
          width: 10,
          height: 10,
          border: "2px solid #fff",
        }}
      />
    </div>
  );
}
