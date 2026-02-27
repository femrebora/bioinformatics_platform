import { Handle, Position, useReactFlow } from "@xyflow/react";
import { IGENOMES } from "../pipelineParams";

export interface NfCorePipelineNodeData {
  label: string;
  pipelineId: string;
  description: string | null;
  stars: number;
  genome?: string;
  params?: Record<string, unknown>;
}

interface NfCorePipelineNodeProps {
  id: string;
  data: NfCorePipelineNodeData;
}

const COLOR = "#0e7490";

export function NfCorePipelineNode({ id, data }: NfCorePipelineNodeProps) {
  const { setNodes, setEdges, updateNodeData } = useReactFlow();

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  function handleOpenParams(e: React.MouseEvent) {
    e.stopPropagation();
    window.dispatchEvent(
      new CustomEvent("openParamPanel", { detail: { nodeId: id, pipelineId: data.pipelineId } })
    );
  }

  const genome = data.genome ?? "";
  const paramCount = Object.keys(data.params ?? {}).filter(
    (k) => (data.params ?? {})[k] !== undefined && (data.params ?? {})[k] !== ""
  ).length;

  return (
    <div style={styles.node}>
      <Handle type="target" position={Position.Left} id="nfc-in-data" style={styles.handle} />

      <div style={styles.header}>
        <span style={styles.icon}>🔬</span>
        <span style={styles.label} title={data.label}>{data.label}</span>
        <button onClick={handleDelete} style={styles.deleteBtn} title="Remove node">×</button>
      </div>

      <div style={styles.body}>
        {data.stars > 0 && (
          <div style={styles.stars}>⭐ {data.stars.toLocaleString()}</div>
        )}
        {data.description && (
          <div style={styles.desc}>
            {data.description.length > 80
              ? data.description.slice(0, 77) + "…"
              : data.description}
          </div>
        )}

        {/* Genome selector */}
        <div style={{ marginTop: 8 }}>
          <div style={styles.fieldLabel}>Reference genome</div>
          <select
            value={genome}
            onChange={(e) => updateNodeData(id, { genome: e.target.value })}
            onClick={(e) => e.stopPropagation()}
            style={{
              ...styles.select,
              borderColor: genome ? "#0e7490" : "#fca5a5",
              color: genome ? "#0f172a" : "#dc2626",
            }}
          >
            <option value="">⚠ Select genome…</option>
            {IGENOMES.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}{g.organism ? ` (${g.organism})` : ""}
              </option>
            ))}
          </select>
          {!genome && (
            <div style={{ fontSize: 9, color: "#dc2626", marginTop: 2 }}>
              Required — pipeline will fail without a genome build.
            </div>
          )}
        </div>

        {/* Parameters button */}
        <button onClick={handleOpenParams} style={styles.paramsBtn}>
          ⚙ Parameters
          {paramCount > 0 && (
            <span style={styles.paramBadge}>{paramCount}</span>
          )}
        </button>
      </div>

      <Handle type="source" position={Position.Right} id="nfc-out-results" style={styles.handle} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: `2px solid ${COLOR}`,
    borderRadius: 8,
    minWidth: 200,
    maxWidth: 240,
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
  },
  header: {
    background: COLOR,
    borderRadius: "6px 6px 0 0",
    padding: "6px 10px",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 13 },
  label: {
    color: "#fff",
    fontWeight: 600,
    fontSize: 11,
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  deleteBtn: {
    marginLeft: "auto",
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.75)",
    cursor: "pointer",
    fontSize: 16,
    lineHeight: 1,
    padding: "0 2px",
    flexShrink: 0,
  },
  body: { padding: "8px 10px" },
  stars: { fontSize: 11, color: "#6b7280", marginBottom: 4 },
  desc: { fontSize: 10, color: "#6b7280", lineHeight: 1.4 },
  fieldLabel: { fontSize: 10, fontWeight: 600, color: "#6b7280", marginBottom: 3, textTransform: "uppercase" as const, letterSpacing: ".04em" },
  select: {
    width: "100%",
    fontSize: 11,
    padding: "4px 7px",
    borderRadius: 5,
    border: "1.5px solid #d1d5db",
    background: "#f9fafb",
    color: "#0f172a",
    cursor: "pointer",
  },
  paramsBtn: {
    marginTop: 8,
    width: "100%",
    padding: "5px 10px",
    borderRadius: 6,
    border: "1px solid #0e7490",
    background: "#f0fdfa",
    color: "#0e7490",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  paramBadge: {
    background: "#0e7490",
    color: "#fff",
    borderRadius: 999,
    fontSize: 9,
    fontWeight: 700,
    padding: "1px 6px",
  },
  handle: { width: 8, height: 8, background: COLOR },
};
