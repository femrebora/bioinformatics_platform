import type { Node, Edge } from "@xyflow/react";

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

export interface PipelineTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  tags: string[];
  build: () => { nodes: Node[]; edges: Edge[] };
}

// ── HLA Typing ────────────────────────────────────────────────────────────

const HLA_TYPING: PipelineTemplate = {
  id: "hla-typing",
  name: "HLA Typing",
  description: "Run HLA-HD to type Class I and II alleles from BAM or FASTQ input.",
  icon: "🧬",
  tags: ["HLA", "Immunology", "Typing"],
  build: () => {
    const inputId   = uid("input");
    const hlaId     = uid("hlatyping");
    const resultsId = uid("results");
    return {
      nodes: [
        { id: inputId,   type: "inputFile", position: { x: 80,  y: 200 }, data: { label: "Input File",    fileType: "bam"    } },
        { id: hlaId,     type: "hlaTyping", position: { x: 360, y: 200 }, data: { label: "HLA-HD Typing", tier: "medium"    } },
        { id: resultsId, type: "results",   position: { x: 640, y: 200 }, data: { label: "Results"                          } },
      ],
      edges: [
        { id: uid("e"), source: inputId,   sourceHandle: "file-out",   target: hlaId,     targetHandle: "file-in"   },
        { id: uid("e"), source: hlaId,     sourceHandle: "result-out", target: resultsId, targetHandle: "result-in" },
      ],
    };
  },
};

// ── nf-core helper ────────────────────────────────────────────────────────

interface NfcoreTemplateOpts {
  id: string;
  name: string;
  description: string;
  icon: string;
  tags: string[];
  pipelineId: string;
  pipelineLabel: string;
  pipelineDescription: string;
  inputFileType: string;
}

function nfcoreTemplate(opts: NfcoreTemplateOpts): PipelineTemplate {
  return {
    id: opts.id,
    name: opts.name,
    description: opts.description,
    icon: opts.icon,
    tags: opts.tags,
    build: () => {
      const inputId   = uid("input");
      const pipeId    = uid("nfpipe");
      const resultsId = uid("results");
      return {
        nodes: [
          {
            id: inputId, type: "inputFile", position: { x: 80, y: 200 },
            data: { label: "Input File", fileType: opts.inputFileType },
          },
          {
            id: pipeId, type: "nfcorePipeline", position: { x: 380, y: 200 },
            data: {
              label: opts.pipelineLabel,
              pipelineId: opts.pipelineId,
              description: opts.pipelineDescription,
              stars: 0,
            },
          },
          {
            id: resultsId, type: "results", position: { x: 720, y: 200 },
            data: { label: "Results" },
          },
        ],
        edges: [
          { id: uid("e"), source: inputId, sourceHandle: "file-out",       target: pipeId,    targetHandle: "nfc-in-data"    },
          { id: uid("e"), source: pipeId,  sourceHandle: "nfc-out-results", target: resultsId, targetHandle: "result-in"      },
        ],
      };
    },
  };
}

// ── Templates ─────────────────────────────────────────────────────────────

export const PIPELINE_TEMPLATES: PipelineTemplate[] = [
  HLA_TYPING,

  nfcoreTemplate({
    id: "rnaseq", name: "RNA-seq", icon: "🔬",
    description: "Quantify gene expression from RNA-seq reads using nf-core/rnaseq.",
    tags: ["RNA-seq", "Expression", "nf-core"],
    pipelineId: "rnaseq", pipelineLabel: "nf-core/rnaseq",
    pipelineDescription: "RNA sequencing analysis pipeline for expression quantification.",
    inputFileType: "fastq",
  }),

  nfcoreTemplate({
    id: "sarek", name: "Variant Calling (WGS)", icon: "🔍",
    description: "Germline and somatic variant calling from WGS/WES data using nf-core/sarek.",
    tags: ["Variant Calling", "WGS", "Sarek", "nf-core"],
    pipelineId: "sarek", pipelineLabel: "nf-core/sarek",
    pipelineDescription: "Germline and somatic variant calling from WGS/WES data.",
    inputFileType: "fastq",
  }),

  nfcoreTemplate({
    id: "atacseq", name: "ATAC-seq", icon: "🧫",
    description: "Chromatin accessibility profiling using nf-core/atacseq.",
    tags: ["ATAC-seq", "Chromatin", "Epigenomics", "nf-core"],
    pipelineId: "atacseq", pipelineLabel: "nf-core/atacseq",
    pipelineDescription: "ATAC-seq peak calling and differential accessibility analysis.",
    inputFileType: "fastq",
  }),

  nfcoreTemplate({
    id: "methylseq", name: "Methylation (Bisulfite-seq)", icon: "🧪",
    description: "DNA methylation analysis from bisulfite sequencing using nf-core/methylseq.",
    tags: ["Methylation", "Bisulfite", "Epigenomics", "nf-core"],
    pipelineId: "methylseq", pipelineLabel: "nf-core/methylseq",
    pipelineDescription: "Bisulfite-sequencing alignment and methylation calling.",
    inputFileType: "fastq",
  }),

  nfcoreTemplate({
    id: "ampliseq", name: "Amplicon Sequencing", icon: "🦠",
    description: "16S/ITS amplicon sequencing for microbiome studies via nf-core/ampliseq.",
    tags: ["Amplicon", "Microbiome", "16S", "nf-core"],
    pipelineId: "ampliseq", pipelineLabel: "nf-core/ampliseq",
    pipelineDescription: "Amplicon sequencing analysis for microbiome and metagenomics.",
    inputFileType: "fastq",
  }),

  nfcoreTemplate({
    id: "chipseq", name: "ChIP-seq", icon: "🧲",
    description: "ChIP-seq peak calling and differential binding analysis via nf-core/chipseq.",
    tags: ["ChIP-seq", "Epigenomics", "nf-core"],
    pipelineId: "chipseq", pipelineLabel: "nf-core/chipseq",
    pipelineDescription: "ChIP-seq peak calling and differential binding analysis.",
    inputFileType: "fastq",
  }),

  nfcoreTemplate({
    id: "fetchngs", name: "Fetch SRA / ENA Data", icon: "⬇",
    description: "Download public sequencing data from SRA/ENA/DDBJ using nf-core/fetchngs.",
    tags: ["SRA", "Download", "ENA", "nf-core"],
    pipelineId: "fetchngs", pipelineLabel: "nf-core/fetchngs",
    pipelineDescription: "Fetch metadata and raw reads from SRA, ENA, DDBJ and GSA.",
    inputFileType: "fastq",
  }),
];
