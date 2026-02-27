/**
 * ParameterPanel — fixed right-edge drawer showing per-pipeline parameters.
 * Opened when user clicks "⚙ Parameters" on an NfCorePipelineNode.
 * Writes param values back into the node via updateNodeData().
 */
import { useReactFlow } from "@xyflow/react";
import { PIPELINE_PARAMS, type PipelineParam } from "./pipelineParams";

interface ParameterPanelProps {
  nodeId: string | null;
  pipelineId: string | null;
  onClose: () => void;
}

export function ParameterPanel({ nodeId, pipelineId, onClose }: ParameterPanelProps) {
  const { updateNodeData, getNode } = useReactFlow();

  const open = !!nodeId && !!pipelineId;
  const params = pipelineId ? (PIPELINE_PARAMS[pipelineId] ?? []) : [];

  // Read current values from node data
  const nodeData = nodeId ? (getNode(nodeId)?.data as Record<string, unknown> | undefined) : undefined;
  const currentParams = (nodeData?.params ?? {}) as Record<string, unknown>;

  function getValue(param: PipelineParam): unknown {
    if (param.key in currentParams) return currentParams[param.key];
    return param.default;
  }

  function setValue(key: string, value: unknown) {
    if (!nodeId) return;
    const existing = (getNode(nodeId)?.data?.params ?? {}) as Record<string, unknown>;
    updateNodeData(nodeId, { params: { ...existing, [key]: value } });
  }

  function resetAll() {
    if (!nodeId) return;
    updateNodeData(nodeId, { params: {} });
  }

  const panelStyle: React.CSSProperties = {
    position: "fixed",
    top: 0,
    right: open ? 0 : -380,
    width: 360,
    height: "100vh",
    background: "#fff",
    borderLeft: "1px solid #e5e7eb",
    boxShadow: "-6px 0 32px rgba(0,0,0,0.14)",
    zIndex: 300,
    display: "flex",
    flexDirection: "column",
    transition: "right 0.28s cubic-bezier(0.4, 0, 0.2, 1)",
    pointerEvents: open ? "all" : "none",
  };

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", borderBottom: "1px solid #e5e7eb", background: "#f9fafb", flexShrink: 0 }}>
        <span style={{ fontSize: 16 }}>⚙️</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#111827" }}>Pipeline Parameters</div>
          {pipelineId && (
            <div style={{ fontSize: 10, color: "#6b7280", marginTop: 1 }}>nf-core/{pipelineId}</div>
          )}
        </div>
        <button
          onClick={resetAll}
          title="Reset all to defaults"
          style={{ fontSize: 11, padding: "3px 9px", borderRadius: 6, border: "1px solid #e5e7eb", background: "#f1f5f9", color: "#64748b", cursor: "pointer" }}
        >
          Reset
        </button>
        <button
          onClick={onClose}
          style={{ fontSize: 18, background: "none", border: "none", color: "#9ca3af", cursor: "pointer", lineHeight: 1, padding: "0 2px" }}
        >
          ×
        </button>
      </div>

      {/* Params list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px" }}>
        {params.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#9ca3af", fontSize: 13 }}>
            No configurable parameters for this pipeline.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {params.map((param) => (
              <ParamControl
                key={param.key}
                param={param}
                value={getValue(param)}
                onChange={(v) => setValue(param.key, v)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer note */}
      <div style={{ padding: "10px 18px", borderTop: "1px solid #e5e7eb", background: "#f9fafb", fontSize: 10, color: "#9ca3af", flexShrink: 0 }}>
        Parameters are passed as <code style={{ background: "#f1f5f9", borderRadius: 3, padding: "1px 4px" }}>--key value</code> flags to nextflow run.
      </div>
    </div>
  );
}

function ParamControl({
  param,
  value,
  onChange,
}: {
  param: PipelineParam;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const isModified = value !== param.default && !(value === "" && param.default === "");

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 5 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", flex: 1 }}>
          {param.label}
          {isModified && (
            <span style={{ marginLeft: 5, fontSize: 9, background: "#dbeafe", color: "#1d4ed8", borderRadius: 4, padding: "1px 5px", fontWeight: 700 }}>
              modified
            </span>
          )}
        </label>
        {isModified && (
          <button
            onClick={() => onChange(param.default)}
            style={{ fontSize: 9, color: "#6b7280", background: "none", border: "none", cursor: "pointer", padding: 0 }}
          >
            reset
          </button>
        )}
      </div>

      {param.type === "boolean" && (
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
            style={{ width: 15, height: 15, accentColor: "#3b82f6" }}
          />
          <span style={{ fontSize: 11, color: "#6b7280" }}>
            {value ? "Enabled" : "Disabled"}
          </span>
        </label>
      )}

      {param.type === "select" && (
        <select
          value={String(value ?? param.default)}
          onChange={(e) => onChange(e.target.value)}
          style={{ width: "100%", fontSize: 12, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", color: "#374151", cursor: "pointer" }}
        >
          {(param.options ?? []).map((opt) => (
            <option key={opt} value={opt}>{opt || "(none)"}</option>
          ))}
        </select>
      )}

      {param.type === "number" && (
        <input
          type="number"
          value={String(value ?? param.default)}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          style={{ width: "100%", fontSize: 12, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", color: "#374151" }}
        />
      )}

      {param.type === "text" && (
        <input
          type="text"
          value={String(value ?? param.default)}
          onChange={(e) => onChange(e.target.value)}
          placeholder={param.hint ?? `--${param.key} …`}
          style={{ width: "100%", fontSize: 12, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", color: "#374151" }}
        />
      )}

      {param.hint && (
        <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 4, lineHeight: 1.4 }}>
          {param.hint}
        </div>
      )}
    </div>
  );
}
