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

export const PIPELINE_TEMPLATES: PipelineTemplate[] = [SAREK_TEMPLATE];
