import type { GraphData } from "../types/pipeline";

/**
 * Extract file extensions from an nf-core port pattern string.
 * Handles: "*.bam", "*.{bam,cram}", "*_{1,2}.fastq.gz", "{*.bam,*.cram}"
 */
export function extractExtensions(pattern: string): string[] {
  if (!pattern) return [];
  const exts = new Set<string>();

  // Step 1: expand brace groups — e.g. {bam,cram} or {*.bam,*.cram}
  const withoutBraces = pattern.replace(/\{([^}]+)\}/g, (_m, inner: string) => {
    inner.split(",").forEach((part) => {
      const t = part.trim();
      const starred = t.match(/\*\.(.+)/);
      if (starred) {
        exts.add(starred[1].toLowerCase());
      } else if (t && !t.includes("*") && !t.includes("/")) {
        exts.add(t.replace(/^\./, "").toLowerCase());
      }
    });
    return "";
  });

  // Step 2: find *.ext or *.ext.ext2 in the remainder
  for (const m of withoutBraces.matchAll(/\*\.([\w.]+)/g)) {
    exts.add(m[1].toLowerCase());
  }

  // Step 3: fallback — take the trailing extension of the pattern
  if (exts.size === 0) {
    const m = pattern.match(/\.([\w.]+)$/);
    if (m) exts.add(m[1].toLowerCase());
  }

  return [...exts];
}

/**
 * Return true if two nf-core port patterns share at least one file extension.
 * Permissive when either pattern is empty/unknown.
 */
export function patternsOverlap(p1: string, p2: string): boolean {
  if (!p1 || !p2) return true;
  const e1 = extractExtensions(p1);
  const e2 = extractExtensions(p2);
  if (e1.length === 0 || e2.length === 0) return true; // can't determine → allow
  return e1.some((e) => e2.includes(e));
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

export function validatePipeline(graph: GraphData): ValidationResult {
  const errors: string[] = [];

  const inputNodes     = graph.nodes.filter((n) => n.type === "inputFile");
  const resultsNodes   = graph.nodes.filter((n) => n.type === "results");
  const nfModuleNodes  = graph.nodes.filter((n) => n.type === "nfcoreModule");
  const nfPipeNodes    = graph.nodes.filter((n) => n.type === "nfcorePipeline");
  const sampleSheetNodes = graph.nodes.filter((n) => n.type === "sampleSheetBuilder");
  const smkWrappers    = graph.nodes.filter((n) => n.type === "snakemakeWrapper");
  const smkWorkflows   = graph.nodes.filter((n) => n.type === "snakemakeWorkflow");
  const bsNodes        = graph.nodes.filter((n) => n.type === "bioScript");
  const customNodes    = graph.nodes.filter((n) => n.type === "customPipeline");

  const hasNfcoreParts = nfModuleNodes.length > 0 || nfPipeNodes.length > 0 || sampleSheetNodes.length > 0;
  const hasSmkParts    = smkWrappers.length > 0 || smkWorkflows.length > 0;
  const hasBsParts     = bsNodes.length > 0;
  const hasCustomParts = customNodes.length > 0;

  // ── Empty canvas ────────────────────────────────────────────────────────
  if (graph.nodes.length === 0) {
    return { valid: false, errors: [] };
  }

  // ── Only generic nodes, nothing runnable yet ────────────────────────────
  if (!hasNfcoreParts && !hasSmkParts && !hasBsParts && !hasCustomParts && resultsNodes.length === 0) {
    return { valid: false, errors: [] };
  }

  // ── Multiple InputFileNodes without a SampleSheet ─────────────────────
  if (inputNodes.length > 1 && sampleSheetNodes.length === 0) {
    errors.push(
      "Multiple Input File nodes detected — use a Sample Sheet node to define multi-sample runs. " +
      "Multiple bare Input File nodes are not supported; only the first would be used."
    );
  }

  // ── nf-core rules (permissive — just needs at least one module/pipeline) ─
  if (hasNfcoreParts && !hasSmkParts) {
    // Genome must be selected on NfCorePipelineNode
    for (const pipe of nfPipeNodes) {
      const genome = (pipe.data as { genome?: string }).genome ?? "";
      if (!genome) {
        errors.push(`Select a reference genome on "${(pipe.data as { label?: string }).label ?? "nf-core Pipeline"}".`);
      }
    }
    // If an InputFileNode is present it should be connected to something
    for (const inp of inputNodes) {
      const connected = graph.edges.some((e) => e.source === inp.id);
      if (!connected) {
        errors.push(`"${(inp.data as { label?: string }).label ?? "Input File"}" is not connected to any module.`);
      }
    }
    // SampleSheet must have at least one complete row (name + r1_key)
    for (const ssn of sampleSheetNodes) {
      type Row = { sample_name: string; r1_key: string };
      const rows = ((ssn.data as { samples?: Row[] }).samples ?? []);
      const complete = rows.filter((r) => r.sample_name.trim() && r.r1_key.trim());
      if (complete.length === 0) {
        errors.push("Sample Sheet must have at least one sample with a name and R1 key.");
      }
    }
  }

  // ── Snakemake rules (permissive — wrappers/workflows can run standalone) ─
  if (hasSmkParts) {
    // Wrappers/workflows just need at least one node — already guaranteed above
    // If InputFileNode is present, it should be connected to something
    const isMixed = hasNfcoreParts && hasSmkParts;
    for (const inp of inputNodes) {
      const connected = graph.edges.some((e) => e.source === inp.id);
      if (!connected) {
        errors.push(
          isMixed
            ? `"${(inp.data as { label?: string }).label ?? "Input File"}" is not connected to any processing node.`
            : `"${(inp.data as { label?: string }).label ?? "Input File"}" is not connected to any Snakemake node.`
        );
      }
    }
  }

  // ── BioScript rules — permissive; just needs the node ────────────────────
  if (hasBsParts && !hasNfcoreParts && !hasSmkParts) {
    const bsNode = bsNodes[0];
    const script = ((bsNode.data as { script?: string }).script ?? "").trim();
    if (!script) {
      errors.push("Write a bash script in the BioScript node.");
    }
  }

  // ── Custom pipeline rules — permissive; just needs the node ──────────────
  if (hasCustomParts && !hasNfcoreParts && !hasSmkParts && !hasBsParts) {
    if (inputNodes.length === 0) {
      errors.push("Add an Input File node to provide data to the custom pipeline.");
    }
  }

  return { valid: errors.length === 0, errors };
}
