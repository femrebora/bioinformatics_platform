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

  const inputNodes    = graph.nodes.filter((n) => n.type === "inputFile");
  const hlaNodes      = graph.nodes.filter((n) => n.type === "hlaTyping");
  const resultsNodes  = graph.nodes.filter((n) => n.type === "results");
  const converterNodes= graph.nodes.filter((n) => n.type === "fastqToBam");
  const nfModuleNodes = graph.nodes.filter((n) => n.type === "nfcoreModule");
  const nfPipeNodes   = graph.nodes.filter((n) => n.type === "nfcorePipeline");

  const hasHlaParts   = hlaNodes.length > 0 || converterNodes.length > 0;
  const hasNfcoreParts= nfModuleNodes.length > 0 || nfPipeNodes.length > 0;

  // ── Empty canvas ────────────────────────────────────────────────────────
  if (graph.nodes.length === 0) {
    // Disabled with no error message — user hasn't started yet
    return { valid: false, errors: [] };
  }

  // ── Only generic nodes, nothing runnable yet ────────────────────────────
  // e.g. just an InputFileNode or Results node alone — don't show HLA errors
  if (!hasHlaParts && !hasNfcoreParts && resultsNodes.length === 0) {
    return { valid: false, errors: [] };
  }

  // ── HLA pipeline rules (only when HLA-HD or converter nodes are present) ─
  if (hasHlaParts) {
    if (inputNodes.length !== 1) {
      errors.push(
        inputNodes.length === 0
          ? "Add an Input File node."
          : "Only one Input File node is allowed."
      );
    }
    if (hlaNodes.length !== 1) {
      errors.push(
        hlaNodes.length === 0
          ? "Add an HLA-HD Typing node."
          : "Only one HLA-HD Typing node is allowed."
      );
    }
    if (resultsNodes.length > 1) {
      errors.push("Only one Results node is allowed.");
    }
    if (converterNodes.length > 1) {
      errors.push("Only one FASTQ → BAM converter is allowed.");
    }

    if (errors.length === 0 && inputNodes.length === 1 && hlaNodes.length === 1) {
      const inputId = inputNodes[0].id;
      const hlaId   = hlaNodes[0].id;

      if (converterNodes.length === 1) {
        const convId = converterNodes[0].id;
        const hasInputToConv = graph.edges.some(
          (e) =>
            e.source === inputId && e.sourceHandle === "file-out" &&
            e.target === convId  && e.targetHandle === "fastq-in"
        );
        if (!hasInputToConv) errors.push("Connect Input File → FASTQ→BAM converter.");

        const hasConvToHla = graph.edges.some(
          (e) =>
            e.source === convId && e.sourceHandle === "bam-out" &&
            e.target === hlaId  && e.targetHandle === "file-in"
        );
        if (!hasConvToHla) errors.push("Connect FASTQ→BAM converter → HLA-HD Typing.");
      } else {
        const hasInputToHla = graph.edges.some(
          (e) =>
            e.source === inputId && e.sourceHandle === "file-out" &&
            e.target === hlaId   && e.targetHandle === "file-in"
        );
        if (!hasInputToHla) errors.push("Connect Input File → HLA-HD Typing.");
      }

      if (resultsNodes.length === 1) {
        const hasHlaToResults = graph.edges.some(
          (e) =>
            e.source === hlaId           && e.sourceHandle === "result-out" &&
            e.target === resultsNodes[0].id && e.targetHandle === "result-in"
        );
        if (!hasHlaToResults) errors.push("Connect HLA-HD Typing → Results.");
      }
    }
  }

  // ── nf-core rules (permissive — just needs at least one module/pipeline) ─
  if (hasNfcoreParts && !hasHlaParts) {
    // If an InputFileNode is present it should be connected to something
    for (const inp of inputNodes) {
      const connected = graph.edges.some((e) => e.source === inp.id);
      if (!connected) {
        errors.push(`"${(inp.data as { label?: string }).label ?? "Input File"}" is not connected to any module.`);
      }
    }
    // Otherwise nf-core modules freely connected to each other → valid
  }

  return { valid: errors.length === 0, errors };
}
