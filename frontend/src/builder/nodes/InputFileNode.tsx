import { useEffect } from "react";
import { Handle, Position, useReactFlow, useEdges, useNodes } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import { extractExtensions } from "../validation";
import type { NfCoreIOPort } from "../../types/nfcore";

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

// Extension string → format value
const EXT_TO_FORMAT: Record<string, string> = {
  fastq: "fastq", "fastq.gz": "fastq", fq: "fastq", "fq.gz": "fastq",
  fa: "fasta", fasta: "fasta", fna: "fasta",
  bam: "bam",
  cram: "cram",
  sam: "sam",
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
  h5ad: "h5ad",
  loom: "loom",
  h5: "h5", hdf5: "h5",
  tif: "tiff", tiff: "tiff",
  "ome.tiff": "ome_tiff",
  zarr: "zarr",
  n5: "n5",
  png: "png",
  czi: "czi",
  lif: "lif",
  nd2: "nd2",
  svs: "svs",
  mzml: "mzml",
  mzxml: "mzxml",
  raw: "raw",
  mgf: "mgf",
  json: "json",
  yaml: "yaml", yml: "yaml",
};

interface AllowedResult {
  /** null = no connections (disable selector) */
  allowed: Set<string> | null;
  /** Shown as a badge / hint below the selector */
  note: string | null;
}

/**
 * Derive the set of allowed format values from the live edges + nodes.
 *
 * allowed:
 *   null          — no outgoing edges → selector disabled
 *   empty Set     — connected but no parseable pattern → show all
 *   non-empty Set — restricted to these format values
 */
function deriveAllowed(
  nodeId: string,
  edges: Edge[],
  nodes: Node[]
): AllowedResult {
  const outEdges = edges.filter((e) => e.source === nodeId);
  if (outEdges.length === 0) return { allowed: null, note: null };

  const allowed = new Set<string>();
  let anyRestriction = false;
  let hasPipelineBlock = false;

  for (const edge of outEdges) {
    const th = edge.targetHandle ?? "";
    const target = nodes.find((n) => n.id === edge.target);

    if (th === "fastq-in") {
      allowed.add("fastq");
      anyRestriction = true;
    } else if (th === "file-in") {
      // HLA-HD accepts FASTQ or BAM
      allowed.add("fastq");
      allowed.add("bam");
      anyRestriction = true;
    } else if (th.startsWith("nfc-in-") && target) {
      if (target.type === "nfcorePipeline") {
        const fmts = (target.data as { inputFormats?: string[] }).inputFormats;
        if (fmts && fmts.length > 0) {
          for (const f of fmts) { allowed.add(f); anyRestriction = true; }
        } else {
          hasPipelineBlock = true; // has no scraped format data
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
      // No pattern on port → no restriction from this edge
    }
  }

  if (hasPipelineBlock && !anyRestriction) {
    return {
      allowed: new Set<string>(),
      note: "Pipeline block has no port metadata — expand it into modules for automatic format filtering, or select manually.",
    };
  }

  return {
    allowed: anyRestriction ? allowed : new Set<string>(),
    note: null,
  };
}

// ── Component ──────────────────────────────────────────────────────────────

interface InputFileNodeData {
  label: string;
  fileType: string;
}

interface InputFileNodeProps {
  id: string;
  data: InputFileNodeData;
}

export function InputFileNode({ id, data }: InputFileNodeProps) {
  const { updateNodeData, setNodes, setEdges } = useReactFlow();
  const edges = useEdges();
  const nodes = useNodes();

  const { allowed, note } = deriveAllowed(id, edges, nodes);
  const isDisabled = allowed === null;
  const isRestricted = allowed !== null && allowed.size > 0;

  // Stable key for the effect below (avoids Set reference equality issues)
  const allowedKey = allowed === null ? "__none__" : [...allowed].sort().join(",");

  // Auto-reset fileType when connections change and current value is no longer valid
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

  const visibleGroups = FILE_FORMATS.map((g) => ({
    ...g,
    options: isRestricted
      ? g.options.filter((o) => allowed!.has(o.value))
      : g.options,
  })).filter((g) => g.options.length > 0);

  const currentLabel = ALL_OPTIONS.find((o) => o.value === data.fileType)?.label;

  return (
    <div style={styles.node}>
      <div style={styles.header}>
        <span style={styles.icon}>📂</span>
        <span style={styles.label}>{data.label}</span>
        <button onClick={handleDelete} style={styles.deleteBtn} title="Remove node">×</button>
      </div>

      <div style={styles.body}>
        {isDisabled ? (
          <div style={styles.hint}>
            Connect to a module to enable format selection.
          </div>
        ) : (
          <>
            <label style={styles.fieldLabel}>
              File Format
              {isRestricted && (
                <span style={styles.filteredBadge}>filtered by target</span>
              )}
            </label>
            <select
              value={data.fileType ?? ""}
              onChange={(e) => updateNodeData(id, { fileType: e.target.value })}
              style={styles.select}
            >
              {visibleGroups.map((group) => (
                <optgroup key={group.group} label={group.group}>
                  {group.options.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            {currentLabel && (
              <div style={styles.currentHint}>{currentLabel}</div>
            )}
            {note && (
              <div style={styles.noteHint}>{note}</div>
            )}
          </>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="file-out"
        style={styles.handle}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
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
