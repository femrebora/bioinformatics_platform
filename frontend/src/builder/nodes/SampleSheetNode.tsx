/**
 * SampleSheetNode — multi-sample table for nf-core pipelines.
 *
 * Each row represents one biological sample:
 *   sample_name  — identifier used in the samplesheet CSV
 *   group        — experimental condition (treatment / control / custom)
 *   strandedness — RNA-seq library strandedness (auto / forward / reverse / unstranded)
 *   r1_key       — storage_key for the R1 FASTQ (from an InputFile upload)
 *   r2_key       — storage_key for R2 (optional, paired-end)
 *
 * Outputs a `samplesheet-out` handle that connects to an NfCorePipelineNode's
 * `nfc-in-data` handle.  The row data is serialised into workflow_config.samples
 * and consumed by the backend samplesheet generator.
 */
import { useState } from "react";
import { Handle, Position, useReactFlow } from "@xyflow/react";

export interface SampleRow {
  id: string;
  sample_name: string;
  group: string;
  strandedness: string;
  sex: string;
  r1_key: string;
  r2_key: string;
}

export interface SampleSheetNodeData {
  label: string;
  samples: SampleRow[];
}

interface SampleSheetNodeProps {
  id: string;
  data: SampleSheetNodeData;
}

const COLOR = "#7c3aed";
const STRAND_OPTS = ["auto", "forward", "reverse", "unstranded"] as const;

let _rowCounter = 0;
function newRowId() { return `row-${++_rowCounter}-${Date.now().toString(36)}`; }

function emptyRow(): SampleRow {
  return { id: newRowId(), sample_name: "", group: "treatment", strandedness: "auto", sex: "XX", r1_key: "", r2_key: "" };
}

export function SampleSheetNode({ id, data }: SampleSheetNodeProps) {
  const { setNodes, setEdges, updateNodeData } = useReactFlow();
  const [collapsed, setCollapsed] = useState(false);

  const samples: SampleRow[] = data.samples?.length ? data.samples : [emptyRow()];

  function updateSamples(next: SampleRow[]) {
    updateNodeData(id, { samples: next });
  }

  function updateRow(rowId: string, patch: Partial<SampleRow>) {
    updateSamples(samples.map((r) => r.id === rowId ? { ...r, ...patch } : r));
  }

  function addRow() {
    updateSamples([...samples, emptyRow()]);
  }

  function removeRow(rowId: string) {
    const next = samples.filter((r) => r.id !== rowId);
    updateSamples(next.length ? next : [emptyRow()]);
  }

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  const groupColors: Record<string, string> = {
    treatment: "#dbeafe",
    control: "#dcfce7",
  };

  return (
    <div style={styles.node}>
      <div style={styles.header}>
        <span style={{ fontSize: 13 }}>🗂️</span>
        <span style={styles.label} title={data.label}>{data.label}</span>
        <span style={styles.badge}>{samples.length} sample{samples.length !== 1 ? "s" : ""}</span>
        <button
          onClick={(e) => { e.stopPropagation(); setCollapsed((c) => !c); }}
          style={styles.iconBtn}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "▶" : "▼"}
        </button>
        <button onClick={handleDelete} style={styles.deleteBtn} title="Remove node">×</button>
      </div>

      {!collapsed && (
        <div style={styles.body}>
          {/* Column headers */}
          <div style={styles.colHeaders}>
            <span style={{ width: 88 }}>Sample name</span>
            <span style={{ width: 74 }}>Group</span>
            <span style={{ width: 66 }}>Strand</span>
            <span style={{ width: 42 }}>Sex</span>
            <span style={{ flex: 1 }}>R1 key</span>
            <span style={{ flex: 1 }}>R2 key</span>
            <span style={{ width: 18 }} />
          </div>

          {/* Sample rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {samples.map((row) => (
              <div key={row.id} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                {/* Sample name */}
                <input
                  value={row.sample_name}
                  onChange={(e) => updateRow(row.id, { sample_name: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  placeholder="sample1"
                  style={{ ...styles.inp, width: 84 }}
                />

                {/* Group / condition */}
                <input
                  value={row.group}
                  onChange={(e) => updateRow(row.id, { group: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  placeholder="treatment"
                  style={{
                    ...styles.inp,
                    width: 70,
                    background: groupColors[row.group] ?? "#fef9c3",
                    borderColor: "#d1d5db",
                  }}
                  title="Experimental group / condition"
                  list={`group-list-${id}`}
                />
                <datalist id={`group-list-${id}`}>
                  <option value="treatment" />
                  <option value="control" />
                  <option value="case" />
                  <option value="normal" />
                  <option value="tumour" />
                </datalist>

                {/* Strandedness */}
                <select
                  value={row.strandedness}
                  onChange={(e) => updateRow(row.id, { strandedness: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  style={{ ...styles.inp, width: 62, padding: "3px 4px" }}
                  title="RNA-seq library strandedness (ignored for non-RNA pipelines)"
                >
                  {STRAND_OPTS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>

                {/* Sex / karyotype */}
                <select
                  value={row.sex ?? "XX"}
                  onChange={(e) => updateRow(row.id, { sex: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  style={{ ...styles.inp, width: 38, padding: "3px 4px" }}
                  title="Sample karyotype — affects ploidy on sex chromosomes (sarek/germline)"
                >
                  <option value="XX">XX</option>
                  <option value="XY">XY</option>
                </select>

                {/* R1 storage key */}
                <input
                  value={row.r1_key}
                  onChange={(e) => updateRow(row.id, { r1_key: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  placeholder="uploads/…_R1.fastq.gz"
                  style={{ ...styles.inp, flex: 1 }}
                  title="Storage key from an InputFile upload (R1)"
                />

                {/* R2 storage key */}
                <input
                  value={row.r2_key}
                  onChange={(e) => updateRow(row.id, { r2_key: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  placeholder="R2 (optional)"
                  style={{ ...styles.inp, flex: 1 }}
                  title="Storage key for paired-end R2 (optional)"
                />

                {/* Remove row */}
                <button
                  onClick={() => removeRow(row.id)}
                  style={{ ...styles.iconBtn, color: "#ef4444", fontSize: 14, width: 18, flexShrink: 0 }}
                  title="Remove sample"
                >
                  −
                </button>
              </div>
            ))}
          </div>

          {/* Add row */}
          <button onClick={addRow} style={styles.addBtn}>
            + Add sample
          </button>

          {/* Hint */}
          <div style={styles.hint}>
            R1/R2 keys come from InputFile uploads. Group values drive comparisons (e.g. DESeq2 treatment vs control).
          </div>
        </div>
      )}

      {/* Output handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="samplesheet-out"
        style={{ width: 8, height: 8, background: COLOR }}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: `2px solid ${COLOR}`,
    borderRadius: 8,
    minWidth: 560,
    maxWidth: 700,
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
  label: {
    color: "#fff",
    fontWeight: 600,
    fontSize: 11,
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  badge: {
    background: "rgba(255,255,255,0.2)",
    color: "#fff",
    borderRadius: 999,
    fontSize: 9,
    fontWeight: 700,
    padding: "1px 7px",
    flexShrink: 0,
  },
  iconBtn: {
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.8)",
    cursor: "pointer",
    fontSize: 12,
    padding: "0 3px",
    flexShrink: 0,
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
  body: { padding: "10px 12px" },
  colHeaders: {
    display: "flex",
    gap: 4,
    alignItems: "center",
    marginBottom: 5,
    fontSize: 9,
    fontWeight: 700,
    color: "#9ca3af",
    textTransform: "uppercase" as const,
    letterSpacing: ".04em",
  },
  inp: {
    fontSize: 11,
    padding: "3px 6px",
    borderRadius: 5,
    border: "1px solid #d1d5db",
    background: "#f9fafb",
    color: "#0f172a",
    minWidth: 0,
  },
  addBtn: {
    marginTop: 8,
    width: "100%",
    padding: "5px",
    borderRadius: 6,
    border: `1.5px dashed ${COLOR}`,
    background: "#faf5ff",
    color: COLOR,
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
  },
  hint: {
    marginTop: 8,
    fontSize: 9,
    color: "#9ca3af",
    lineHeight: 1.5,
  },
};
