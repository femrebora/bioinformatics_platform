import type { PipelineListItem } from "../types/pipeline";

interface PipelineToolbarProps {
  pipelineName: string;
  onNameChange: (name: string) => void;
  savedPipelines: PipelineListItem[];
  activePipelineId: string | null;
  onSave: () => void;
  onLoad: (pipelineId: string) => void;
  onNew: () => void;
  onDelete: () => void;
  onRun: () => void;
  canRun: boolean;
  saving: boolean;
  validationErrors: string[];
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
  canRun,
  saving,
  validationErrors,
}: PipelineToolbarProps) {
  return (
    <div style={styles.wrapper}>
      <div style={styles.toolbar}>
        <input
          type="text"
          value={pipelineName}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Pipeline name…"
          style={styles.nameInput}
        />

        <button onClick={onSave} disabled={saving || !pipelineName.trim()} style={styles.btn}>
          {saving ? "Saving…" : activePipelineId ? "Save" : "Save New"}
        </button>

        <select
          value=""
          onChange={(e) => e.target.value && onLoad(e.target.value)}
          style={styles.loadSelect}
        >
          <option value="">Load…</option>
          {savedPipelines.map((p) => (
            <option key={p.pipeline_id} value={p.pipeline_id}>
              {p.name}
            </option>
          ))}
        </select>

        <button onClick={onNew} style={styles.btn}>
          New
        </button>

        <button
          onClick={onDelete}
          disabled={!activePipelineId}
          style={{ ...styles.btn, ...styles.deleteBtn }}
        >
          Delete
        </button>

        <div style={styles.divider} />

        <button
          onClick={onRun}
          disabled={!canRun}
          style={{ ...styles.btn, ...styles.runBtn, opacity: canRun ? 1 : 0.5 }}
        >
          ▶ Run
        </button>
      </div>

      {validationErrors.length > 0 && (
        <ul style={styles.errorList}>
          {validationErrors.map((err, i) => (
            <li key={i} style={styles.errorItem}>
              {err}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    borderBottom: "1px solid #e5e7eb",
    background: "#fff",
  },
  toolbar: {
    padding: "8px 12px",
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  nameInput: {
    flex: "0 0 200px",
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
    padding: "6px 14px",
    borderRadius: 6,
    border: "1px solid #d1d5db",
    background: "#fff",
    fontSize: 13,
    cursor: "pointer",
    fontWeight: 500,
    whiteSpace: "nowrap" as const,
  },
  deleteBtn: {
    color: "#dc2626",
    borderColor: "#fca5a5",
  },
  divider: {
    width: 1,
    height: 24,
    background: "#e5e7eb",
    margin: "0 4px",
  },
  runBtn: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    fontWeight: 700,
    cursor: "pointer",
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
