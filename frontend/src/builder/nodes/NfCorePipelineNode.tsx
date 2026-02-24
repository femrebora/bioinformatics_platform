import { Handle, Position, useReactFlow } from "@xyflow/react";

interface NfCorePipelineNodeData {
  label: string;
  pipelineId: string;
  description: string | null;
  stars: number;
}

interface NfCorePipelineNodeProps {
  id: string;
  data: NfCorePipelineNodeData;
}

const COLOR = "#0e7490";

export function NfCorePipelineNode({ id, data }: NfCorePipelineNodeProps) {
  const { setNodes, setEdges } = useReactFlow();

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  return (
    <div style={styles.node}>
      <Handle
        type="target"
        position={Position.Left}
        id="nfc-in-data"
        style={styles.handle}
      />
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
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="nfc-out-results"
        style={styles.handle}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: `2px solid ${COLOR}`,
    borderRadius: 8,
    minWidth: 190,
    maxWidth: 220,
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
  handle: { width: 8, height: 8, background: COLOR },
};
