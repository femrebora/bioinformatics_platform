import { Handle, Position, useReactFlow } from "@xyflow/react";

interface FastqToBamNodeData {
  label: string;
}

interface FastqToBamNodeProps {
  id: string;
  data: FastqToBamNodeData;
}

export function FastqToBamNode({ id, data }: FastqToBamNodeProps) {
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
        id="fastq-in"
        style={styles.handle}
      />
      <div style={styles.header}>
        <span style={styles.icon}>🔄</span>
        <span style={styles.label}>{data.label}</span>
        <button onClick={handleDelete} style={styles.deleteBtn} title="Remove node">×</button>
      </div>
      <div style={styles.body}>
        <span style={styles.hint}>samtools view</span>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="bam-out"
        style={styles.handle}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: "2px solid #7c3aed",
    borderRadius: 8,
    minWidth: 155,
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
  },
  header: {
    background: "#7c3aed",
    borderRadius: "6px 6px 0 0",
    padding: "6px 10px",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 14 },
  label: { color: "#fff", fontWeight: 600, fontSize: 12, flex: 1 },
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
  body: { padding: "10px 12px" },
  hint: { fontSize: 11, color: "#6b7280", fontStyle: "italic" },
  handle: { width: 10, height: 10, background: "#7c3aed" },
};
