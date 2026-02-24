import { useState, useEffect, useRef } from "react";
import { useNfcoreModules } from "../hooks/useNfcoreModules";
import { fetchNfcoreModules } from "../api/nfcoreClient";
import type { NfCoreModule, NfCorePipeline } from "../types/nfcore";

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
    description: "FASTQ or BAM",
    borderColor: "#3b82f6",
    headerColor: "#3b82f6",
  },
  {
    type: "fastqToBam",
    label: "FASTQ → BAM",
    icon: "🔄",
    description: "Convert via samtools",
    borderColor: "#7c3aed",
    headerColor: "#7c3aed",
  },
  {
    type: "hlaTyping",
    label: "HLA-HD Typing",
    icon: "🧬",
    description: "HLA allele calling",
    borderColor: "#2563eb",
    headerColor: "#2563eb",
  },
  {
    type: "results",
    label: "Results",
    icon: "📊",
    description: "HLA allele output",
    borderColor: "#16a34a",
    headerColor: "#16a34a",
  },
];

export function NodePalette({ onExpandPipeline }: NodePaletteProps) {
  const { status, categories, pipelines, loading, fetchCatalogMeta } =
    useNfcoreModules();

  const [expandingId, setExpandingId] = useState<string | null>(null);
  const [moduleQuery, setModuleQuery] = useState("");
  const [pipelineQuery, setPipelineQuery] = useState("");
  const [expandedCat, setExpandedCat] = useState<string | null>(null);
  const [catModules, setCatModules] = useState<Record<string, NfCoreModule[]>>({});
  const [catLoading, setCatLoading] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<NfCoreModule[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchCatalogMeta();
  }, [fetchCatalogMeta]);

  // Debounced module search
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    if (moduleQuery.trim().length < 2) {
      setSearchResults(null);
      return;
    }
    searchTimerRef.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const results = await fetchNfcoreModules(moduleQuery.trim(), undefined, 30);
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [moduleQuery]);

  async function handleCategoryToggle(cat: string) {
    if (expandedCat === cat) {
      setExpandedCat(null);
      return;
    }
    setExpandedCat(cat);
    if (!catModules[cat]) {
      setCatLoading(cat);
      try {
        const mods = await fetchNfcoreModules(undefined, cat, 100);
        setCatModules((prev) => ({ ...prev, [cat]: mods }));
      } catch {
        setCatModules((prev) => ({ ...prev, [cat]: [] }));
      } finally {
        setCatLoading(null);
      }
    }
  }

  function handleBuiltinDragStart(e: React.DragEvent, nodeType: string) {
    e.dataTransfer.setData("nodeType", nodeType);
    e.dataTransfer.effectAllowed = "move";
  }

  function handleModuleDragStart(e: React.DragEvent, mod: NfCoreModule) {
    e.dataTransfer.setData("nodeType", "nfcoreModule");
    e.dataTransfer.setData(
      "nodeData",
      JSON.stringify({
        label: mod.id,
        tool: mod.tool,
        subcommand: mod.subcommand,
        description: mod.description,
        category: mod.category,
        inputs: mod.inputs,
        outputs: mod.outputs,
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

  const filteredPipelines = pipelineQuery.trim()
    ? pipelines.filter(
        (p) =>
          p.id.toLowerCase().includes(pipelineQuery.toLowerCase()) ||
          p.full_name.toLowerCase().includes(pipelineQuery.toLowerCase())
      )
    : pipelines.slice(0, 15);

  const showSearchResults = moduleQuery.trim().length >= 2;
  const searchModules = searchResults ?? [];

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

      {/* nf-core Modules */}
      <div style={styles.sectionTitle}>
        nf-core Modules
        {status && <span style={styles.countBadge}>{status.modules}</span>}
      </div>

      <input
        type="text"
        placeholder="Search modules…"
        value={moduleQuery}
        onChange={(e) => setModuleQuery(e.target.value)}
        style={styles.searchInput}
      />

      {!status?.ready && !loading && (
        <div style={styles.notReady}>Catalog loading in background…</div>
      )}

      {showSearchResults ? (
        // Search results view
        searchLoading ? (
          <div style={styles.hint}>Searching…</div>
        ) : searchModules.length === 0 ? (
          <div style={styles.hint}>No results</div>
        ) : (
          <div style={styles.itemList}>
            {searchModules.map((mod) => (
              <div
                key={mod.id}
                draggable
                onDragStart={(e) => handleModuleDragStart(e, mod)}
                style={styles.moduleItem}
                title={mod.description ?? mod.id}
              >
                <span style={styles.moduleIcon}>🔧</span>
                <div style={styles.moduleInfo}>
                  <div style={styles.moduleId}>{mod.id}</div>
                  <div style={styles.moduleCat}>{mod.category}</div>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        // Category accordion
        <div style={styles.accordion}>
          {loading && categories.length === 0 && (
            <div style={styles.hint}>Loading…</div>
          )}
          {!loading && categories.length === 0 && (
            <div style={styles.hint}>
              {status?.ready ? "No categories" : "Waiting for catalog…"}
            </div>
          )}
          {categories.map((cat) => {
            const isExpanded = expandedCat === cat.category;
            return (
              <div key={cat.category}>
                <button
                  style={{
                    ...styles.catHeader,
                    background: isExpanded ? "#f3f4f6" : "none",
                  }}
                  onClick={() => handleCategoryToggle(cat.category)}
                >
                  <span style={styles.catArrow}>{isExpanded ? "▼" : "▶"}</span>
                  <span style={styles.catName}>{cat.category}</span>
                  <span style={styles.catCount}>{cat.count}</span>
                </button>
                {isExpanded && (
                  <div style={styles.catBody}>
                    {catLoading === cat.category ? (
                      <div style={styles.hint}>Loading…</div>
                    ) : (catModules[cat.category] ?? []).length === 0 ? (
                      <div style={styles.hint}>No modules</div>
                    ) : (
                      (catModules[cat.category] ?? []).map((mod) => (
                        <div
                          key={mod.id}
                          draggable
                          onDragStart={(e) => handleModuleDragStart(e, mod)}
                          style={styles.moduleItem}
                          title={mod.description ?? mod.id}
                        >
                          <span style={styles.moduleIcon}>🔧</span>
                          <div style={styles.moduleInfo}>
                            <div style={styles.moduleId}>{mod.id}</div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div style={styles.divider} />

      {/* nf-core Pipelines */}
      <div style={styles.sectionTitle}>
        nf-core Pipelines
        {status && <span style={styles.countBadge}>{status.pipelines}</span>}
      </div>

      <input
        type="text"
        placeholder="Search pipelines…"
        value={pipelineQuery}
        onChange={(e) => setPipelineQuery(e.target.value)}
        style={styles.searchInput}
      />

      <div style={styles.itemList}>
        {filteredPipelines.map((pipe) => (
          <div key={pipe.id} style={styles.pipelineItem}>
            {/* Draggable area — adds pipeline as a single block node */}
            <div
              draggable
              onDragStart={(e) => handlePipelineDragStart(e, pipe)}
              style={styles.pipelineDragArea}
              title={`Drag to add as single block\n${pipe.description ?? ""}`}
            >
              <div style={styles.pipelineName}>{pipe.id}</div>
              {pipe.stars > 0 && (
                <div style={styles.pipelineStars}>
                  ⭐ {pipe.stars.toLocaleString()}
                </div>
              )}
            </div>
            {/* Expand button — drops all pipeline modules onto canvas */}
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
        {filteredPipelines.length === 0 && (
          <div style={styles.hint}>No pipelines</div>
        )}
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
  searchInput: {
    width: "100%",
    padding: "5px 8px",
    fontSize: 11,
    border: "1px solid #d1d5db",
    borderRadius: 4,
    background: "#fff",
    outline: "none",
    boxSizing: "border-box",
  },
  notReady: { fontSize: 10, color: "#f59e0b", fontStyle: "italic" },
  accordion: { display: "flex", flexDirection: "column", gap: 1 },
  catHeader: {
    width: "100%",
    border: "none",
    borderRadius: 4,
    padding: "5px 6px",
    display: "flex",
    alignItems: "center",
    gap: 4,
    cursor: "pointer",
    textAlign: "left",
    fontSize: 11,
    color: "#374151",
  },
  catArrow: { fontSize: 9, color: "#9ca3af", minWidth: 10 },
  catName: { flex: 1, fontWeight: 600, fontSize: 11 },
  catCount: { fontSize: 10, color: "#9ca3af" },
  catBody: {
    paddingLeft: 8,
    display: "flex",
    flexDirection: "column",
    gap: 2,
    marginBottom: 4,
  },
  itemList: { display: "flex", flexDirection: "column", gap: 2 },
  moduleItem: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    padding: "4px 6px",
    borderRadius: 4,
    cursor: "grab",
    background: "#fff",
    border: "1px solid #e5e7eb",
    userSelect: "none",
  },
  moduleIcon: { fontSize: 11, flexShrink: 0 },
  moduleInfo: { flex: 1, overflow: "hidden" },
  moduleId: {
    fontSize: 10,
    fontWeight: 600,
    color: "#0891b2",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  moduleCat: { fontSize: 9, color: "#9ca3af" },
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
