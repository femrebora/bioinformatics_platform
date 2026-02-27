import { Handle, Position, useReactFlow } from "@xyflow/react";

interface SnakemakeWrapperNodeData {
  label: string;
  tool: string;
  subcommand: string | null;
  description: string | null;
  category: string;
  input_names: string[] | null;
  output_names: string[] | null;
}

interface SnakemakeWrapperNodeProps {
  id: string;
  data: SnakemakeWrapperNodeData;
}

const COLOR = "#d97706"; // amber-600

function portTop(i: number, total: number): string {
  if (total <= 1) return "50%";
  return `${((i + 1) / (total + 1)) * 100}%`;
}

export function SnakemakeWrapperNode({ id, data }: SnakemakeWrapperNodeProps) {
  const { setNodes, setEdges } = useReactFlow();
  const inputs  = data.input_names  ?? [];
  const outputs = data.output_names ?? [];

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  return (
    <div style={styles.node}>
      {/* Input handles — left side */}
      {inputs.length > 0 ? (
        inputs.map((name, i) => (
          <Handle
            key={name}
            type="target"
            position={Position.Left}
            id={`smk-in-${name}`}
            title={name}
            style={{ ...styles.handle, top: portTop(i, inputs.length) }}
          />
        ))
      ) : (
        <Handle
          type="target"
          position={Position.Left}
          id="smk-in-data"
          style={{ ...styles.handle, top: "50%" }}
        />
      )}

      <div style={styles.header}>
        <span style={styles.icon}>🐍</span>
        <span style={styles.label} title={data.label}>{data.label}</span>
        <button onClick={handleDelete} style={styles.deleteBtn} title="Remove node">×</button>
      </div>

      <div style={styles.body}>
        <span style={styles.catBadge}>{data.category}</span>
        {data.description && (
          <div style={styles.desc}>
            {data.description.length > 70
              ? data.description.slice(0, 67) + "…"
              : data.description}
          </div>
        )}
        {inputs.length > 0 && (
          <div style={styles.portRow}>
            <span style={styles.portDir}>in:</span>
            {inputs.slice(0, 4).map((n) => (
              <span key={n} style={styles.portTag}>{n}</span>
            ))}
            {inputs.length > 4 && (
              <span style={styles.portMore}>+{inputs.length - 4}</span>
            )}
          </div>
        )}
        {outputs.length > 0 && (
          <div style={styles.portRow}>
            <span style={styles.portDir}>out:</span>
            {outputs.slice(0, 4).map((n) => (
              <span key={n} style={styles.portTag}>{n}</span>
            ))}
            {outputs.length > 4 && (
              <span style={styles.portMore}>+{outputs.length - 4}</span>
            )}
          </div>
        )}
      </div>

      {/* Output handles — right side */}
      {outputs.length > 0 ? (
        outputs.map((name, i) => (
          <Handle
            key={name}
            type="source"
            position={Position.Right}
            id={`smk-out-${name}`}
            title={name}
            style={{ ...styles.handle, top: portTop(i, outputs.length) }}
          />
        ))
      ) : (
        <Handle
          type="source"
          position={Position.Right}
          id="smk-out-data"
          style={{ ...styles.handle, top: "50%" }}
        />
      )}
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
    position: "relative",
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
  body: {
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  catBadge: {
    fontSize: 9,
    fontWeight: 700,
    textTransform: "uppercase" as const,
    color: COLOR,
    letterSpacing: "0.06em",
  },
  desc: { fontSize: 10, color: "#6b7280", lineHeight: 1.4 },
  portRow: { display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" as const },
  portDir: { fontSize: 9, fontWeight: 700, color: "#9ca3af", minWidth: 18 },
  portTag: {
    fontSize: 9,
    background: "#fef3c7",
    color: "#92400e",
    borderRadius: 3,
    padding: "1px 4px",
  },
  portMore: { fontSize: 9, color: "#9ca3af" },
  handle: { width: 8, height: 8, background: COLOR },
};
