import { useEffect, useRef } from "react";
import { Handle, Position, useReactFlow, useEdges, useNodes } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import { extractExtensions } from "../validation";
import type { NfCoreIOPort } from "../../types/nfcore";
import type { PresignResponse } from "../../types/job";
import { presignUpload, uploadFile } from "../../api/client";

// ── File format catalogue ──────────────────────────────────────────────────

const FILE_FORMATS = [
  { group: "Sequencing Reads", options: [
    { value: "fastq",       label: "FASTQ (.fastq / .fastq.gz)" },
    { value: "fasta",       label: "FASTA (.fa / .fasta / .fna)" },
  ]},
  { group: "Alignments", options: [
    { value: "bam",         label: "BAM (.bam)" },
    { value: "cram",        label: "CRAM (.cram)" },
    { value: "sam",         label: "SAM (.sam)" },
  ]},
  { group: "Variants", options: [
    { value: "vcf",         label: "VCF (.vcf / .vcf.gz)" },
    { value: "bcf",         label: "BCF (.bcf)" },
    { value: "gvcf",        label: "gVCF (.g.vcf.gz)" },
  ]},
  { group: "Annotation", options: [
    { value: "gtf",         label: "GTF (.gtf)" },
    { value: "gff",         label: "GFF3 (.gff / .gff3)" },
    { value: "bed",         label: "BED (.bed)" },
    { value: "bedgraph",    label: "BEDGraph (.bg / .bedgraph)" },
    { value: "bigwig",      label: "BigWig (.bw / .bigWig)" },
    { value: "bigbed",      label: "BigBed (.bb / .bigBed)" },
  ]},
  { group: "Expression / Quant", options: [
    { value: "counts",      label: "Counts table (.tsv / .csv)" },
    { value: "h5ad",        label: "AnnData (.h5ad)" },
    { value: "loom",        label: "Loom (.loom)" },
    { value: "h5",          label: "HDF5 (.h5 / .hdf5)" },
  ]},
  { group: "Imaging", options: [
    { value: "tiff",        label: "TIFF (.tif / .tiff)" },
    { value: "ome_tiff",    label: "OME-TIFF (.ome.tiff)" },
    { value: "zarr",        label: "Zarr (.zarr)" },
    { value: "n5",          label: "N5 (.n5)" },
    { value: "png",         label: "PNG (.png)" },
    { value: "czi",         label: "Zeiss CZI (.czi)" },
    { value: "lif",         label: "Leica LIF (.lif)" },
    { value: "nd2",         label: "Nikon ND2 (.nd2)" },
    { value: "svs",         label: "SVS (.svs)" },
  ]},
  { group: "Mass Spec / Proteomics", options: [
    { value: "mzml",        label: "mzML (.mzML)" },
    { value: "mzxml",       label: "mzXML (.mzXML)" },
    { value: "raw",         label: "Thermo RAW (.raw)" },
    { value: "mgf",         label: "MGF (.mgf)" },
  ]},
  { group: "Genome / Reference", options: [
    { value: "genome",      label: "Reference genome (.fa.gz)" },
    { value: "index_bwa",   label: "BWA index (.amb/.ann/…)" },
    { value: "index_star",  label: "STAR index (directory)" },
    { value: "index_bowtie",label: "Bowtie2 index (.bt2)" },
  ]},
  { group: "Generic", options: [
    { value: "tsv",         label: "TSV (.tsv)" },
    { value: "csv",         label: "CSV (.csv)" },
    { value: "json",        label: "JSON (.json)" },
    { value: "yaml",        label: "YAML (.yaml / .yml)" },
    { value: "other",       label: "Other / Unknown" },
  ]},
];

const ALL_OPTIONS = FILE_FORMATS.flatMap((g) => g.options);

const EXT_TO_FORMAT: Record<string, string> = {
  fastq: "fastq", "fastq.gz": "fastq", fq: "fastq", "fq.gz": "fastq",
  fa: "fasta", fasta: "fasta", fna: "fasta",
  bam: "bam", cram: "cram", sam: "sam",
  vcf: "vcf", "vcf.gz": "vcf",
  bcf: "bcf",
  "g.vcf.gz": "gvcf", gvcf: "gvcf",
  gtf: "gtf",
  gff: "gff", gff3: "gff",
  bed: "bed",
  bg: "bedgraph", bedgraph: "bedgraph",
  bw: "bigwig", bigwig: "bigwig",
  bb: "bigbed", bigbed: "bigbed",
  tsv: "tsv", txt: "tsv",
  csv: "csv",
  h5ad: "h5ad", loom: "loom",
  h5: "h5", hdf5: "h5",
  tif: "tiff", tiff: "tiff",
  "ome.tiff": "ome_tiff",
  zarr: "zarr", n5: "n5",
  png: "png", czi: "czi", lif: "lif", nd2: "nd2", svs: "svs",
  mzml: "mzml", mzxml: "mzxml", raw: "raw", mgf: "mgf",
  json: "json",
  yaml: "yaml", yml: "yaml",
};

// ── Format restriction (from connections) ──────────────────────────────────

interface AllowedResult {
  allowed: Set<string> | null;
  note: string | null;
}

function deriveAllowed(nodeId: string, edges: Edge[], nodes: Node[]): AllowedResult {
  const outEdges = edges.filter((e) => e.source === nodeId);
  if (outEdges.length === 0) return { allowed: null, note: null };

  const allowed = new Set<string>();
  let anyRestriction = false;
  let hasPipelineBlock = false;

  for (const edge of outEdges) {
    const th = edge.targetHandle ?? "";
    const target = nodes.find((n) => n.id === edge.target);

    if (th === "fastq-in") {
      allowed.add("fastq"); anyRestriction = true;
    } else if (th === "file-in") {
      allowed.add("fastq"); allowed.add("bam"); anyRestriction = true;
    } else if (th.startsWith("nfc-in-") && target) {
      if (target.type === "nfcorePipeline") {
        const fmts = (target.data as { inputFormats?: string[] }).inputFormats;
        if (fmts && fmts.length > 0) {
          for (const f of fmts) { allowed.add(f); anyRestriction = true; }
        } else {
          hasPipelineBlock = true;
        }
        continue;
      }
      const portName = th.slice("nfc-in-".length);
      const inputs = (target.data as { inputs?: NfCoreIOPort[] | null }).inputs;
      const port = inputs?.find((p) => p.name === portName);
      if (port?.pattern) {
        const exts = extractExtensions(port.pattern);
        for (const ext of exts) {
          const fmt = EXT_TO_FORMAT[ext];
          if (fmt) { allowed.add(fmt); anyRestriction = true; }
        }
      }
    }
  }

  if (hasPipelineBlock && !anyRestriction) {
    return {
      allowed: new Set<string>(),
      note: "Pipeline block has no port metadata — expand it into modules for automatic format filtering, or select manually.",
    };
  }

  return { allowed: anyRestriction ? allowed : new Set<string>(), note: null };
}

// ── Node data type ─────────────────────────────────────────────────────────

export interface InputFileNodeData {
  label: string;
  fileType: string;
  inputMode?: "upload" | "dataset";
  // upload mode
  presign?: PresignResponse;
  uploadedFilename?: string;
  uploadStatus?: "idle" | "uploading" | "done" | "error";
  uploadError?: string;
  // dataset mode
  datasetId?: string;
}

// ── Component ──────────────────────────────────────────────────────────────

interface InputFileNodeProps {
  id: string;
  data: InputFileNodeData;
}

export function InputFileNode({ id, data }: InputFileNodeProps) {
  const { updateNodeData, setNodes, setEdges } = useReactFlow();
  const edges = useEdges();
  const nodes = useNodes();
  const fileRef = useRef<HTMLInputElement>(null);

  const mode = data.inputMode ?? "upload";
  const uploadStatus = data.uploadStatus ?? "idle";

  const { allowed, note } = deriveAllowed(id, edges, nodes);
  const isDisabled = allowed === null;
  const isRestricted = allowed !== null && allowed.size > 0;
  const allowedKey = allowed === null ? "__none__" : [...allowed].sort().join(",");

  // Auto-reset fileType when connections change
  useEffect(() => {
    if (!isRestricted) return;
    if (allowed!.has(data.fileType ?? "")) return;
    const first = ALL_OPTIONS.find((o) => allowed!.has(o.value));
    if (first) updateNodeData(id, { fileType: first.value });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowedKey]);

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    updateNodeData(id, { uploadStatus: "uploading", uploadError: undefined });
    try {
      const presign = await presignUpload(file.name, file.size);
      await uploadFile(presign.upload_url, file);
      updateNodeData(id, { uploadStatus: "done", presign, uploadedFilename: file.name });
    } catch (err) {
      updateNodeData(id, {
        uploadStatus: "error",
        uploadError: err instanceof Error ? err.message : "Upload failed",
      });
    }
  }

  const visibleGroups = FILE_FORMATS.map((g) => ({
    ...g,
    options: isRestricted ? g.options.filter((o) => allowed!.has(o.value)) : g.options,
  })).filter((g) => g.options.length > 0);

  const currentLabel = ALL_OPTIONS.find((o) => o.value === data.fileType)?.label;

  return (
    <div style={s.node}>
      <div style={s.header}>
        <span style={s.icon}>📂</span>
        <span style={s.label}>{data.label}</span>
        <button onClick={handleDelete} style={s.deleteBtn} title="Remove node">×</button>
      </div>

      <div style={s.body}>
        {/* Mode toggle */}
        <div style={s.modeRow}>
          <button
            style={{ ...s.modeBtn, ...(mode === "upload" ? s.modeBtnActive : {}) }}
            onClick={() => updateNodeData(id, { inputMode: "upload" })}
          >
            Upload
          </button>
          <button
            style={{ ...s.modeBtn, ...(mode === "dataset" ? s.modeBtnActive : {}) }}
            onClick={() => updateNodeData(id, { inputMode: "dataset" })}
          >
            Dataset ID
          </button>
        </div>

        {/* Upload section */}
        {mode === "upload" && (
          <div style={s.section}>
            {uploadStatus === "idle" && (
              <button style={s.uploadBtn} onClick={() => fileRef.current?.click()}>
                Choose File…
              </button>
            )}
            {uploadStatus === "uploading" && (
              <div style={s.statusRow}>
                <span style={s.spinner}>⟳</span>
                <span style={{ fontSize: 11, color: "#6b7280" }}>Uploading…</span>
              </div>
            )}
            {uploadStatus === "done" && (
              <div style={s.doneRow}>
                <span style={s.doneIcon}>✓</span>
                <span style={s.doneFilename} title={data.uploadedFilename}>
                  {data.uploadedFilename}
                </span>
                <button style={s.changeBtn} onClick={() => {
                  updateNodeData(id, { uploadStatus: "idle", presign: undefined, uploadedFilename: undefined });
                }}>×</button>
              </div>
            )}
            {uploadStatus === "error" && (
              <div>
                <div style={s.errorMsg}>{data.uploadError ?? "Upload failed"}</div>
                <button style={s.uploadBtn} onClick={() => {
                  updateNodeData(id, { uploadStatus: "idle" });
                  fileRef.current?.click();
                }}>Retry</button>
              </div>
            )}
            <input
              ref={fileRef}
              type="file"
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
          </div>
        )}

        {/* Dataset ID section */}
        {mode === "dataset" && (
          <div style={s.section}>
            <input
              type="text"
              placeholder="storage-key or dataset ID…"
              value={data.datasetId ?? ""}
              onChange={(e) => updateNodeData(id, { datasetId: e.target.value })}
              style={s.datasetInput}
            />
            <div style={s.datasetHint}>Enter the storage key of a previously uploaded file.</div>
          </div>
        )}

        {/* Divider */}
        <div style={s.divider} />

        {/* Format selector */}
        {isDisabled ? (
          <div style={s.hint}>Connect to a module to enable format selection.</div>
        ) : (
          <>
            <label style={s.fieldLabel}>
              File Format
              {isRestricted && <span style={s.filteredBadge}>filtered by target</span>}
            </label>
            <select
              value={data.fileType ?? ""}
              onChange={(e) => updateNodeData(id, { fileType: e.target.value })}
              style={s.select}
            >
              {visibleGroups.map((group) => (
                <optgroup key={group.group} label={group.group}>
                  {group.options.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            {currentLabel && <div style={s.currentHint}>{currentLabel}</div>}
            {note && <div style={s.noteHint}>{note}</div>}
          </>
        )}
      </div>

      <Handle type="source" position={Position.Right} id="file-out" style={s.handle} />
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  node: {
    background: "#fff",
    border: "2px solid #3b82f6",
    borderRadius: 8,
    minWidth: 210,
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
  },
  header: {
    background: "#3b82f6",
    borderRadius: "6px 6px 0 0",
    padding: "6px 10px",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 14 },
  label: { color: "#fff", fontWeight: 600, fontSize: 12, flex: 1 },
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
  body: { padding: "10px 12px" },
  modeRow: {
    display: "flex",
    gap: 0,
    border: "1px solid #d1d5db",
    borderRadius: 6,
    overflow: "hidden",
    marginBottom: 8,
  },
  modeBtn: {
    flex: 1,
    padding: "4px 0",
    border: "none",
    background: "#f9fafb",
    cursor: "pointer",
    fontSize: 11,
    color: "#6b7280",
  },
  modeBtnActive: {
    background: "#3b82f6",
    color: "#fff",
    fontWeight: 600,
  },
  section: { marginBottom: 8 },
  uploadBtn: {
    width: "100%",
    padding: "6px 0",
    border: "1px dashed #93c5fd",
    borderRadius: 6,
    background: "#eff6ff",
    color: "#2563eb",
    fontSize: 11,
    cursor: "pointer",
    fontWeight: 500,
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "5px 8px",
    background: "#f9fafb",
    borderRadius: 6,
    border: "1px solid #e5e7eb",
  },
  spinner: {
    display: "inline-block",
    fontSize: 14,
    animation: "spin 1s linear infinite",
    color: "#3b82f6",
  },
  doneRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 8px",
    background: "#f0fdf4",
    borderRadius: 6,
    border: "1px solid #bbf7d0",
  },
  doneIcon: { color: "#16a34a", fontWeight: 700, fontSize: 12, flexShrink: 0 },
  doneFilename: {
    fontSize: 10,
    color: "#166534",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
  },
  changeBtn: {
    background: "none",
    border: "none",
    color: "#6b7280",
    cursor: "pointer",
    fontSize: 12,
    padding: "0 2px",
    flexShrink: 0,
  },
  errorMsg: {
    fontSize: 10,
    color: "#dc2626",
    background: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 4,
    padding: "3px 6px",
    marginBottom: 4,
  },
  datasetInput: {
    width: "100%",
    padding: "5px 7px",
    border: "1px solid #d1d5db",
    borderRadius: 6,
    fontSize: 10,
    background: "#f9fafb",
    boxSizing: "border-box",
    fontFamily: "monospace",
  },
  datasetHint: {
    fontSize: 9,
    color: "#9ca3af",
    marginTop: 3,
    lineHeight: 1.4,
  },
  divider: { height: 1, background: "#f0f0f0", margin: "6px 0" },
  fieldLabel: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 11,
    color: "#6b7280",
    marginBottom: 4,
  },
  filteredBadge: {
    background: "#dbeafe",
    color: "#1d4ed8",
    borderRadius: 6,
    padding: "1px 5px",
    fontSize: 9,
    fontWeight: 600,
  },
  select: {
    width: "100%",
    padding: "4px 6px",
    borderRadius: 4,
    border: "1px solid #d1d5db",
    fontSize: 11,
    background: "#f9fafb",
    cursor: "pointer",
  },
  currentHint: {
    marginTop: 4,
    fontSize: 10,
    color: "#9ca3af",
    fontStyle: "italic",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  hint: {
    fontSize: 11,
    color: "#9ca3af",
    fontStyle: "italic",
    textAlign: "center",
    padding: "4px 0",
  },
  noteHint: {
    marginTop: 6,
    fontSize: 10,
    color: "#b45309",
    background: "#fef3c7",
    border: "1px solid #fde68a",
    borderRadius: 4,
    padding: "4px 6px",
    lineHeight: 1.4,
  },
  handle: { width: 10, height: 10, background: "#3b82f6" },
};
