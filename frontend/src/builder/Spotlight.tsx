import { useState, useEffect, useRef, useCallback } from "react";
import type { NfCoreModule, NfCorePipeline } from "../types/nfcore";
import type { SnakemakeWrapper } from "../types/snakemake";
import { fetchNfcoreModules, fetchNfcorePipelines } from "../api/nfcoreClient";
import { fetchWrappers } from "../api/snakemakeClient";
import { PIPELINE_TEMPLATES, type PipelineTemplate } from "./templates";

// ── Action types ──────────────────────────────────────────────────────────

type CommandAction = {
  kind: "command";
  id: string;
  label: string;
  description: string;
  icon: string;
};
type TemplateAction = { kind: "template"; template: PipelineTemplate };
type ModuleAction   = { kind: "module";   module:   NfCoreModule      };
type PipelineAction = { kind: "pipeline"; pipeline: NfCorePipeline    };
type WrapperAction  = { kind: "wrapper";  wrapper:  SnakemakeWrapper  };
type SpotlightItem  = CommandAction | TemplateAction | ModuleAction | PipelineAction | WrapperAction;

const COMMANDS: CommandAction[] = [
  { kind: "command", id: "new",       label: "New Pipeline",     description: "Clear canvas and start fresh",         icon: "✨" },
  { kind: "command", id: "save",      label: "Save Pipeline",    description: "Save current pipeline to the database", icon: "💾" },
  { kind: "command", id: "run",       label: "Run Pipeline",     description: "Execute the current pipeline",          icon: "▶" },
  { kind: "command", id: "undo",      label: "Undo",             description: "Undo last canvas action",              icon: "↩" },
  { kind: "command", id: "redo",      label: "Redo",             description: "Redo last undone action",              icon: "↪" },
  { kind: "command", id: "templates", label: "Browse Templates", description: "Open the template gallery",            icon: "📋" },
];

// ── Props ─────────────────────────────────────────────────────────────────

interface SpotlightProps {
  onClose:        () => void;
  onCommand:      (id: string) => void;
  onTemplate:     (template: PipelineTemplate) => void;
  onAddModule:    (module: NfCoreModule) => void;
  onAddPipeline:  (pipeline: NfCorePipeline) => void;
  onAddWrapper:   (wrapper: SnakemakeWrapper) => void;
}

// ── Component ─────────────────────────────────────────────────────────────

export function Spotlight({
  onClose,
  onCommand,
  onTemplate,
  onAddModule,
  onAddPipeline,
  onAddWrapper,
}: SpotlightProps) {
  const [query,     setQuery]     = useState("");
  const [modules,   setModules]   = useState<NfCoreModule[]>([]);
  const [pipelines, setPipelines] = useState<NfCorePipeline[]>([]);
  const [wrappers,  setWrappers]  = useState<SnakemakeWrapper[]>([]);
  const [loading,   setLoading]   = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-focus on mount
  useEffect(() => { inputRef.current?.focus(); }, []);

  // Debounced API search when query is long enough
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (query.length < 2) {
      setModules([]);
      setPipelines([]);
      setWrappers([]);
      return;
    }
    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const [mods, pipes, wraps] = await Promise.all([
          fetchNfcoreModules(query, undefined, 8),
          fetchNfcorePipelines(query),
          fetchWrappers(query, undefined, 8),
        ]);
        setModules(mods.slice(0, 6));
        setPipelines(pipes.slice(0, 4));
        setWrappers(wraps.slice(0, 6));
      } catch {
        // silently ignore network errors in spotlight
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query]);

  // Reset cursor when results change
  useEffect(() => { setActiveIdx(0); }, [query, modules.length, pipelines.length, wrappers.length]);

  // ── Build filtered sections ─────────────────────────────────────────────

  const q = query.toLowerCase();

  const filteredCommands = COMMANDS.filter(
    (c) => !q || c.label.toLowerCase().includes(q) || c.description.toLowerCase().includes(q)
  );

  const filteredTemplates = PIPELINE_TEMPLATES.filter(
    (t) =>
      !q ||
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.tags.some((tag) => tag.toLowerCase().includes(q))
  );

  const sections: Array<{ heading: string; items: SpotlightItem[] }> = [];
  if (filteredCommands.length)  sections.push({ heading: "Commands",              items: filteredCommands });
  if (filteredTemplates.length) sections.push({ heading: "Templates",             items: filteredTemplates.map((t) => ({ kind: "template" as const, template: t })) });
  if (wrappers.length)          sections.push({ heading: "Snakemake Wrappers",    items: wrappers.map((w)  => ({ kind: "wrapper"  as const, wrapper:  w })) });
  if (modules.length)           sections.push({ heading: "nf-core Modules",       items: modules.map((m)   => ({ kind: "module"   as const, module:   m })) });
  if (pipelines.length)         sections.push({ heading: "nf-core Pipelines",     items: pipelines.map((p) => ({ kind: "pipeline" as const, pipeline: p })) });

  const allItems: SpotlightItem[] = sections.flatMap((s) => s.items);

  // Pre-compute section start indices for flat keyboard navigation
  const sectionStarts: number[] = [];
  let offset = 0;
  for (const sec of sections) {
    sectionStarts.push(offset);
    offset += sec.items.length;
  }

  // ── Actions ────────────────────────────────────────────────────────────

  function handleSelect(item: SpotlightItem) {
    if      (item.kind === "command")  { onCommand(item.id);           onClose(); }
    else if (item.kind === "template") { onTemplate(item.template);    onClose(); }
    else if (item.kind === "wrapper")  { onAddWrapper(item.wrapper);   onClose(); }
    else if (item.kind === "module")   { onAddModule(item.module);     onClose(); }
    else if (item.kind === "pipeline") { onAddPipeline(item.pipeline); onClose(); }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { onClose(); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, allItems.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    }
    if (e.key === "Enter" && allItems[activeIdx]) {
      handleSelect(allItems[activeIdx]);
    }
  }

  // Scroll active item into view
  const activeItemRef = useCallback((el: HTMLDivElement | null) => {
    if (el) el.scrollIntoView({ block: "nearest" });
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div style={s.backdrop} onClick={onClose}>
      <div style={s.panel} onClick={(e) => e.stopPropagation()}>

        {/* Search input */}
        <div style={s.inputRow}>
          <span style={s.searchLabel}>⌘K</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search commands, templates, modules…"
            style={s.input}
          />
          {loading && <span style={s.spinner}>↻</span>}
          <button onClick={onClose} style={s.closeBtn}>✕</button>
        </div>

        {/* Results */}
        <div style={s.results}>
          {sections.length === 0 && !loading && (
            <div style={s.empty}>
              {query ? `No results for "${query}"` : "Type to search…"}
            </div>
          )}

          {sections.map((section, si) => (
            <div key={section.heading}>
              <div style={s.sectionHeading}>{section.heading}</div>
              {section.items.map((item, ii) => {
                const idx      = sectionStarts[si] + ii;
                const isActive = idx === activeIdx;
                return (
                  <div
                    key={idx}
                    ref={isActive ? activeItemRef : undefined}
                    style={{ ...s.item, ...(isActive ? s.itemActive : {}) }}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => handleSelect(item)}
                  >
                    <ItemContent item={item} />
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer hints */}
        <div style={s.footer}>
          <span style={s.hint}><kbd style={s.kbd}>↑↓</kbd> navigate</span>
          <span style={s.hint}><kbd style={s.kbd}>↵</kbd> select</span>
          <span style={s.hint}><kbd style={s.kbd}>Esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}

// ── Item content renderers ────────────────────────────────────────────────

function ItemContent({ item }: { item: SpotlightItem }) {
  if (item.kind === "command") {
    return (
      <>
        <span style={s.itemIcon}>{item.icon}</span>
        <div style={s.itemText}>
          <span style={s.itemLabel}>{item.label}</span>
          <span style={s.itemDesc}>{item.description}</span>
        </div>
      </>
    );
  }
  if (item.kind === "template") {
    return (
      <>
        <span style={s.itemIcon}>{item.template.icon}</span>
        <div style={s.itemText}>
          <span style={s.itemLabel}>{item.template.name}</span>
          <span style={s.itemDesc}>{item.template.description}</span>
        </div>
        <div style={s.tags}>
          {item.template.tags.slice(0, 2).map((t) => (
            <span key={t} style={s.tag}>{t}</span>
          ))}
        </div>
      </>
    );
  }
  if (item.kind === "wrapper") {
    return (
      <>
        <span style={s.itemIcon}>🐍</span>
        <div style={s.itemText}>
          <span style={s.itemLabel}>{item.wrapper.id}</span>
          <span style={s.itemDesc}>{item.wrapper.description ?? item.wrapper.category}</span>
        </div>
        <span style={{ ...s.badge, background: "#fef3c7", color: "#92400e" }}>Wrapper</span>
      </>
    );
  }
  if (item.kind === "module") {
    return (
      <>
        <span style={s.itemIcon}>🔧</span>
        <div style={s.itemText}>
          <span style={s.itemLabel}>{item.module.id}</span>
          <span style={s.itemDesc}>{item.module.description ?? item.module.category}</span>
        </div>
        <span style={s.badge}>Module</span>
      </>
    );
  }
  // pipeline
  return (
    <>
      <span style={s.itemIcon}>⚡</span>
      <div style={s.itemText}>
        <span style={s.itemLabel}>{item.pipeline.full_name}</span>
        <span style={s.itemDesc}>{item.pipeline.description ?? ""}</span>
      </div>
      <span style={{ ...s.badge, background: "#dbeafe", color: "#1d4ed8" }}>Pipeline</span>
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  backdrop: {
    position: "fixed", inset: 0,
    background: "rgba(0,0,0,0.45)",
    display: "flex", alignItems: "flex-start", justifyContent: "center",
    paddingTop: "12vh",
    zIndex: 200,
    backdropFilter: "blur(2px)",
  },
  panel: {
    width: "min(640px, 94vw)",
    background: "#fff",
    borderRadius: 12,
    boxShadow: "0 24px 64px rgba(0,0,0,0.22), 0 4px 16px rgba(0,0,0,0.12)",
    display: "flex", flexDirection: "column",
    overflow: "hidden",
    maxHeight: "72vh",
  },
  inputRow: {
    display: "flex", alignItems: "center", gap: 8,
    padding: "12px 16px",
    borderBottom: "1px solid #e5e7eb",
  },
  searchLabel: {
    fontSize: 11, fontWeight: 700, color: "#6b7280",
    background: "#f3f4f6", padding: "2px 6px", borderRadius: 4,
    letterSpacing: "0.05em", flexShrink: 0,
  },
  input: {
    flex: 1, border: "none", outline: "none",
    fontSize: 15, color: "#111827", background: "transparent",
  },
  spinner: {
    fontSize: 16, color: "#6b7280",
    animation: "spin 1s linear infinite",
    display: "inline-block",
  },
  closeBtn: {
    border: "none", background: "none", cursor: "pointer",
    color: "#9ca3af", fontSize: 16, padding: "2px 4px",
    borderRadius: 4,
  },
  results: {
    flex: 1, overflowY: "auto",
    padding: "8px 0",
  },
  empty: {
    padding: "24px 16px", textAlign: "center",
    color: "#9ca3af", fontSize: 14,
  },
  sectionHeading: {
    padding: "6px 16px 2px",
    fontSize: 10, fontWeight: 700,
    color: "#9ca3af", letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  item: {
    display: "flex", alignItems: "center", gap: 12,
    padding: "8px 16px",
    cursor: "pointer",
    borderRadius: 0,
    transition: "background 0.1s",
  },
  itemActive: {
    background: "#eff6ff",
  },
  itemIcon: {
    fontSize: 18, flexShrink: 0, width: 24, textAlign: "center",
  },
  itemText: {
    flex: 1, minWidth: 0,
    display: "flex", flexDirection: "column", gap: 1,
  },
  itemLabel: {
    fontSize: 13, fontWeight: 600, color: "#111827",
    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
  },
  itemDesc: {
    fontSize: 11, color: "#6b7280",
    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
  },
  tags: {
    display: "flex", gap: 4, flexShrink: 0,
  },
  tag: {
    fontSize: 10, fontWeight: 500,
    background: "#f0fdf4", color: "#166534",
    border: "1px solid #bbf7d0",
    padding: "1px 6px", borderRadius: 10,
  },
  badge: {
    fontSize: 10, fontWeight: 600,
    background: "#f0fdf4", color: "#166534",
    padding: "2px 8px", borderRadius: 10,
    flexShrink: 0,
  },
  footer: {
    display: "flex", gap: 16,
    padding: "8px 16px",
    borderTop: "1px solid #f3f4f6",
    background: "#fafafa",
  },
  hint: {
    display: "flex", alignItems: "center", gap: 4,
    fontSize: 11, color: "#9ca3af",
  },
  kbd: {
    background: "#e5e7eb", color: "#374151",
    borderRadius: 4, padding: "1px 5px",
    fontSize: 10, fontWeight: 600,
    border: "1px solid #d1d5db",
  },
};
