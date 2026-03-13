import { Handle, Position, useReactFlow, useEdges, useNodes } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import type { NfCoreIOPort } from "../../types/nfcore";

interface OutputHint {
  icon: string;
  label: string;
}

function patternToHint(pattern: string): OutputHint | null {
  const p = pattern.toLowerCase();
  if (/\.(bam|cram|sam)/.test(p))     return { icon: "🧬", label: "Alignment" };
  if (/\.(vcf|bcf|gvcf)/.test(p))     return { icon: "🔍", label: "Variants" };
  if (/\.html/.test(p))               return { icon: "📄", label: "HTML Report" };
  if (/\.(tsv|csv)/.test(p))          return { icon: "📊", label: "Table" };
  if (/\.txt/.test(p))                return { icon: "📝", label: "Text" };
  if (/\.json/.test(p))               return { icon: "📦", label: "JSON" };
  if (/\.(fa|fasta|fna)/.test(p))     return { icon: "🔬", label: "FASTA" };
  if (/\.(fastq|fq)/.test(p))         return { icon: "🧬", label: "FASTQ" };
  if (/\.pdf/.test(p))                return { icon: "📑", label: "PDF" };
  if (/\.(png|svg|jpg|tiff?)/.test(p))return { icon: "🖼️", label: "Image" };
  return null;
}

function deriveOutputHints(nodeId: string, edges: Edge[], nodes: Node[]): OutputHint[] | null {
  const inEdges = edges.filter(
    (e) => e.target === nodeId && e.targetHandle === "result-in"
  );
  if (inEdges.length === 0) return null;

  const hints: OutputHint[] = [];
  const seen = new Set<string>();
  function addHint(h: OutputHint) {
    const k = `${h.icon}${h.label}`;
    if (!seen.has(k)) { seen.add(k); hints.push(h); }
  }

  for (const edge of inEdges) {
    const src = nodes.find((n) => n.id === edge.source);
    if (!src) continue;

    if (src.type === "nfcorePipeline") {
      addHint({ icon: "📦", label: "Pipeline Output" });
      continue;
    }
    if (src.type === "nfcoreModule") {
      const sh = edge.sourceHandle ?? "";
      if (sh.startsWith("nfc-out-")) {
        const portName = sh.slice("nfc-out-".length);
        const outputs = (src.data as { outputs?: NfCoreIOPort[] | null }).outputs;
        const port = outputs?.find((o) => o.name === portName);
        if (port?.pattern) {
          const hint = patternToHint(port.pattern);
          if (hint) { addHint(hint); continue; }
        }
        if (portName) addHint({ icon: "📁", label: portName });
      }
      continue;
    }
    addHint({ icon: "📁", label: "Output" });
  }
  return hints;
}

// ── Component ──────────────────────────────────────────────────────────────

interface ResultsNodeData {
  label: string;
  jobDone?: boolean;
  jobStatus?: "completed" | "failed";
}

interface ResultsNodeProps {
  id: string;
  data: ResultsNodeData;
}

export function ResultsNode({ id, data }: ResultsNodeProps) {
  const { setNodes, setEdges } = useReactFlow();
  const edges = useEdges();
  const nodes = useNodes();

  const hints = deriveOutputHints(id, edges, nodes);
  const isConnected = hints !== null;
  const jobDone = data.jobDone === true;
  const jobFailed = data.jobStatus === "failed";

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  function openPanel(tab?: string) {
    window.dispatchEvent(
      new CustomEvent("openResultsPanel", { detail: { tab: tab ?? "summary" } })
    );
  }

  const borderColor = jobFailed ? "#dc2626" : jobDone ? "#16a34a" : "#16a34a";
  const headerColor = jobFailed ? "#dc2626" : jobDone ? "#16a34a" : "#16a34a";

  return (
    <div style={{ ...s.node, borderColor }}>
      <Handle type="target" position={Position.Left} id="result-in" style={s.handle} />

      <div style={{ ...s.header, background: headerColor }}>
        <span style={s.icon}>📊</span>
        <span style={s.label}>{data.label}</span>
        {jobDone && !jobFailed && <span style={s.doneBadge}>✓</span>}
        {jobFailed && <span style={s.failBadge}>✗</span>}
        <button onClick={handleDelete} style={s.deleteBtn} title="Remove node">×</button>
      </div>

      <div style={s.body}>
        {!isConnected ? (
          <span style={s.hint}>Connect a module to see expected outputs.</span>
        ) : hints!.length === 0 ? (
          <span style={s.hint}>Outputs will appear here.</span>
        ) : (
          <div style={s.hintList}>
            {hints!.map((h, i) => (
              <div key={i} style={s.hintRow}>
                <span style={s.hintIcon}>{h.icon}</span>
                <span style={s.hintLabel}>{h.label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Results ready actions */}
        {jobDone && !jobFailed && (
          <div style={s.actionRow}>
            <button style={s.viewBtn} onClick={() => openPanel("summary")}>
              View Results
            </button>
            <button style={s.dlBtn} onClick={() => openPanel("downloads")} title="Downloads">
              ⬇
            </button>
          </div>
        )}
        {jobFailed && (
          <div style={s.failMsg}>Pipeline failed — check logs.</div>
        )}
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: "2px solid #16a34a",
    borderRadius: 8,
    minWidth: 160,
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
  },
  header: {
    background: "#16a34a",
    borderRadius: "6px 6px 0 0",
    padding: "6px 10px",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 14 },
  label: { color: "#fff", fontWeight: 600, fontSize: 12, flex: 1 },
  doneBadge: {
    background: "rgba(255,255,255,0.25)",
    color: "#fff",
    borderRadius: 10,
    fontSize: 10,
    padding: "1px 5px",
    fontWeight: 700,
  },
  failBadge: {
    background: "rgba(255,255,255,0.25)",
    color: "#fff",
    borderRadius: 10,
    fontSize: 10,
    padding: "1px 5px",
    fontWeight: 700,
  },
  deleteBtn: {
    marginLeft: 2,
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
  hint: { fontSize: 11, color: "#9ca3af", fontStyle: "italic" },
  hintList: { display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 },
  hintRow: { display: "flex", alignItems: "center", gap: 6 },
  hintIcon: { fontSize: 12, flexShrink: 0 },
  hintLabel: { fontSize: 11, color: "#374151", fontWeight: 500 },
  actionRow: { display: "flex", gap: 5, marginTop: 6 },
  viewBtn: {
    flex: 1,
    padding: "5px 0",
    borderRadius: 6,
    border: "none",
    background: "#16a34a",
    color: "#fff",
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
  },
  dlBtn: {
    width: 28,
    padding: "5px 0",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    background: "#fff",
    color: "#374151",
    fontSize: 12,
    cursor: "pointer",
    flexShrink: 0,
  },
  failMsg: {
    marginTop: 6,
    fontSize: 10,
    color: "#dc2626",
    background: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 4,
    padding: "3px 6px",
  },
  handle: { width: 10, height: 10, background: "#16a34a" },
};
