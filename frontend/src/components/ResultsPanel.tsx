/**
 * ResultsPanel — sliding results drawer with tabs, charts, and downloads.
 *
 * Positions:
 *   "side"   — right-edge panel (480 px wide, full height)
 *   "center" — centered modal overlay (up to 900 px wide, 85 vh tall)
 *
 * Triggered by custom DOM event "openResultsPanel" from anywhere in the app.
 * Close via the × button or by clicking the backdrop (center mode only).
 */
import { useState, useEffect } from "react";
import { getDownloadUrl, getVcfPage } from "../api/client";
import type { Job, JobResult, HLAAllele, VcfVariant, Provenance } from "../types/job";

// ── File type helpers ──────────────────────────────────────────────────────

function fileIcon(mime: string | undefined, name: string): string {
  const n = name.toLowerCase();
  if (n.endsWith(".html") || n.endsWith(".htm")) return "📊";
  if (n.endsWith(".bam") || n.endsWith(".cram")) return "🧬";
  if (n.endsWith(".bai") || n.endsWith(".crai")) return "📑";
  if (n.endsWith(".vcf") || n.endsWith(".vcf.gz") || n.endsWith(".bcf")) return "🔬";
  if (n.endsWith(".fastq") || n.endsWith(".fastq.gz") || n.endsWith(".fq.gz")) return "🧪";
  if (n.endsWith(".fasta") || n.endsWith(".fa") || n.endsWith(".fna")) return "🔗";
  if (n.endsWith(".gff") || n.endsWith(".gff3") || n.endsWith(".gtf")) return "🗺️";
  if (n.endsWith(".tsv") || n.endsWith(".csv")) return "📋";
  if (n.endsWith(".log") || n.endsWith(".txt")) return "📝";
  if (n.endsWith(".gz") || n.endsWith(".tar.gz") || n.endsWith(".zip")) return "📦";
  if (n.endsWith(".bigwig") || n.endsWith(".bw")) return "📈";
  if (n.endsWith(".bed") || n.endsWith(".narrowpeak") || n.endsWith(".broadpeak")) return "🗃️";
  if (n.endsWith(".nwk") || n.endsWith(".newick")) return "🌿";
  if (n.endsWith(".svg")) return "🖼️";
  if (mime?.includes("html")) return "📊";
  if (mime?.includes("octet-stream")) return "💾";
  return "📄";
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1073741824) return `${(n / 1048576).toFixed(1)} MB`;
  return `${(n / 1073741824).toFixed(1)} GB`;
}

function isHtmlFile(f: { name: string; mime_type?: string }): boolean {
  return f.name.toLowerCase().endsWith(".html") || f.name.toLowerCase().endsWith(".htm")
    || (f.mime_type ?? "").includes("html");
}

// ── DE table detection & Volcano plot ─────────────────────────────────────

function findCol(columns: string[], ...candidates: string[]): string | undefined {
  const lower = columns.map((c) => c.toLowerCase());
  for (const cand of candidates) {
    const idx = lower.indexOf(cand.toLowerCase());
    if (idx >= 0) return columns[idx];
  }
  return undefined;
}

function isDETable(result: JobResult): boolean {
  if (!result.columns) return false;
  const lower = result.columns.map((c) => c.toLowerCase());
  return (
    (lower.includes("log2foldchange") || lower.includes("log2fc")) &&
    (lower.includes("padj") || lower.includes("pvalue") || lower.includes("p.adj") || lower.includes("p.value"))
  );
}

function VolcanoPlot({ columns, rows }: { columns: string[]; rows: Record<string, string | number>[] }) {
  const [padjCut, setPadjCut] = useState(0.05);
  const [lfcCut,  setLfcCut]  = useState(1.0);

  const l2fcCol = findCol(columns, "log2FoldChange", "log2fc", "log2FC");
  const padjCol = findCol(columns, "padj", "p.adj", "pvalue", "p.value", "pval");
  const geneCol = findCol(columns, "gene", "gene_id", "geneId", "symbol", "geneName");

  if (!l2fcCol || !padjCol) return null;

  interface Pt { x: number; y: number; sig: "up" | "down" | "ns" }
  const pts: Pt[] = rows.map((r) => {
    const x = parseFloat(String(r[l2fcCol] ?? "0"));
    const pv = parseFloat(String(r[padjCol] ?? "1"));
    const y = pv > 0 && isFinite(pv) ? -Math.log10(pv) : 0;
    const sig: Pt["sig"] = Math.abs(x) >= lfcCut && pv < padjCut ? (x > 0 ? "up" : "down") : "ns";
    return { x, y, sig };
  }).filter((p) => isFinite(p.x) && isFinite(p.y));

  if (pts.length === 0) return null;

  const up   = pts.filter((p) => p.sig === "up").length;
  const down = pts.filter((p) => p.sig === "down").length;
  const ns   = pts.length - up - down;

  const W = 320, H = 200, ML = 38, MR = 12, MT = 12, MB = 28;
  const pw = W - ML - MR, ph = H - MT - MB;

  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const xMin = Math.min(...xs) - 0.5, xMax = Math.max(...xs) + 0.5;
  const yMax = Math.max(...ys) + 0.5;

  const toX = (v: number) => ML + ((v - xMin) / (xMax - xMin)) * pw;
  const toY = (v: number) => MT + (1 - v / yMax) * ph;

  const sigLineY = toY(-Math.log10(padjCut));
  const xTicks: number[] = [];
  const step = (xMax - xMin) > 8 ? 2 : 1;
  for (let v = Math.ceil(xMin); v <= Math.floor(xMax); v += step) xTicks.push(v);
  const yTicks = [0, 2, 4, 6, 8, 10].filter((v) => v <= yMax + 0.1);

  void geneCol; // available for future tooltip use

  return (
    <div>
      {/* Threshold controls */}
      <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#374151" }}>
          <span style={{ width: 80 }}>padj &lt; {padjCut}</span>
          <input type="range" min={0.001} max={0.2} step={0.001} value={padjCut}
            onChange={(e) => setPadjCut(parseFloat(e.target.value))}
            style={{ width: 80 }} />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#374151" }}>
          <span style={{ width: 80 }}>|log₂FC| &gt; {lfcCut.toFixed(1)}</span>
          <input type="range" min={0} max={4} step={0.1} value={lfcCut}
            onChange={(e) => setLfcCut(parseFloat(e.target.value))}
            style={{ width: 80 }} />
        </label>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <StatCard label="Up-regulated"    value={up.toLocaleString()}   color="#ef4444" />
        <StatCard label="Down-regulated"  value={down.toLocaleString()} color="#3b82f6" />
        <StatCard label="Not significant" value={ns.toLocaleString()}   color="#9ca3af" />
      </div>
      <SectionTitle>Volcano Plot (log₂FC vs −log₁₀ padj)</SectionTitle>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", maxHeight: 220, display: "block" }}>
        <rect x={ML} y={MT} width={pw} height={ph} fill="#f9fafb" rx={3} />
        {/* Threshold lines */}
        {sigLineY > MT && sigLineY < MT + ph && (
          <line x1={ML} y1={sigLineY} x2={ML + pw} y2={sigLineY} stroke="#9ca3af" strokeWidth={0.8} strokeDasharray="3,2" />
        )}
        {[lfcCut, -lfcCut].map((fc) => {
          const x = toX(fc);
          return x > ML && x < ML + pw
            ? <line key={fc} x1={x} y1={MT} x2={x} y2={MT + ph} stroke="#9ca3af" strokeWidth={0.8} strokeDasharray="3,2" />
            : null;
        })}
        {/* Points */}
        {pts.map((p, i) => (
          <circle
            key={i}
            cx={toX(p.x)} cy={toY(p.y)} r={2.2}
            fill={p.sig === "up" ? "#ef4444" : p.sig === "down" ? "#3b82f6" : "#9ca3af"}
            fillOpacity={p.sig === "ns" ? 0.3 : 0.7}
          />
        ))}
        {/* Axes */}
        <line x1={ML} y1={MT + ph} x2={ML + pw} y2={MT + ph} stroke="#374151" strokeWidth={1} />
        <line x1={ML} y1={MT} x2={ML} y2={MT + ph} stroke="#374151" strokeWidth={1} />
        {/* X ticks */}
        {xTicks.map((v) => {
          const x = toX(v);
          if (x < ML || x > ML + pw) return null;
          return (
            <g key={v}>
              <line x1={x} y1={MT + ph} x2={x} y2={MT + ph + 3} stroke="#374151" strokeWidth={0.8} />
              <text x={x} y={MT + ph + 10} textAnchor="middle" fontSize={7} fill="#6b7280">{v}</text>
            </g>
          );
        })}
        {/* Y ticks */}
        {yTicks.map((v) => {
          const y = toY(v);
          if (y < MT - 1 || y > MT + ph + 1) return null;
          return (
            <g key={v}>
              <line x1={ML - 3} y1={y} x2={ML} y2={y} stroke="#374151" strokeWidth={0.8} />
              <text x={ML - 5} y={y + 3} textAnchor="end" fontSize={7} fill="#6b7280">{v}</text>
            </g>
          );
        })}
        {/* Axis labels */}
        <text x={ML + pw / 2} y={H - 1} textAnchor="middle" fontSize={8} fill="#374151">log₂ Fold Change</text>
        <text x={10} y={MT + ph / 2} textAnchor="middle" fontSize={8} fill="#374151" transform={`rotate(-90,10,${MT + ph / 2})`}>−log₁₀(padj)</text>
      </svg>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function detectType(result: JobResult): string {
  if (result.type) return result.type;
  if (result.hla_alleles?.length) return "hla_alleles";
  if (result.variants?.length) return "vcf";
  if (result.columns && result.rows) return "table";
  if (result.html) return "html_report";
  if (result.content) return "text";
  if (result.files?.length) return "files";
  return "unknown";
}

function dlBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
function dlJson(data: unknown, filename: string) {
  dlBlob(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), filename);
}
function dlText(text: string, filename: string, mime = "text/plain") {
  dlBlob(new Blob([text], { type: mime }), filename);
}

// ── Locus colour palette (MHC genes) ─────────────────────────────────────

type LocusStyle = { bg: string; text: string; accent: string };
const LOCUS: Record<string, LocusStyle> = {
  A:    { bg: "#dbeafe", text: "#1d4ed8", accent: "#3b82f6" },
  B:    { bg: "#dcfce7", text: "#15803d", accent: "#22c55e" },
  C:    { bg: "#fef3c7", text: "#92400e", accent: "#f59e0b" },
  DRB1: { bg: "#fee2e2", text: "#b91c1c", accent: "#ef4444" },
  DRB3: { bg: "#fee2e2", text: "#b91c1c", accent: "#ef4444" },
  DRB4: { bg: "#fee2e2", text: "#b91c1c", accent: "#ef4444" },
  DRB5: { bg: "#fee2e2", text: "#b91c1c", accent: "#ef4444" },
  DQA1: { bg: "#ede9fe", text: "#6d28d9", accent: "#8b5cf6" },
  DQB1: { bg: "#fce7f3", text: "#9d174d", accent: "#ec4899" },
  DPA1: { bg: "#ccfbf1", text: "#0f766e", accent: "#14b8a6" },
  DPB1: { bg: "#cffafe", text: "#0e7490", accent: "#06b6d4" },
};
function locusStyle(gene: string): LocusStyle {
  const locus = gene.replace(/^HLA-/, "");
  return LOCUS[locus] ?? { bg: "#f3f4f6", text: "#374151", accent: "#6b7280" };
}
function locusShort(gene: string): string {
  const l = gene.replace(/^HLA-/, "");
  return l.length > 4 ? l.slice(0, 4) : l;
}

// ── Horizontal bar chart ───────────────────────────────────────────────────

interface BarEntry { label: string; value: number; color: string }

function HBarChart({ data }: { data: BarEntry[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      {data.map((d, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 64, fontSize: 10, color: "#6b7280", textAlign: "right", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.label}</div>
          <div style={{ flex: 1, height: 12, background: "#f3f4f6", borderRadius: 6, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${(d.value / max) * 100}%`, background: d.color, borderRadius: 6, transition: "width 0.5s ease" }} />
          </div>
          <div style={{ width: 36, fontSize: 10, color: "#6b7280", flexShrink: 0 }}>{d.value.toLocaleString()}</div>
        </div>
      ))}
    </div>
  );
}

// ── Donut chart (SVG) ──────────────────────────────────────────────────────

interface DonutSlice { label: string; value: number; color: string }

function DonutChart({ slices, size = 120 }: { slices: DonutSlice[]; size?: number }) {
  const total = slices.reduce((s, d) => s + d.value, 0);
  if (total === 0) return null;

  const cx = size / 2, cy = size / 2, r = size * 0.38, inner = size * 0.22;
  let angle = -Math.PI / 2;

  const paths = slices.map((slice) => {
    const sweep = (slice.value / total) * 2 * Math.PI;
    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    angle += sweep;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    const xi1 = cx + inner * Math.cos(angle - sweep);
    const yi1 = cy + inner * Math.sin(angle - sweep);
    const xi2 = cx + inner * Math.cos(angle);
    const yi2 = cy + inner * Math.sin(angle);
    const large = sweep > Math.PI ? 1 : 0;
    return (
      <path
        key={slice.label}
        d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} L ${xi2} ${yi2} A ${inner} ${inner} 0 ${large} 0 ${xi1} ${yi1} Z`}
        fill={slice.color}
      />
    );
  });

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <svg width={size} height={size} style={{ flexShrink: 0 }}>{paths}</svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {slices.map((s) => (
          <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: s.color, flexShrink: 0 }} />
            <span style={{ color: "#374151" }}>{s.label}</span>
            <span style={{ color: "#9ca3af" }}>({((s.value / total) * 100).toFixed(1)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stat card ──────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      flex: 1,
      padding: "12px 14px",
      background: "#fff",
      border: "1px solid #e5e7eb",
      borderRadius: 10,
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: "#111827", lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 10, color: "#6b7280", marginTop: 3 }}>{label}</div>
    </div>
  );
}

// ── Pipeline interpretation blurbs ────────────────────────────────────────

const PIPELINE_INTERPRETATION: Record<string, string> = {
  "nf-core/rnaseq":     "Open the MultiQC report first to check alignment rate and duplication metrics. The count matrix (in the Data tab) contains raw read counts — use DESeq2 or edgeR for differential expression. The volcano plot appears automatically when a DE results file is detected.",
  "nf-core/sarek":      "Review the MultiQC report for coverage and contamination. VCF files contain somatic/germline calls — filter by PASS in the Data tab. Check allele frequency (AF) in the INFO field. Clinical interpretation requires further annotation with VEP or ANNOVAR.",
  "nf-core/atacseq":    "Check the FRiP score (fraction of reads in peaks) in MultiQC — FRiP > 0.2 indicates a successful experiment. Peak files (.narrowPeak) can be loaded into IGV for visual inspection.",
  "nf-core/chipseq":    "Review the correlation heatmap in MultiQC to confirm replicate consistency. Peak files are suitable for motif enrichment (MEME-ChIP) or downstream TF binding analysis.",
  "nf-core/methylseq":  "Bismark alignment rate should be > 60% for good WGBS libraries. The CpG methylation files can be imported into R (bsseq or DMRcate) for differential methylation analysis.",
  "nf-core/ampliseq":   "DADA2 denoising produces exact amplicon sequence variants (ASVs). Check the rarefaction curve in MultiQC to confirm adequate sequencing depth. Relative abundance values are normalized per sample.",
  "nf-core/fetchngs":   "Download complete. FASTQ files have been fetched from SRA/ENA and are ready for downstream processing. Check file sizes and MD5 checksums in the report.",
  "snakemake":          "Snakemake wrappers ran modularly. Check each output file for expected formats and sizes. Log files contain per-rule execution details.",
  "bioscript":          "Custom bash pipeline complete. Review the log file for command output and exit codes. Output files are listed in the Data tab.",
};

function PipelineInterpretation({ pipeline }: { pipeline: string }) {
  const key = Object.keys(PIPELINE_INTERPRETATION).find((k) => pipeline.toLowerCase().includes(k.replace("nf-core/", "")));
  const text = key ? PIPELINE_INTERPRETATION[key] : null;
  if (!text) return null;
  return (
    <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 9, padding: "12px 14px", marginTop: 16 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#0369a1", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
        How to interpret these results
      </div>
      <p style={{ fontSize: 12, color: "#0c4a6e", lineHeight: 1.6, margin: 0 }}>{text}</p>
    </div>
  );
}

// ── Provenance card ────────────────────────────────────────────────────────

function ProvenanceCard({ provenance }: { provenance: Provenance }) {
  const [copied, setCopied] = useState(false);

  function buildMethodsText(): string {
    return [
      `Analysis was performed using ${provenance.pipeline ?? "the pipeline"}`,
      provenance.pipeline_version ? ` (v${provenance.pipeline_version})` : "",
      provenance.genome ? ` with reference genome ${provenance.genome}` : "",
      provenance.n_samples ? `. A total of ${provenance.n_samples} sample(s) were analysed` : "",
      `. The pipeline ran on a ${provenance.instance_type} instance for ${provenance.runtime_seconds} s`,
      `, completing on ${new Date(provenance.completed_at).toLocaleDateString()}.`,
    ].join("");
  }

  function handleCopy() {
    navigator.clipboard.writeText(buildMethodsText()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const paramEntries = Object.entries(provenance.params ?? {})
    .filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false);

  return (
    <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "14px 16px", marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Methods / Provenance
        </div>
        <button
          onClick={handleCopy}
          style={{ padding: "4px 10px", borderRadius: 5, border: "1px solid #d1d5db", background: "#fff", color: "#374151", cursor: "pointer", fontSize: 11 }}
        >
          {copied ? "Copied!" : "Copy methods text"}
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px", fontSize: 12 }}>
        {provenance.pipeline && (
          <div><span style={{ color: "#9ca3af" }}>Pipeline: </span><strong>{provenance.pipeline}</strong></div>
        )}
        {provenance.pipeline_version && (
          <div><span style={{ color: "#9ca3af" }}>Version: </span><strong>v{provenance.pipeline_version}</strong></div>
        )}
        {provenance.genome && (
          <div><span style={{ color: "#9ca3af" }}>Genome: </span><strong>{provenance.genome}</strong></div>
        )}
        {provenance.n_samples !== undefined && (
          <div><span style={{ color: "#9ca3af" }}>Samples: </span><strong>{provenance.n_samples}</strong></div>
        )}
        <div><span style={{ color: "#9ca3af" }}>Completed: </span><strong>{new Date(provenance.completed_at).toLocaleString()}</strong></div>
        <div><span style={{ color: "#9ca3af" }}>Instance: </span><strong>{provenance.instance_type}</strong></div>
      </div>
      {paramEntries.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Custom parameters</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {paramEntries.map(([k, v]) => (
              <code key={k} style={{ background: "#e0f2fe", color: "#0369a1", borderRadius: 4, padding: "2px 8px", fontSize: 11 }}>
                {k}={String(v)}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── HLA viewers ────────────────────────────────────────────────────────────

function AlleleCard({ gene, allele_1, allele_2 }: HLAAllele) {
  const ls = locusStyle(gene);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", background: "#fafafa", border: "1px solid #f0f0f0", borderRadius: 8, marginBottom: 5 }}>
      <div style={{ width: 34, height: 34, borderRadius: 7, background: ls.bg, display: "flex", alignItems: "center", justifyContent: "center", color: ls.text, fontWeight: 700, fontSize: 10, flexShrink: 0, border: `1px solid ${ls.accent}30` }}>
        {locusShort(gene)}
      </div>
      <div style={{ minWidth: 68, fontSize: 11, color: "#374151", fontWeight: 600 }}>{gene}</div>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
        <code style={{ background: ls.bg, color: ls.text, borderRadius: 5, padding: "3px 9px", fontSize: 11, fontFamily: "monospace", fontWeight: 500 }}>{allele_1}</code>
        <code style={{ background: ls.bg, color: ls.text, borderRadius: 5, padding: "3px 9px", fontSize: 11, fontFamily: "monospace", fontWeight: 500 }}>{allele_2}</code>
      </div>
    </div>
  );
}

function HLASummaryView({ alleles }: { alleles: HLAAllele[] }) {
  const classI  = alleles.filter((a) => /^HLA-[ABC]$/.test(a.gene));
  const classII = alleles.filter((a) => !classI.includes(a));
  const barData: BarEntry[] = alleles.map((a) => ({
    label: a.gene.replace("HLA-", ""),
    value: 2,
    color: locusStyle(a.gene).accent,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {classI.length > 0 && (
        <section>
          <SectionTitle>MHC Class I — {classI.map((a) => a.gene).join(", ")}</SectionTitle>
          {classI.map((a) => <AlleleCard key={a.gene} {...a} />)}
        </section>
      )}
      {classII.length > 0 && (
        <section>
          <SectionTitle>MHC Class II — {classII.map((a) => a.gene).join(", ")}</SectionTitle>
          {classII.map((a) => <AlleleCard key={a.gene} {...a} />)}
        </section>
      )}
      {alleles.length > 0 && (
        <section>
          <SectionTitle>Loci Genotyped</SectionTitle>
          <HBarChart data={barData} />
        </section>
      )}
    </div>
  );
}

function HLADataTab({ alleles }: { alleles: HLAAllele[] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ background: "#f9fafb" }}>
          {["Gene", "Allele 1", "Allele 2"].map((h) => (
            <th key={h} style={TH}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {alleles.map((a) => {
          const ls = locusStyle(a.gene);
          return (
            <tr key={a.gene} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={TD}><strong>{a.gene}</strong></td>
              <td style={TD}><code style={{ background: ls.bg, color: ls.text, borderRadius: 4, padding: "2px 8px", fontSize: 12, fontFamily: "monospace" }}>{a.allele_1}</code></td>
              <td style={TD}><code style={{ background: ls.bg, color: ls.text, borderRadius: 4, padding: "2px 8px", fontSize: 12, fontFamily: "monospace" }}>{a.allele_2}</code></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── VCF viewers ────────────────────────────────────────────────────────────

function VcfSummaryView({ variants }: { variants: VcfVariant[] }) {
  const chromCounts: Record<string, number> = {};
  for (const v of variants) chromCounts[v.chrom] = (chromCounts[v.chrom] ?? 0) + 1;

  const chromData: BarEntry[] = Object.entries(chromCounts)
    .sort(([a], [b]) => {
      const na = parseInt(a.replace(/^chr/i, "")), nb = parseInt(b.replace(/^chr/i, ""));
      return (isNaN(na) ? 99 : na) - (isNaN(nb) ? 99 : nb);
    })
    .slice(0, 20)
    .map(([label, value], i) => ({
      label,
      value,
      color: `hsl(${(i * 25) % 360}, 60%, 55%)`,
    }));

  const snps   = variants.filter((v) => v.ref.length === 1 && v.alt.length === 1).length;
  const indels = variants.filter((v) => Math.abs(v.ref.length - v.alt.length) > 0).length;
  const other  = variants.length - snps - indels;

  const typeSlices: DonutSlice[] = [
    { label: "SNPs",   value: snps,   color: "#3b82f6" },
    { label: "Indels", value: indels, color: "#f59e0b" },
    ...(other > 0 ? [{ label: "Other", value: other, color: "#9ca3af" }] : []),
  ].filter((s) => s.value > 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", gap: 10 }}>
        <StatCard label="Total Variants" value={variants.length.toLocaleString()} color="#3b82f6" />
        <StatCard label="SNPs"           value={snps.toLocaleString()}             color="#22c55e" />
        <StatCard label="Indels"         value={indels.toLocaleString()}           color="#f59e0b" />
      </div>

      {typeSlices.length > 0 && (
        <section>
          <SectionTitle>Variant Types</SectionTitle>
          <DonutChart slices={typeSlices} size={130} />
        </section>
      )}

      {chromData.length > 0 && (
        <section>
          <SectionTitle>Variants per Chromosome</SectionTitle>
          <HBarChart data={chromData} />
        </section>
      )}
    </div>
  );
}

function VcfDataTab({ jobId }: { jobId: string }) {
  const [rows, setRows] = useState<VcfVariant[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState(0);
  const [chroms, setChroms] = useState<string[]>([]);
  const [chrom, setChrom] = useState("");
  const [filterPass, setFilterPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<keyof VcfVariant>("chrom");
  const [asc, setAsc] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setRows([]);
    setNextOffset(0);
    setLoading(true);
    getVcfPage(jobId, 0, 100, chrom, filterPass)
      .then((res) => {
        if (cancelled) return;
        setRows(res.variants);
        if (res.chroms.length > 0) setChroms(res.chroms);
        setTotal(res.total);
        setNextOffset(res.next_offset ?? 100);
      })
      .catch(() => undefined)
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId, chrom, filterPass]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleLoadMore() {
    setLoading(true);
    getVcfPage(jobId, nextOffset, 100, chrom, filterPass)
      .then((res) => {
        setRows((prev) => [...prev, ...res.variants]);
        setTotal(res.total);
        setNextOffset(res.next_offset ?? nextOffset + 100);
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }

  function toggleSort(k: keyof VcfVariant) {
    if (sortKey === k) setAsc(!asc); else { setSortKey(k); setAsc(true); }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = String(a[sortKey] ?? ""), bv = String(b[sortKey] ?? "");
    return asc ? av.localeCompare(bv, undefined, { numeric: true }) : bv.localeCompare(av, undefined, { numeric: true });
  });

  const cols: (keyof VcfVariant)[] = ["chrom", "pos", "ref", "alt", "qual", "filter"];
  return (
    <>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
        <select
          value={chrom}
          onChange={(e) => setChrom(e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 12, background: "#fff", color: "#374151" }}
        >
          <option value="">All chromosomes</option>
          {chroms.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#374151", cursor: "pointer", userSelect: "none" }}>
          <input type="checkbox" checked={filterPass} onChange={(e) => setFilterPass(e.target.checked)} />
          PASS only
        </label>
        <div style={{ marginLeft: "auto", fontSize: 11, color: "#9ca3af" }}>
          {loading ? "Loading…" : `${rows.length.toLocaleString()} of ${total.toLocaleString()} variants`}
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead><tr style={{ background: "#f9fafb" }}>
            {cols.map((c) => (
              <th key={c} style={{ ...TH, cursor: "pointer", userSelect: "none" }} onClick={() => toggleSort(c)}>
                {c.toUpperCase()} {sortKey === c ? (asc ? "▲" : "▼") : ""}
              </th>
            ))}
          </tr></thead>
          <tbody>
            {sorted.map((v, i) => {
              const chromClean = String(v.chrom).replace(/^chr/i, "");
              const ensemblUrl = /^\d+$|^[XY]$|^MT$/i.test(chromClean)
                ? `https://www.ensembl.org/Homo_sapiens/Location/View?r=${v.chrom}:${v.pos}-${v.pos}`
                : null;
              return (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={TD}><code style={MONO_BLUE}>{v.chrom}</code></td>
                <td style={TD}>
                  {ensemblUrl
                    ? <a href={ensemblUrl} target="_blank" rel="noopener noreferrer" style={{ color: "#2563eb", textDecoration: "none", fontFamily: "monospace" }}>{v.pos} ↗</a>
                    : v.pos
                  }
                </td>
                <td style={TD}><code style={MONO_BLUE}>{v.ref}</code></td>
                <td style={TD}><code style={MONO_BLUE}>{v.alt}</code></td>
                <td style={TD}>{v.qual ?? "."}</td>
                <td style={TD}>{v.filter ?? "."}</td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length < total && (
        <div style={{ textAlign: "center", padding: "12px 0" }}>
          <button
            onClick={handleLoadMore}
            disabled={loading}
            style={{ padding: "7px 20px", borderRadius: 7, border: "1px solid #d1d5db", background: "#fff", color: "#374151", cursor: loading ? "default" : "pointer", fontSize: 12 }}
          >
            {loading ? "Loading…" : `Load more (${(total - rows.length).toLocaleString()} remaining)`}
          </button>
        </div>
      )}
    </>
  );
}

// ── Generic table viewer ───────────────────────────────────────────────────

function GenericTableViewer({ columns, rows }: { columns: string[]; rows: Record<string, string | number>[] }) {
  const [filter, setFilter] = useState("");
  const [sortCol, setSortCol] = useState(columns[0] ?? "");
  const [asc, setAsc] = useState(true);

  const filtered = rows.filter((r) =>
    !filter || Object.values(r).some((v) => String(v).toLowerCase().includes(filter.toLowerCase()))
  );
  const sorted = [...filtered].sort((a, b) => {
    const av = String(a[sortCol] ?? ""), bv = String(b[sortCol] ?? "");
    return asc ? av.localeCompare(bv, undefined, { numeric: true }) : bv.localeCompare(av, undefined, { numeric: true });
  });

  return (
    <>
      <input placeholder="Filter rows…" value={filter} onChange={(e) => setFilter(e.target.value)} style={FILTER_INPUT} />
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead><tr style={{ background: "#f9fafb" }}>
            {columns.map((c) => (
              <th key={c} style={{ ...TH, cursor: "pointer", userSelect: "none" }}
                onClick={() => { if (sortCol === c) setAsc(!asc); else { setSortCol(c); setAsc(true); } }}>
                {c} {sortCol === c ? (asc ? "▲" : "▼") : ""}
              </th>
            ))}
          </tr></thead>
          <tbody>
            {sorted.slice(0, 200).map((r, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                {columns.map((c) => <td key={c} style={TD}>{String(r[c] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length > 200 && <div style={MORE_HINT}>Showing 200 of {sorted.length} rows</div>}
      </div>
    </>
  );
}

// ── Downloads tab ──────────────────────────────────────────────────────────

function DownloadsTab({ result, kind }: { result: JobResult; kind: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    if (!result.hla_alleles) return;
    const text = result.hla_alleles.map((a) => `${a.gene}: ${a.allele_1} / ${a.allele_2}`).join("\n");
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }

  function makeTsv(): string | null {
    if (kind === "hla_alleles" && result.hla_alleles) {
      return ["Gene\tAllele 1\tAllele 2", ...result.hla_alleles.map((a) => `${a.gene}\t${a.allele_1}\t${a.allele_2}`)].join("\n");
    }
    if (kind === "table" && result.columns && result.rows) {
      return [result.columns.join("\t"), ...result.rows.map((r) => result.columns!.map((c) => String(r[c] ?? "")).join("\t"))].join("\n");
    }
    if (kind === "vcf" && result.variants) {
      return ["CHROM\tPOS\tREF\tALT\tQUAL\tFILTER", ...result.variants.map((v) => `${v.chrom}\t${v.pos}\t${v.ref}\t${v.alt}\t${v.qual ?? "."}\t${v.filter ?? "."}`)].join("\n");
    }
    return null;
  }

  const tsv = makeTsv();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>
        Download your results in multiple formats.
      </p>

      <DlButton icon="📦" label="Download JSON" sub="Complete result payload" onClick={() => dlJson(result, `results_${Date.now()}.json`)} />

      {tsv && (
        <DlButton icon="📊" label="Download TSV" sub="Tab-separated, compatible with Excel" onClick={() => dlText(tsv, kind === "vcf" ? "variants.tsv" : "results.tsv", "text/tab-separated-values")} />
      )}

      {kind === "hla_alleles" && (
        <DlButton icon={copied ? "✅" : "📋"} label={copied ? "Copied!" : "Copy Alleles to Clipboard"} sub="Gene: Allele1 / Allele2 format" onClick={handleCopy} />
      )}

      {kind === "html_report" && result.html && (
        <DlButton icon="📄" label="Download HTML Report" sub="Self-contained interactive report" onClick={() => dlText(result.html!, "report.html", "text/html")} />
      )}

      {kind === "text" && result.content && (
        <DlButton icon="📝" label="Download Text Output" sub="Plain text log / output" onClick={() => dlText(result.content!, "output.txt")} />
      )}
    </div>
  );
}

function DlButton({ icon, label, sub, onClick }: { icon: string; label: string; sub: string; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "13px 16px",
        background: hover ? "#f0f7ff" : "#fff",
        border: `1px solid ${hover ? "#3b82f6" : "#e5e7eb"}`,
        borderRadius: 10,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.15s",
        width: "100%",
      }}
    >
      <span style={{ fontSize: 22, flexShrink: 0 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>{label}</div>
        <div style={{ fontSize: 11, color: "#6b7280", marginTop: 1 }}>{sub}</div>
      </div>
    </button>
  );
}

// ── Section title ──────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
      {children}
    </div>
  );
}

// ── Shared styles ──────────────────────────────────────────────────────────

const TH: React.CSSProperties = {
  padding: "9px 13px",
  textAlign: "left",
  fontSize: 11,
  fontWeight: 600,
  color: "#6b7280",
  borderBottom: "1px solid #e5e7eb",
  whiteSpace: "nowrap",
};
const TD: React.CSSProperties = { padding: "9px 13px" };
const MONO_BLUE: React.CSSProperties = {
  fontFamily: "monospace",
  background: "#eff6ff",
  color: "#1d4ed8",
  padding: "2px 7px",
  borderRadius: 4,
  fontSize: 12,
};
const FILTER_INPUT: React.CSSProperties = {
  width: "100%",
  padding: "7px 10px",
  borderRadius: 7,
  border: "1px solid #d1d5db",
  fontSize: 12,
  marginBottom: 10,
  boxSizing: "border-box",
  outline: "none",
};
const MORE_HINT: React.CSSProperties = {
  fontSize: 11,
  color: "#9ca3af",
  textAlign: "center",
  padding: "8px",
};

// ── Panel icon button ──────────────────────────────────────────────────────

function IconBtn({ onClick, title, children }: { onClick: () => void; title: string; children: React.ReactNode }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      title={title}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width: 30, height: 30,
        borderRadius: 6,
        border: "1px solid #e5e7eb",
        background: hover ? "#f3f4f6" : "#fff",
        cursor: "pointer",
        fontSize: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        transition: "background 0.12s",
      }}
    >
      {children}
    </button>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

interface ResultsPanelProps {
  job: Job;
  isOpen: boolean;
  onClose: () => void;
  onReset: () => void;
}

export function ResultsPanel({ job, isOpen, onClose, onReset }: ResultsPanelProps) {
  const [pos, setPos] = useState<"side" | "center">("side");
  const [tab, setTab] = useState<"summary" | "data" | "downloads" | "raw">("summary");
  const [downloadingPath, setDownloadingPath] = useState<string | null>(null);

  async function handleFileDownload(path: string) {
    // S3 paths: generate presigned URL and open in new tab
    if (path.startsWith("s3://")) {
      setDownloadingPath(path);
      try {
        const url = await getDownloadUrl(job.job_id, path);
        window.open(url, "_blank", "noopener");
      } catch {
        // fallback: copy path to clipboard
        navigator.clipboard.writeText(path).catch(() => undefined);
      } finally {
        setDownloadingPath(null);
      }
    } else if (path.startsWith("http")) {
      window.open(path, "_blank", "noopener");
    }
  }

  const result = job.result;
  if (!result) return null;

  const kind = detectType(result);
  const isSide = pos === "side";

  const panelStyle: React.CSSProperties = isSide
    ? {
        position: "fixed",
        top: 0,
        right: 0,
        height: "100vh",
        width: 480,
        background: "#fff",
        borderLeft: "1px solid #e5e7eb",
        boxShadow: "-6px 0 32px rgba(0,0,0,0.14)",
        display: "flex",
        flexDirection: "column",
        zIndex: 200,
        transform: isOpen ? "translateX(0)" : "translateX(100%)",
        transition: "transform 0.32s cubic-bezier(0.4, 0, 0.2, 1)",
        pointerEvents: isOpen ? "all" : "none",
      }
    : {
        position: "fixed",
        top: "50%",
        left: "50%",
        width: "min(900px, 94vw)",
        height: "min(86vh, 820px)",
        background: "#fff",
        borderRadius: 14,
        boxShadow: "0 24px 80px rgba(0,0,0,0.22)",
        display: "flex",
        flexDirection: "column",
        zIndex: 200,
        transform: isOpen ? "translate(-50%, -50%)" : "translate(-50%, 110%)",
        transition: "transform 0.32s cubic-bezier(0.4, 0, 0.2, 1)",
        pointerEvents: isOpen ? "all" : "none",
      };

  const tabs = ["summary", "data", "downloads", "raw"] as const;

  return (
    <>
      {/* Backdrop for center mode */}
      {!isSide && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            zIndex: 199,
            opacity: isOpen ? 1 : 0,
            transition: "opacity 0.32s",
            pointerEvents: isOpen ? "all" : "none",
          }}
          onClick={onClose}
        />
      )}

      <div style={panelStyle}>
        {/* ── Header ── */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "13px 16px", borderBottom: "1px solid #e5e7eb", background: "#fafafa", flexShrink: 0 }}>
          <span style={{ fontSize: 20 }}>📊</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#111827" }}>Analysis Results</div>
            <div style={{ fontSize: 10, color: "#6b7280" }}>
              {job.status === "completed" ? "✅ Completed" : "❌ Failed"}
              {" · "}{result.instance_type}
              {" · "}{result.runtime_seconds}s
              {" · "}${job.estimated_cost_usd.toFixed(2)}
            </div>
          </div>
          <IconBtn
            onClick={() => setPos(isSide ? "center" : "side")}
            title={isSide ? "Expand to center" : "Snap to side"}
          >
            {isSide ? "⊡" : "⊞"}
          </IconBtn>
          <IconBtn onClick={onClose} title="Close panel">×</IconBtn>
        </div>

        {/* ── Tabs ── */}
        <div style={{ display: "flex", borderBottom: "1px solid #e5e7eb", background: "#fafafa", flexShrink: 0 }}>
          {tabs.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: "9px 18px",
                border: "none",
                borderBottom: `2px solid ${tab === t ? "#3b82f6" : "transparent"}`,
                background: "none",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: tab === t ? 700 : 400,
                color: tab === t ? "#2563eb" : "#6b7280",
                transition: "all 0.15s",
              }}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* ── Content ── */}
        <div style={{ flex: 1, overflowY: "auto", padding: "18px 20px" }}>

          {/* SUMMARY TAB */}
          {tab === "summary" && (
            <>
              {result._mock && (
                <div style={{ background: "#fef3c7", border: "1px solid #fbbf24", borderRadius: 8, padding: "10px 14px", marginBottom: 16, display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span style={{ fontSize: 18, flexShrink: 0 }}>⚠️</span>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#92400e" }}>Demo data — not for clinical use</div>
                    <div style={{ fontSize: 11, color: "#a16207", marginTop: 2, lineHeight: 1.4 }}>
                      This result was produced by a mock runner for demonstration purposes. Set <code style={{ background: "#fde68a", padding: "1px 4px", borderRadius: 3 }}>NEXTFLOW_BACKEND=awsbatch</code> (or the equivalent for your runner) to run real analysis.
                    </div>
                  </div>
                </div>
              )}
              <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
                <StatCard label="Instance"  value={result.instance_type}               color="#6b7280" />
                <StatCard label="Runtime"   value={`${result.runtime_seconds}s`}       color="#3b82f6" />
                <StatCard label="Est. Cost" value={`$${job.estimated_cost_usd.toFixed(2)}`} color="#22c55e" />
              </div>

              {kind === "hla_alleles" && result.hla_alleles && (
                <HLASummaryView alleles={result.hla_alleles} />
              )}
              {kind === "vcf" && result.variants && (
                <VcfSummaryView variants={result.variants} />
              )}
              {kind === "table" && result.rows && result.columns && isDETable(result) ? (
                <VolcanoPlot columns={result.columns} rows={result.rows} />
              ) : kind === "table" && result.rows ? (
                <StatCard label="Result rows" value={result.rows.length.toLocaleString()} color="#3b82f6" />
              ) : null}
              {kind === "html_report" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ padding: "12px 14px", background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 8 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#0369a1" }}>HTML Report ready</div>
                    <div style={{ fontSize: 11, color: "#0284c7", marginTop: 2 }}>Interactive MultiQC report with QC metrics.</div>
                  </div>
                  <button onClick={() => setTab("data")} style={{ padding: "7px 14px", borderRadius: 7, border: "1px solid #bae6fd", background: "#e0f2fe", color: "#0369a1", cursor: "pointer", fontSize: 12, fontWeight: 600, textAlign: "left" as const }}>
                    View Report →
                  </button>
                </div>
              )}
              {kind === "files" && result.files && (() => {
                const files = result.files;
                const htmlFiles  = files.filter((f) => isHtmlFile(f));
                const bamFiles   = files.filter((f) => /\.(bam|cram|sam)$/i.test(f.name));
                const vcfFiles   = files.filter((f) => /\.(vcf|bcf)(\.gz)?$/i.test(f.name));
                const fastaFiles = files.filter((f) => /\.(fa|fasta|fna|ffn|faa)(\.gz)?$/i.test(f.name));
                const otherFiles = files.filter((f) => !htmlFiles.includes(f) && !bamFiles.includes(f) && !vcfFiles.includes(f) && !fastaFiles.includes(f));
                return (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <StatCard label="Total files"   value={files.length.toLocaleString()}      color="#8b5cf6" />
                      {htmlFiles.length  > 0 && <StatCard label="QC reports" value={htmlFiles.length.toLocaleString()}  color="#0ea5e9" />}
                      {bamFiles.length   > 0 && <StatCard label="Alignments" value={bamFiles.length.toLocaleString()}   color="#22c55e" />}
                      {vcfFiles.length   > 0 && <StatCard label="Variants"   value={vcfFiles.length.toLocaleString()}   color="#f59e0b" />}
                      {fastaFiles.length > 0 && <StatCard label="Sequences"  value={fastaFiles.length.toLocaleString()} color="#6366f1" />}
                      {otherFiles.length > 0 && <StatCard label="Other"      value={otherFiles.length.toLocaleString()} color="#9ca3af" />}
                    </div>
                    {htmlFiles.length > 0 && (
                      <div style={{ padding: "10px 12px", background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#0369a1", marginBottom: 4 }}>
                          📊 {htmlFiles.length} HTML report{htmlFiles.length > 1 ? "s" : ""} available
                        </div>
                        <div style={{ fontSize: 11, color: "#0284c7" }}>
                          Open the Data tab to browse output files and download reports.
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}
              {kind === "text" && (
                <div style={{ fontSize: 13, color: "#6b7280" }}>Switch to the Data tab to view results.</div>
              )}
              {result.provenance && <ProvenanceCard provenance={result.provenance} />}
              {result.provenance?.pipeline && <PipelineInterpretation pipeline={result.provenance.pipeline} />}
            </>
          )}

          {/* DATA TAB */}
          {tab === "data" && (
            <>
              {kind === "hla_alleles" && result.hla_alleles && <HLADataTab alleles={result.hla_alleles} />}
              {kind === "vcf"         && <VcfDataTab jobId={job.job_id} />}
              {kind === "table"       && result.columns     && result.rows && (
                <GenericTableViewer columns={result.columns} rows={result.rows} />
              )}
              {kind === "html_report" && result.html && (
                <iframe
                  srcDoc={result.html}
                  style={{ width: "100%", height: "100%", minHeight: 500, border: "1px solid #e5e7eb", borderRadius: 8 }}
                  sandbox="allow-scripts"
                  title="Pipeline report"
                />
              )}
              {kind === "files" && result.files && (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {result.files.map((f, i) => {
                    const isS3 = f.path.startsWith("s3://");
                    const isHttp = f.path.startsWith("http");
                    const canDownload = isS3 || isHttp;
                    const isLoading = downloadingPath === f.path;
                    const isHtml = isHtmlFile(f);
                    return (
                      <div key={i} style={{ padding: "9px 12px", background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 7, display: "flex", gap: 10, alignItems: "flex-start" }}>
                        <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>{fileIcon(f.mime_type, f.name)}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</div>
                          {f.description && (
                            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 1, lineHeight: 1.3 }}>{f.description}</div>
                          )}
                          <div style={{ fontSize: 10, color: "#9ca3af", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 2 }}>{f.path}</div>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4, flexShrink: 0 }}>
                          {f.size_bytes !== undefined && (
                            <div style={{ fontSize: 11, color: "#9ca3af" }}>{formatBytes(f.size_bytes)}</div>
                          )}
                          <div style={{ display: "flex", gap: 4 }}>
                            {isHtml && isHttp && (
                              <button
                                onClick={() => window.open(f.path, "_blank", "noopener")}
                                title="Open report in new tab"
                                style={{ padding: "4px 10px", borderRadius: 5, border: "1px solid #bae6fd", background: "#e0f2fe", color: "#0369a1", cursor: "pointer", fontSize: 11, fontWeight: 500 }}
                              >
                                Open
                              </button>
                            )}
                            {canDownload && (
                              <button
                                onClick={() => handleFileDownload(f.path)}
                                disabled={isLoading}
                                title="Download file"
                                style={{ padding: "4px 10px", borderRadius: 5, border: "1px solid #d1d5db", background: "#fff", color: "#374151", cursor: "pointer", fontSize: 12, fontWeight: 500 }}
                              >
                                {isLoading ? "…" : "⬇"}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {kind === "text" && result.content && (
                <pre style={{ background: "#0f172a", color: "#e2e8f0", padding: "18px 20px", borderRadius: 10, fontSize: 11, lineHeight: 1.7, overflowX: "auto", margin: 0 }}>
                  {result.content}
                </pre>
              )}
              {kind === "unknown" && (
                <pre style={{ background: "#0f172a", color: "#e2e8f0", padding: "18px 20px", borderRadius: 10, fontSize: 11, lineHeight: 1.6, overflowX: "auto", margin: 0 }}>
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </>
          )}

          {/* DOWNLOADS TAB */}
          {tab === "downloads" && <DownloadsTab result={result} kind={kind} />}

          {/* RAW TAB */}
          {tab === "raw" && (
            <pre style={{ background: "#0f172a", color: "#e2e8f0", padding: "18px 20px", borderRadius: 10, fontSize: 11, lineHeight: 1.6, overflowX: "auto", margin: 0 }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>

        {/* ── Footer ── */}
        <div style={{ padding: "10px 16px", borderTop: "1px solid #e5e7eb", background: "#fafafa", display: "flex", gap: 8, flexShrink: 0 }}>
          <button
            onClick={() => { dlJson(result, `results_${Date.now()}.json`); }}
            style={{ padding: "7px 14px", borderRadius: 7, border: "1px solid #d1d5db", background: "#fff", color: "#374151", cursor: "pointer", fontSize: 12, fontWeight: 500 }}
          >
            ⬇ JSON
          </button>
          <div style={{ flex: 1 }} />
          <button
            onClick={onReset}
            style={{ padding: "7px 16px", borderRadius: 7, border: "none", background: "#2563eb", color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
          >
            New Analysis
          </button>
        </div>
      </div>
    </>
  );
}
