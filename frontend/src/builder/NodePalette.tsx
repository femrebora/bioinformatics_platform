import { useState, useEffect } from "react";
import { useNfcoreModules } from "../hooks/useNfcoreModules";
import type { NfCorePipeline } from "../types/nfcore";

interface NodePaletteProps {
  onExpandPipeline: (pipelineId: string) => Promise<void>;
}

interface PaletteCard {
  type: string;
  label: string;
  icon: string;
  description: string;
  borderColor: string;
  headerColor: string;
}

const BUILTIN_CARDS: PaletteCard[] = [
  {
    type: "inputFile",
    label: "Input File",
    icon: "📂",
    description: "FASTQ / BAM (paired-end ok)",
    borderColor: "#3b82f6",
    headerColor: "#3b82f6",
  },
  {
    type: "sampleSheetBuilder",
    label: "Sample Sheet",
    icon: "🗂️",
    description: "Multi-sample + conditions + strandedness",
    borderColor: "#7c3aed",
    headerColor: "#7c3aed",
  },
  {
    type: "results",
    label: "Results",
    icon: "📊",
    description: "View pipeline output",
    borderColor: "#16a34a",
    headerColor: "#16a34a",
  },
];

export function NodePalette({ onExpandPipeline }: NodePaletteProps) {
  const { status, pipelines, fetchCatalogMeta } = useNfcoreModules();
  const [expandingId, setExpandingId] = useState<string | null>(null);

  useEffect(() => {
    fetchCatalogMeta();
  }, [fetchCatalogMeta]);

  // Only expose sarek
  const sarekPipelines: NfCorePipeline[] = pipelines.filter((p) => p.id === "sarek");

  function handleBuiltinDragStart(e: React.DragEvent, nodeType: string) {
    e.dataTransfer.setData("nodeType", nodeType);
    e.dataTransfer.effectAllowed = "move";
  }

  function handlePipelineDragStart(e: React.DragEvent, pipe: NfCorePipeline) {
    e.dataTransfer.setData("nodeType", "nfcorePipeline");
    e.dataTransfer.setData(
      "nodeData",
      JSON.stringify({
        label: pipe.full_name,
        pipelineId: pipe.id,
        description: pipe.description,
        stars: pipe.stars,
        inputFormats: pipe.input_formats ?? [],
      })
    );
    e.dataTransfer.effectAllowed = "move";
  }

  async function handleExpand(e: React.MouseEvent, pipelineId: string) {
    e.stopPropagation();
    setExpandingId(pipelineId);
    try {
      await onExpandPipeline(pipelineId);
    } finally {
      setExpandingId(null);
    }
  }

  return (
    <aside style={styles.palette}>
      {/* Built-in nodes */}
      <div style={styles.sectionTitle}>Built-in</div>
      {BUILTIN_CARDS.map((card) => (
        <div
          key={card.type}
          draggable
          onDragStart={(e) => handleBuiltinDragStart(e, card.type)}
          style={{ ...styles.card, borderColor: card.borderColor }}
        >
          <div style={{ ...styles.cardHeader, background: card.headerColor }}>
            <span style={styles.cardIcon}>{card.icon}</span>
            <span style={styles.cardLabel}>{card.label}</span>
          </div>
          <div style={styles.cardDesc}>{card.description}</div>
        </div>
      ))}

      <div style={styles.divider} />

      {/* nf-core/sarek */}
      <div style={styles.sectionTitle}>
        nf-core Pipelines
        {status && <span style={styles.countBadge}>sarek</span>}
      </div>

      <div style={styles.itemList}>
        {sarekPipelines.length === 0 && (
          <div style={styles.hint}>Loading catalog…</div>
        )}
        {sarekPipelines.map((pipe) => (
          <div key={pipe.id} style={styles.pipelineItem}>
            <div
              draggable
              onDragStart={(e) => handlePipelineDragStart(e, pipe)}
              style={styles.pipelineDragArea}
              title={`Drag to add nf-core/sarek\n${pipe.description ?? ""}`}
            >
              <div style={styles.pipelineName}>{pipe.id}</div>
              {pipe.stars > 0 && (
                <div style={styles.pipelineStars}>
                  ⭐ {pipe.stars.toLocaleString()}
                </div>
              )}
            </div>
            <button
              style={{
                ...styles.expandBtn,
                opacity: expandingId === pipe.id ? 0.5 : 1,
              }}
              onClick={(e) => handleExpand(e, pipe.id)}
              disabled={expandingId === pipe.id}
              title="Expand into individual modules"
            >
              {expandingId === pipe.id ? "…" : "⊞"}
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

const styles: Record<string, React.CSSProperties> = {
  palette: {
    width: 240,
    flexShrink: 0,
    borderRight: "1px solid #e5e7eb",
    background: "#f9fafb",
    padding: "10px 8px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    overflowY: "auto",
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: 700,
    color: "#6b7280",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  countBadge: {
    background: "#e5e7eb",
    color: "#374151",
    borderRadius: 10,
    padding: "1px 6px",
    fontSize: 9,
    fontWeight: 600,
  },
  divider: { height: 1, background: "#e5e7eb", margin: "2px 0" },
  card: {
    border: "2px solid",
    borderRadius: 6,
    cursor: "grab",
    overflow: "hidden",
    background: "#fff",
    userSelect: "none",
  },
  cardHeader: {
    padding: "5px 8px",
    display: "flex",
    alignItems: "center",
    gap: 5,
  },
  cardIcon: { fontSize: 12 },
  cardLabel: { color: "#fff", fontSize: 11, fontWeight: 600 },
  cardDesc: { padding: "5px 8px", fontSize: 11, color: "#6b7280" },
  itemList: { display: "flex", flexDirection: "column", gap: 2 },
  pipelineItem: {
    display: "flex",
    alignItems: "stretch",
    borderRadius: 4,
    background: "#fff",
    border: "1px solid #e5e7eb",
    overflow: "hidden",
  },
  pipelineDragArea: {
    flex: 1,
    padding: "5px 8px",
    cursor: "grab",
    userSelect: "none",
  },
  pipelineName: {
    fontSize: 10,
    fontWeight: 600,
    color: "#0e7490",
  },
  pipelineStars: { fontSize: 9, color: "#9ca3af", marginTop: 1 },
  expandBtn: {
    flexShrink: 0,
    padding: "0 8px",
    background: "none",
    border: "none",
    borderLeft: "1px solid #e5e7eb",
    cursor: "pointer",
    fontSize: 14,
    color: "#0e7490",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  hint: {
    fontSize: 10,
    color: "#9ca3af",
    textAlign: "center",
    padding: "6px 0",
    fontStyle: "italic",
  },
};
