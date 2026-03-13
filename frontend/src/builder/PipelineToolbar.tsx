import type { PipelineListItem } from "../types/pipeline";

interface PipelineToolbarProps {
  pipelineName:    string;
  onNameChange:    (name: string) => void;
  savedPipelines:  PipelineListItem[];
  activePipelineId: string | null;
  onSave:          () => void;
  onLoad:          (pipelineId: string) => void;
  onNew:           () => void;
  onDelete:        () => void;
  onRun:           () => void;
  onUndo:          () => void;
  onRedo:          () => void;
  onTemplates:     () => void;
  onSpotlight:     () => void;
  canRun:          boolean;
  canUndo:         boolean;
  canRedo:         boolean;
  saving:          boolean;
  validationErrors: string[];
  pipelineType?:   string;
}

export function PipelineToolbar({
  pipelineName,
  onNameChange,
  savedPipelines,
  activePipelineId,
  onSave,
  onLoad,
  onNew,
  onDelete,
  onRun,
  onUndo,
  onRedo,
  onTemplates,
  onSpotlight,
  canRun,
  canUndo,
  canRedo,
  saving,
  validationErrors,
  pipelineType,
}: PipelineToolbarProps) {
  const badgeColors: Record<string, { bg: string; text: string; border: string }> = {
    "nf-core":   { bg: "#dcfce7", text: "#15803d", border: "#bbf7d0" },
    "Snakemake": { bg: "#fef3c7", text: "#92400e", border: "#fde68a" },
    "BioScript": { bg: "#f3e8ff", text: "#6d28d9", border: "#e9d5ff" },
    "Custom":    { bg: "#ccfbf1", text: "#0f766e", border: "#99f6e4" },
    "Mixed":      { bg: "#fef9c3", text: "#854d0e", border: "#fde68a" },
    "Assessment": { bg: "#fef3c7", text: "#92400e", border: "#fed7aa" },
  };
  const badge = pipelineType ? badgeColors[pipelineType] : null;
  return (
    <div style={s.wrapper}>
      <div style={s.toolbar}>

        {/* Pipeline name */}
        <input
          type="text"
          value={pipelineName}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Pipeline name…"
          style={s.nameInput}
        />

        {badge && (
          <span style={{ padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700, background: badge.bg, color: badge.text, border: `1px solid ${badge.border}`, flexShrink: 0, whiteSpace: "nowrap" as const }}>
            {pipelineType}
          </span>
        )}

        {/* Save / Load / New / Delete */}
        <button onClick={onSave} disabled={saving || !pipelineName.trim()} style={s.btn}>
          {saving ? "Saving…" : activePipelineId ? "Save" : "Save New"}
        </button>

        <select
          value=""
          onChange={(e) => e.target.value && onLoad(e.target.value)}
          style={s.loadSelect}
        >
          <option value="">Load…</option>
          {savedPipelines.map((p) => (
            <option key={p.pipeline_id} value={p.pipeline_id}>{p.name}</option>
          ))}
        </select>

        <button onClick={onNew} style={s.btn}>New</button>

        <button
          onClick={onDelete}
          disabled={!activePipelineId}
          style={{ ...s.btn, ...s.deleteBtn }}
        >
          Delete
        </button>

        <div style={s.divider} />

        {/* Templates */}
        <button onClick={onTemplates} style={s.btn} title="Browse pipeline templates">
          📋 Templates
        </button>

        {/* Undo / Redo */}
        <button
          onClick={onUndo}
          disabled={!canUndo}
          style={{ ...s.btn, opacity: canUndo ? 1 : 0.4 }}
          title="Undo (Ctrl+Z)"
        >
          ↩
        </button>
        <button
          onClick={onRedo}
          disabled={!canRedo}
          style={{ ...s.btn, opacity: canRedo ? 1 : 0.4 }}
          title="Redo (Ctrl+Shift+Z)"
        >
          ↪
        </button>

        <div style={s.divider} />

        {/* Spotlight */}
        <button onClick={onSpotlight} style={s.spotlightBtn} title="Open command palette (Ctrl+K)">
          ⌘K
        </button>

        {/* Run */}
        <button
          onClick={onRun}
          disabled={!canRun}
          style={{ ...s.btn, ...s.runBtn, opacity: canRun ? 1 : 0.5 }}
          title="Run pipeline"
        >
          ▶ Run
        </button>
      </div>

      {validationErrors.length > 0 && (
        <ul style={s.errorList}>
          {validationErrors.map((err, i) => (
            <li key={i} style={s.errorItem}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  wrapper: {
    borderBottom: "1px solid #e5e7eb",
    background: "#fff",
  },
  toolbar: {
    padding: "8px 12px",
    display: "flex",
    alignItems: "center",
    gap: 6,
    flexWrap: "nowrap" as const,
    overflowX: "auto" as const,
  },
  nameInput: {
    flex: "0 0 180px",
    padding: "6px 10px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    fontSize: 13,
    outline: "none",
  },
  loadSelect: {
    padding: "6px 8px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    fontSize: 13,
    background: "#fff",
    cursor: "pointer",
  },
  btn: {
    padding: "6px 12px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    background: "#fff",
    fontSize: 13,
    cursor: "pointer",
    fontWeight: 500,
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  deleteBtn: {
    color: "#dc2626",
    borderColor: "#fca5a5",
  },
  spotlightBtn: {
    padding: "5px 10px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    background: "#f9fafb",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    color: "#6b7280",
    letterSpacing: "0.03em",
    flexShrink: 0,
  },
  divider: {
    width: 1,
    height: 24,
    background: "#e5e7eb",
    margin: "0 2px",
    flexShrink: 0,
  },
  runBtn: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    fontWeight: 700,
    padding: "6px 18px",
  },
  errorList: {
    margin: 0,
    padding: "4px 12px 8px 28px",
    listStyle: "disc",
    background: "#fef2f2",
    borderTop: "1px solid #fecaca",
  },
  errorItem: {
    fontSize: 12,
    color: "#dc2626",
    lineHeight: 1.6,
  },
};
