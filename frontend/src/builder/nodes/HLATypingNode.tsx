import { Handle, Position, useReactFlow } from "@xyflow/react";
import type { Tier } from "../../types/job";

const TIER_COSTS: Record<Tier, string> = {
  small: "~$0.50",
  medium: "~$1.20",
  large: "~$2.80",
};

interface HLATypingNodeData {
  label: string;
  tier: Tier;
}

interface HLATypingNodeProps {
  id: string;
  data: HLATypingNodeData;
}

export function HLATypingNode({ id, data }: HLATypingNodeProps) {
  const { updateNodeData, setNodes, setEdges } = useReactFlow();

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
        id="file-in"
        style={styles.handle}
      />
      <div style={styles.header}>
        <span style={styles.icon}>🧬</span>
        <span style={styles.label}>{data.label}</span>
        <button onClick={handleDelete} style={styles.deleteBtn} title="Remove node">×</button>
      </div>
      <div style={styles.body}>
        <label style={styles.fieldLabel}>Compute Tier</label>
        <select
          value={data.tier}
          onChange={(e) =>
            updateNodeData(id, { tier: e.target.value as Tier })
          }
          style={styles.select}
        >
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
        <div style={styles.costHint}>Est. cost: {TIER_COSTS[data.tier]}</div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="result-out"
        style={styles.handle}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: "2px solid #2563eb",
    borderRadius: 8,
    minWidth: 170,
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
  },
  header: {
    background: "#2563eb",
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
  fieldLabel: { display: "block", fontSize: 11, color: "#6b7280", marginBottom: 4 },
  select: {
    width: "100%",
    padding: "4px 6px",
    borderRadius: 4,
    border: "1px solid #d1d5db",
    fontSize: 12,
    background: "#f9fafb",
    cursor: "pointer",
  },
  costHint: {
    marginTop: 6,
    fontSize: 11,
    color: "#6b7280",
    fontStyle: "italic",
  },
  handle: { width: 10, height: 10, background: "#2563eb" },
};
