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

// ── Active templates (MVP: sarek only) ────────────────────────────────────

const SAREK_TEMPLATE = nfcoreTemplate({
  id: "sarek", name: "Variant Calling (WGS)", icon: "🔍",
  description: "Germline and somatic variant calling from WGS/WES data using nf-core/sarek.",
  tags: ["Variant Calling", "WGS", "Sarek", "nf-core"],
  pipelineId: "sarek", pipelineLabel: "nf-core/sarek",
  pipelineDescription: "Germline and somatic variant calling from WGS/WES data.",
  inputFileType: "fastq",
});

const ASSESSMENT_TEMPLATE: PipelineTemplate = {
  id: "sarek-assessment",
  name: "Variant Calling + Assessment",
  description: "Run nf-core/sarek for variant calling, then annotate variants via ClinVar, CancerHotspots, and dbSNP. Run sarek first, then select the completed job in the Assessment node.",
  icon: "🔬",
  tags: ["Variant Calling", "Assessment", "ClinVar", "Cancer"],
  build: () => {
    const inputId    = uid("input");
    const pipeId     = uid("nfpipe");
    const assessId   = uid("assess");
    const resultsId  = uid("results");
    return {
      nodes: [
        {
          id: inputId, type: "inputFile", position: { x: 60, y: 200 },
          data: { label: "Input File", fileType: "fastq" },
        },
        {
          id: pipeId, type: "nfcorePipeline", position: { x: 340, y: 200 },
          data: { label: "nf-core/sarek", pipelineId: "sarek", description: "Germline and somatic variant calling.", stars: 0 },
        },
        {
          id: assessId, type: "assessment", position: { x: 640, y: 200 },
          data: { label: "Mutation Assessment", sourceJobId: "" },
        },
        {
          id: resultsId, type: "results", position: { x: 920, y: 200 },
          data: { label: "Results" },
        },
      ],
      edges: [
        { id: uid("e"), source: inputId,  sourceHandle: "file-out",        target: pipeId,    targetHandle: "nfc-in-data"    },
        { id: uid("e"), source: pipeId,   sourceHandle: "nfc-out-results",  target: assessId,  targetHandle: "assessment-in"  },
        { id: uid("e"), source: assessId, sourceHandle: "assessment-out",   target: resultsId, targetHandle: "result-in"      },
      ],
    };
  },
};

export const PIPELINE_TEMPLATES: PipelineTemplate[] = [SAREK_TEMPLATE, ASSESSMENT_TEMPLATE];
