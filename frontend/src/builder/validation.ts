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

  const inputNodes = graph.nodes.filter((n) => n.type === "inputFile");
  const hlaNodes = graph.nodes.filter((n) => n.type === "hlaTyping");
  const resultsNodes = graph.nodes.filter((n) => n.type === "results");
  const converterNodes = graph.nodes.filter((n) => n.type === "fastqToBam");

  // No HLA nodes at all — nothing to validate (pure nf-core canvas or empty canvas)
  if (
    inputNodes.length === 0 &&
    hlaNodes.length === 0 &&
    resultsNodes.length === 0
  ) {
    return { valid: true, errors: [] };
  }

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
  if (resultsNodes.length !== 1) {
    errors.push(
      resultsNodes.length === 0
        ? "Add a Results node."
        : "Only one Results node is allowed."
    );
  }
  if (converterNodes.length > 1) {
    errors.push("Only one FASTQ → BAM converter is allowed.");
  }

  if (errors.length === 0) {
    const inputId = inputNodes[0].id;
    const hlaId = hlaNodes[0].id;
    const resultsId = resultsNodes[0].id;

    if (converterNodes.length === 1) {
      // Path: Input →(file-out→fastq-in)→ Converter →(bam-out→file-in)→ HLA
      const convId = converterNodes[0].id;

      const hasInputToConv = graph.edges.some(
        (e) =>
          e.source === inputId &&
          e.sourceHandle === "file-out" &&
          e.target === convId &&
          e.targetHandle === "fastq-in"
      );
      if (!hasInputToConv) {
        errors.push("Connect Input File → FASTQ→BAM converter.");
      }

      const hasConvToHla = graph.edges.some(
        (e) =>
          e.source === convId &&
          e.sourceHandle === "bam-out" &&
          e.target === hlaId &&
          e.targetHandle === "file-in"
      );
      if (!hasConvToHla) {
        errors.push("Connect FASTQ→BAM converter → HLA-HD Typing.");
      }
    } else {
      // Direct path: Input →(file-out→file-in)→ HLA
      const hasInputToHla = graph.edges.some(
        (e) =>
          e.source === inputId &&
          e.sourceHandle === "file-out" &&
          e.target === hlaId &&
          e.targetHandle === "file-in"
      );
      if (!hasInputToHla) {
        errors.push("Connect Input File → HLA-HD Typing.");
      }
    }

    const hasHlaToResults = graph.edges.some(
      (e) =>
        e.source === hlaId &&
        e.sourceHandle === "result-out" &&
        e.target === resultsId &&
        e.targetHandle === "result-in"
    );
    if (!hasHlaToResults) {
      errors.push("Connect HLA-HD Typing → Results.");
    }
  }

  return { valid: errors.length === 0, errors };
}
