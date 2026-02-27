import { Handle, Position, useReactFlow } from "@xyflow/react";

export type CustomTool = "spades" | "kraken2" | "prokka" | "iqtree" | "flye";

export interface CustomPipelineNodeData {
  label: string;
  tool: CustomTool;
}

interface ToolMeta {
  name: string;
  description: string;
  inputLabel: string;
  outputLabels: string[];
  emoji: string;
}

const TOOLS: Record<CustomTool, ToolMeta> = {
  spades: {
    name: "De Novo Assembly",
    description: "SPAdes + QUAST",
    inputLabel: "FASTQ reads",
    outputLabels: ["contigs.fasta", "scaffolds.fasta", "quast_report.html"],
    emoji: "🧩",
  },
  kraken2: {
    name: "Metagenome Profiling",
    description: "Kraken2 + Bracken",
    inputLabel: "FASTQ reads",
    outputLabels: ["taxonomy_report.tsv", "bracken_report.tsv", "krona.html"],
    emoji: "🦠",
  },
  prokka: {
    name: "Prokaryote Annotation",
    description: "Prokka",
    inputLabel: "FASTA assembly",
    outputLabels: ["genome.gff", "proteins.faa", "genome.gbk"],
    emoji: "🔬",
  },
  iqtree: {
    name: "Phylogenomics",
    description: "MAFFT + IQ-TREE 2",
    inputLabel: "Multi-FASTA sequences",
    outputLabels: ["tree.nwk", "aligned.fasta", "iqtree.log"],
    emoji: "🌳",
  },
  flye: {
    name: "Long-read Assembly",
    description: "Flye + NanoStat",
    inputLabel: "Long reads (Nanopore / PacBio)",
    outputLabels: ["assembly.fasta", "assembly_info.txt", "nanostat.txt"],
    emoji: "🔗",
  },
};

const TEAL = "#0d9488";

export function CustomPipelineNode({ id, data }: { id: string; data: CustomPipelineNodeData }) {
  const { updateNodeData, deleteElements, getNode } = useReactFlow();
  const tool = data.tool ?? "spades";
  const meta = TOOLS[tool];

  function handleDelete() {
    const node = getNode(id);
    if (node) deleteElements({ nodes: [node] });
  }

  return (
    <div style={s.card}>
      {/* Left handle — input */}
      <Handle
        type="target"
        position={Position.Left}
        id="custom-in"
        style={s.handle}
        title={`Input: ${meta.inputLabel}`}
      />

      {/* Header */}
      <div style={s.header}>
        <span style={s.emoji}>{meta.emoji}</span>
        <span style={s.title}>Custom Pipeline</span>
        <button onClick={handleDelete} style={s.deleteBtn} title="Remove node">×</button>
      </div>

      {/* Tool selector */}
      <div style={s.body}>
        <label style={s.label}>Tool</label>
        <select
          value={tool}
          onChange={(e) => updateNodeData(id, { tool: e.target.value as CustomTool, label: TOOLS[e.target.value as CustomTool].name })}
          style={s.select}
        >
          {(Object.keys(TOOLS) as CustomTool[]).map((key) => (
            <option key={key} value={key}>{TOOLS[key].emoji} {TOOLS[key].name}</option>
          ))}
        </select>
        <div style={s.desc}>{meta.description}</div>

        <div style={s.ioSection}>
          <div style={s.ioRow}>
            <span style={s.ioIcon}>⬅</span>
            <span style={s.ioText}>{meta.inputLabel}</span>
          </div>
          <div style={{ ...s.ioRow, marginTop: 4 }}>
            <span style={s.ioIcon}>➡</span>
            <span style={s.ioText}>{meta.outputLabels.slice(0, 2).join(", ")}{meta.outputLabels.length > 2 ? ` +${meta.outputLabels.length - 2}` : ""}</span>
          </div>
        </div>
      </div>

      {/* Right handle — output */}
      <Handle
        type="source"
        position={Position.Right}
        id="custom-out"
        style={s.handle}
        title="Analysis results"
      />
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  card: {
    background: "#fff",
    border: `2px solid ${TEAL}`,
    borderRadius: 10,
    minWidth: 210,
    maxWidth: 240,
    boxShadow: "0 2px 8px rgba(13,148,136,0.15)",
    fontSize: 12,
    position: "relative",
  },
  header: {
    background: TEAL,
    color: "#fff",
    padding: "7px 10px",
    borderRadius: "8px 8px 0 0",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  emoji: { fontSize: 14 },
  title: { fontWeight: 700, fontSize: 12, flex: 1 },
  deleteBtn: {
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.8)",
    cursor: "pointer",
    fontSize: 16,
    lineHeight: 1,
    padding: "0 2px",
    flexShrink: 0,
  },
  body: { padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 },
  label: { fontSize: 10, fontWeight: 600, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.04em" },
  select: {
    width: "100%",
    padding: "5px 8px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    fontSize: 12,
    background: "#fff",
    cursor: "pointer",
  },
  desc: { fontSize: 10, color: "#6b7280", fontStyle: "italic" },
  ioSection: {
    background: "#f0fdfa",
    border: "1px solid #ccfbf1",
    borderRadius: 6,
    padding: "6px 8px",
    marginTop: 2,
    display: "flex",
    flexDirection: "column",
    gap: 3,
  },
  ioRow: { display: "flex", alignItems: "flex-start", gap: 5 },
  ioIcon: { fontSize: 9, color: TEAL, flexShrink: 0, marginTop: 1 },
  ioText: { fontSize: 10, color: "#374151", lineHeight: 1.4 },
  handle: {
    width: 10,
    height: 10,
    background: TEAL,
    border: "2px solid #fff",
    borderRadius: "50%",
  },
};
