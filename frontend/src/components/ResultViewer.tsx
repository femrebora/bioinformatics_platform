import type { Job, JobResult, HLAAllele, VcfVariant, ResultFile } from "../types/job";

interface Props {
  job: Job;
  onReset: () => void;
}

/** Detect the result type when the backend doesn't set the `type` field. */
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

// ── Sub-renderers ──────────────────────────────────────────────────────────

function HLATable({ alleles }: { alleles: HLAAllele[] }) {
  return (
    <>
      <h2 style={s.title}>HLA Typing Results</h2>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>Gene</th>
            <th style={s.th}>Allele 1</th>
            <th style={s.th}>Allele 2</th>
          </tr>
        </thead>
        <tbody>
          {alleles.map((row) => (
            <tr key={row.gene} style={s.tr}>
              <td style={{ ...s.td, fontWeight: 600 }}>{row.gene}</td>
              <td style={s.td}><code style={s.mono}>{row.allele_1}</code></td>
              <td style={s.td}><code style={s.mono}>{row.allele_2}</code></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function GenericTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: Record<string, string | number>[];
}) {
  return (
    <>
      <h2 style={s.title}>Results</h2>
      <table style={s.table}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} style={s.th}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={s.tr}>
              {columns.map((c) => (
                <td key={c} style={s.td}>{String(row[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function VcfTable({ variants }: { variants: VcfVariant[] }) {
  const cols = ["chrom", "pos", "ref", "alt", "qual", "filter"] as const;
  return (
    <>
      <h2 style={s.title}>Variant Calls</h2>
      <div style={{ overflowX: "auto" }}>
        <table style={s.table}>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c} style={s.th}>{c.toUpperCase()}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {variants.map((v, i) => (
              <tr key={i} style={s.tr}>
                <td style={s.td}><code style={s.mono}>{v.chrom}</code></td>
                <td style={s.td}>{v.pos}</td>
                <td style={s.td}><code style={s.mono}>{v.ref}</code></td>
                <td style={s.td}><code style={s.mono}>{v.alt}</code></td>
                <td style={s.td}>{v.qual ?? "."}</td>
                <td style={s.td}>{v.filter ?? "."}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function HtmlReport({ html }: { html: string }) {
  return (
    <>
      <h2 style={s.title}>Report</h2>
      <iframe
        srcDoc={html}
        style={s.iframe}
        sandbox="allow-scripts"
        title="Pipeline report"
      />
    </>
  );
}

function TextResult({ content }: { content: string }) {
  return (
    <>
      <h2 style={s.title}>Output</h2>
      <pre style={s.pre}>{content}</pre>
    </>
  );
}

function FileList({ files }: { files: ResultFile[] }) {
  function fmtBytes(n?: number) {
    if (n === undefined) return "";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  return (
    <>
      <h2 style={s.title}>Output Files</h2>
      <div style={s.fileList}>
        {files.map((f) => (
          <div key={f.path} style={s.fileRow}>
            <span style={s.fileIcon}>{fileIcon(f.name)}</span>
            <span style={s.fileName}>
              {f.url ? (
                <a href={f.url} style={s.fileLink} download={f.name}>{f.name}</a>
              ) : (
                f.name
              )}
            </span>
            {f.size_bytes !== undefined && (
              <span style={s.fileSize}>{fmtBytes(f.size_bytes)}</span>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function fileIcon(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    bam: "🧬", cram: "🧬", sam: "🧬",
    vcf: "🔍", bcf: "🔍",
    html: "📄", pdf: "📑",
    tsv: "📊", csv: "📊",
    txt: "📝",
    fastq: "🧬", fq: "🧬",
    fa: "🔬", fasta: "🔬",
    json: "📦",
    png: "🖼️", svg: "🖼️", jpg: "🖼️",
  };
  return map[ext] ?? "📁";
}

function UnknownResult({ result }: { result: JobResult }) {
  return (
    <>
      <h2 style={s.title}>Results</h2>
      <pre style={s.pre}>{JSON.stringify(result, null, 2)}</pre>
    </>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function ResultViewer({ job, onReset }: Props) {
  const result = job.result;
  if (!result) return null;

  const kind = detectType(result);

  return (
    <div style={s.wrapper}>
      {kind === "hla_alleles" && result.hla_alleles?.length ? (
        <HLATable alleles={result.hla_alleles} />
      ) : kind === "table" && result.columns && result.rows ? (
        <GenericTable columns={result.columns} rows={result.rows} />
      ) : kind === "vcf" && result.variants ? (
        <VcfTable variants={result.variants} />
      ) : kind === "html_report" && result.html ? (
        <HtmlReport html={result.html} />
      ) : kind === "text" && result.content ? (
        <TextResult content={result.content} />
      ) : kind === "files" && result.files ? (
        <FileList files={result.files} />
      ) : (
        <UnknownResult result={result} />
      )}

      <div style={s.meta}>
        <span>Instance: <strong>{result.instance_type}</strong></span>
        <span>Runtime: <strong>{result.runtime_seconds}s</strong></span>
        <span>Cost: <strong>${job.estimated_cost_usd.toFixed(2)}</strong></span>
      </div>

      <button style={s.resetBtn} onClick={onReset}>
        Run Another Analysis
      </button>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  wrapper: { maxWidth: 720, margin: "0 auto" },
  title: { fontSize: 22, fontWeight: 700, marginBottom: 20 },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "#fff",
    borderRadius: 10,
    overflow: "hidden",
    border: "1px solid #e5e7eb",
  },
  th: {
    background: "#f9fafb",
    padding: "12px 16px",
    textAlign: "left",
    fontSize: 13,
    fontWeight: 600,
    color: "#6b7280",
    borderBottom: "1px solid #e5e7eb",
  },
  tr: { borderBottom: "1px solid #f3f4f6" },
  td: { padding: "12px 16px", fontSize: 14 },
  mono: {
    fontFamily: "monospace",
    background: "#eff6ff",
    color: "#1d4ed8",
    padding: "2px 8px",
    borderRadius: 6,
    fontSize: 13,
  },
  pre: {
    background: "#1e293b",
    color: "#e2e8f0",
    borderRadius: 8,
    padding: "16px 20px",
    fontSize: 12,
    overflowX: "auto",
    lineHeight: 1.6,
  },
  iframe: {
    width: "100%",
    height: 500,
    border: "1px solid #e5e7eb",
    borderRadius: 8,
  },
  fileList: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: "8px 0",
    overflow: "hidden",
  },
  fileRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "8px 16px",
    borderBottom: "1px solid #f3f4f6",
  },
  fileIcon: { fontSize: 16, flexShrink: 0 },
  fileName: { flex: 1, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  fileLink: { color: "#2563eb", textDecoration: "none" },
  fileSize: { fontSize: 11, color: "#9ca3af", flexShrink: 0 },
  meta: {
    display: "flex",
    gap: 24,
    marginTop: 16,
    fontSize: 13,
    color: "#6b7280",
  },
  resetBtn: {
    marginTop: 24,
    padding: "10px 24px",
    borderRadius: 8,
    border: "none",
    background: "#2563eb",
    color: "#fff",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
  },
};
