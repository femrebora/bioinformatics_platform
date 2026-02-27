import { useState } from "react";
import { Handle, Position, useReactFlow } from "@xyflow/react";

export interface BioScriptNodeData {
  label: string;
  script: string;
  description?: string;
}

interface BioScriptNodeProps {
  id: string;
  data: BioScriptNodeData;
}

const COLOR = "#7c3aed"; // violet-600

const STARTER_SCRIPT = `#!/usr/bin/env bash
# BioScript — write your custom pipeline here.
# Available helpers (auto-sourced):
#   bioplatform_qc       <input.fastq.gz> <outdir>
#   bioplatform_align    <reads.fastq.gz> <genome.fa> <outdir>
#   bioplatform_call     <input.bam> <genome.fa> <outdir>
#   bioplatform_multiqc  <results_dir> <outdir>
#
# Environment variables:
#   INPUT_FILE   — S3 URI of the uploaded input file
#   OUTPUT_DIR   — S3 prefix for output files

set -euo pipefail

# Download input to local
aws s3 cp "$INPUT_FILE" /work/input.fastq.gz

# Run QC
bioplatform_qc /work/input.fastq.gz /work/results/qc

# Sync outputs to S3
bioplatform_s3_sync_out /work/results "$OUTPUT_DIR"
`;

export function BioScriptNode({ id, data }: BioScriptNodeProps) {
  const { updateNodeData, setNodes, setEdges } = useReactFlow();
  const [expanded, setExpanded] = useState(false);

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  const script = data.script || STARTER_SCRIPT;
  const lineCount = script.split("\n").length;

  return (
    <div style={s.node}>
      <Handle type="target" position={Position.Left} id="bioscript-in" style={s.handle} />

      <div style={s.header}>
        <span style={s.icon}>⚡</span>
        <span style={s.label}>{data.label}</span>
        <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          <button
            style={s.expandBtn}
            onClick={() => setExpanded((e) => !e)}
            title={expanded ? "Collapse editor" : "Expand editor"}
          >
            {expanded ? "▲" : "▼"}
          </button>
          <button onClick={handleDelete} style={s.deleteBtn} title="Remove node">×</button>
        </div>
      </div>

      <div style={s.body}>
        <div style={s.badge}>bash</div>
        {data.description && (
          <div style={s.desc}>{data.description}</div>
        )}

        {expanded ? (
          <textarea
            style={s.editor}
            value={script}
            onChange={(e) => updateNodeData(id, { script: e.target.value })}
            rows={Math.min(20, Math.max(6, lineCount + 2))}
            spellCheck={false}
          />
        ) : (
          <div style={s.preview} onClick={() => setExpanded(true)} title="Click to edit">
            <span style={s.previewText}>
              {script.split("\n").filter((l) => l.trim() && !l.startsWith("#")).slice(0, 3).join(" · ") || "Click to write script…"}
            </span>
            <span style={s.editHint}>✎ edit</span>
          </div>
        )}

        <div style={s.hint}>
          <span style={{ color: "#7c3aed" }}>INPUT_FILE</span> → script →{" "}
          <span style={{ color: "#16a34a" }}>OUTPUT_DIR</span>
        </div>
      </div>

      <Handle type="source" position={Position.Right} id="bioscript-out" style={s.handle} />
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: `2px solid ${COLOR}`,
    borderRadius: 8,
    minWidth: 240,
    maxWidth: 340,
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
  },
  header: {
    background: COLOR,
    borderRadius: "6px 6px 0 0",
    padding: "6px 10px",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 14 },
  label: { color: "#fff", fontWeight: 600, fontSize: 12, flex: 1 },
  expandBtn: {
    background: "rgba(255,255,255,0.2)",
    border: "none",
    color: "#fff",
    cursor: "pointer",
    fontSize: 11,
    borderRadius: 3,
    padding: "1px 5px",
  },
  deleteBtn: {
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.75)",
    cursor: "pointer",
    fontSize: 16,
    lineHeight: 1,
    padding: "0 2px",
    flexShrink: 0,
  },
  body: { padding: "8px 10px" },
  badge: {
    display: "inline-block",
    background: "#f3e8ff",
    color: COLOR,
    fontSize: 9,
    fontWeight: 700,
    padding: "1px 6px",
    borderRadius: 4,
    marginBottom: 6,
    fontFamily: "monospace",
    letterSpacing: "0.05em",
  },
  desc: {
    fontSize: 10,
    color: "#6b7280",
    marginBottom: 6,
    lineHeight: 1.4,
  },
  editor: {
    width: "100%",
    fontFamily: "monospace",
    fontSize: 10,
    border: "1px solid #d1d5db",
    borderRadius: 4,
    padding: "6px 8px",
    resize: "vertical",
    background: "#1e1e2e",
    color: "#cdd6f4",
    lineHeight: 1.5,
    boxSizing: "border-box",
    outline: "none",
  },
  preview: {
    background: "#f5f3ff",
    border: "1px solid #e9d5ff",
    borderRadius: 4,
    padding: "5px 8px",
    cursor: "pointer",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
  },
  previewText: {
    fontSize: 10,
    color: "#374151",
    fontFamily: "monospace",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
  },
  editHint: {
    fontSize: 9,
    color: COLOR,
    flexShrink: 0,
  },
  hint: {
    marginTop: 6,
    fontSize: 9,
    color: "#9ca3af",
    fontFamily: "monospace",
  },
  handle: { width: 10, height: 10, background: COLOR },
};
