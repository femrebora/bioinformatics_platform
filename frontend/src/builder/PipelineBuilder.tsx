import { useRef, useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  Background,
  Controls,
  type Connection,
  type NodeTypes,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { InputFileNode } from "./nodes/InputFileNode";
import { HLATypingNode } from "./nodes/HLATypingNode";
import { ResultsNode } from "./nodes/ResultsNode";
import { FastqToBamNode } from "./nodes/FastqToBamNode";
import { NfCoreModuleNode } from "./nodes/NfCoreModuleNode";
import { NfCorePipelineNode } from "./nodes/NfCorePipelineNode";
import { NodePalette } from "./NodePalette";
import { PipelineToolbar } from "./PipelineToolbar";
import { validatePipeline, patternsOverlap } from "./validation";
import { usePipelines } from "../hooks/usePipelines";
import { getPipeline } from "../api/pipelineClient";
import { fetchPipelineModules } from "../api/nfcoreClient";
import { presignUpload, uploadFile } from "../api/client";
import type { GraphData } from "../types/pipeline";
import type { PresignResponse } from "../types/job";
import type { TierConfirmProps } from "../components/TierConfirm";
import type { NfCoreModule } from "../types/nfcore";

// ── Auto-wiring helpers (pure functions, outside component) ───────────────

type AutoEdge = { srcIdx: number; srcPort: string; tgtIdx: number; tgtPort: string };

/** DFS reachability check — returns true if 'to' can already reach 'from'. */
function dfsCycleCheck(adj: Map<number, Set<number>>, from: number, to: number): boolean {
  const visited = new Set<number>();
  const stack = [to];
  while (stack.length > 0) {
    const node = stack.pop()!;
    if (node === from) return true;
    if (visited.has(node)) continue;
    visited.add(node);
    for (const next of adj.get(node) ?? []) stack.push(next);
  }
  return false;
}

/** Normalise a port name to a stem for fuzzy matching (strip ch_ prefix etc.) */
function portStem(name: string): string {
  return name.toLowerCase().replace(/^ch_/, "").replace(/[^a-z0-9]/g, "");
}

/** Ports that carry ancillary data (versions, reference genomes, indices)
 *  rather than primary analysis results — skip them in auto-wiring. */
function isAncillaryPort(name: string): boolean {
  const n = name.toLowerCase();
  return (
    n.startsWith("versions") ||
    n === "index" ||
    n === "fasta" ||
    n === "fai" ||
    n === "dict" ||
    n === "gtf" ||
    n === "gff" ||
    n === "bed" ||
    n === "dbsnp" ||
    n === "vcf_tbi"
  );
}

/**
 * Greedy bipartite matching: for each (output port, input port) pair that
 * are compatible (pattern overlap OR matching port-name stem), assign the
 * most specific (fewest competing candidates) edges first, ensuring each
 * port is used at most once and no cycles form.
 */
function computeAutoEdges(modules: NfCoreModule[]): AutoEdge[] {
  const n = modules.length;
  const all: AutoEdge[] = [];

  for (let t = 0; t < n; t++) {
    for (const inP of modules[t].inputs ?? []) {
      if (isAncillaryPort(inP.name)) continue;
      for (let s = 0; s < n; s++) {
        if (s === t) continue;
        for (const outP of modules[s].outputs ?? []) {
          if (isAncillaryPort(outP.name)) continue;
          const stem = portStem(inP.name);
          const compatible =
            (inP.pattern && outP.pattern)
              ? patternsOverlap(outP.pattern, inP.pattern)
              : stem.length >= 2 && stem === portStem(outP.name); // name-based fallback
          if (compatible) {
            all.push({ srcIdx: s, srcPort: outP.name, tgtIdx: t, tgtPort: inP.name });
          }
        }
      }
    }
  }

  if (all.length === 0) return [];

  // Score = sum of competing candidates; lower = more specific = preferred
  const srcCount = new Map<string, number>();
  const tgtCount = new Map<string, number>();
  for (const c of all) {
    const sk = `${c.srcIdx}:${c.srcPort}`;
    const tk = `${c.tgtIdx}:${c.tgtPort}`;
    srcCount.set(sk, (srcCount.get(sk) ?? 0) + 1);
    tgtCount.set(tk, (tgtCount.get(tk) ?? 0) + 1);
  }

  const scored = all
    .map((c) => ({
      ...c,
      score:
        (srcCount.get(`${c.srcIdx}:${c.srcPort}`) ?? 99) +
        (tgtCount.get(`${c.tgtIdx}:${c.tgtPort}`) ?? 99),
    }))
    .sort((a, b) => a.score - b.score);

  const result: AutoEdge[] = [];
  const usedSrc = new Set<string>();
  const usedTgt = new Set<string>();
  const adj = new Map<number, Set<number>>();

  for (const c of scored) {
    const sk = `${c.srcIdx}:${c.srcPort}`;
    const tk = `${c.tgtIdx}:${c.tgtPort}`;
    if (usedSrc.has(sk) || usedTgt.has(tk)) continue;
    if (dfsCycleCheck(adj, c.srcIdx, c.tgtIdx)) continue;

    result.push(c);
    usedSrc.add(sk);
    usedTgt.add(tk);
    if (!adj.has(c.srcIdx)) adj.set(c.srcIdx, new Set());
    adj.get(c.srcIdx)!.add(c.tgtIdx);
  }

  return result;
}

/**
 * Topological level layout: modules are placed left-to-right by DAG depth.
 * Within each column, modules are stacked vertically.
 */
function computeLevelLayout(
  n: number,
  edges: Pick<AutoEdge, "srcIdx" | "tgtIdx">[],
  startX: number,
  startY: number
): { x: number; y: number }[] {
  const COL_GAP = 310;
  const ROW_GAP = 230;

  // No edges → spread modules in a grid (avoid a single tall column)
  if (edges.length === 0) {
    const COLS = Math.max(1, Math.ceil(Math.sqrt(n)));
    return Array.from({ length: n }, (_, i) => ({
      x: startX + (i % COLS) * COL_GAP,
      y: startY + Math.floor(i / COLS) * ROW_GAP,
    }));
  }

  const parents: number[][] = Array.from({ length: n }, () => []);
  for (const e of edges) parents[e.tgtIdx].push(e.srcIdx);

  const levels = new Array<number>(n).fill(-1);
  function getLevel(i: number, visiting = new Set<number>()): number {
    if (levels[i] >= 0) return levels[i];
    if (visiting.has(i)) { levels[i] = 0; return 0; }
    visiting.add(i);
    levels[i] =
      parents[i].length === 0
        ? 0
        : Math.max(...parents[i].map((p) => getLevel(p, new Set(visiting)))) + 1;
    return levels[i];
  }
  for (let i = 0; i < n; i++) getLevel(i);

  const maxLevel = Math.max(0, ...levels);
  const groups: number[][] = Array.from({ length: maxLevel + 1 }, () => []);
  for (let i = 0; i < n; i++) groups[levels[i]].push(i);

  const positions: { x: number; y: number }[] = new Array(n);
  for (let l = 0; l <= maxLevel; l++) {
    for (let r = 0; r < groups[l].length; r++) {
      positions[groups[l][r]] = {
        x: startX + l * COL_GAP,
        y: startY + r * ROW_GAP,
      };
    }
  }
  return positions;
}

// ──────────────────────────────────────────────────────────────────────────

const nodeTypes: NodeTypes = {
  inputFile: InputFileNode,
  fastqToBam: FastqToBamNode,
  hlaTyping: HLATypingNode,
  results: ResultsNode,
  nfcoreModule: NfCoreModuleNode,
  nfcorePipeline: NfCorePipelineNode,
};

let nodeCounter = 0;
function makeId(prefix: string) {
  return `${prefix}-${++nodeCounter}`;
}

const DEFAULT_NODES: Node[] = [
  {
    id: "input-1",
    type: "inputFile",
    position: { x: 100, y: 200 },
    data: { label: "Input File", fileType: "fastq" },
  },
  {
    id: "hlatyping-1",
    type: "hlaTyping",
    position: { x: 370, y: 200 },
    data: { label: "HLA-HD Typing", tier: "medium" },
  },
  {
    id: "results-1",
    type: "results",
    position: { x: 640, y: 200 },
    data: { label: "Results" },
  },
];

const DEFAULT_EDGES: Edge[] = [
  {
    id: "e1",
    source: "input-1",
    sourceHandle: "file-out",
    target: "hlatyping-1",
    targetHandle: "file-in",
  },
  {
    id: "e2",
    source: "hlatyping-1",
    sourceHandle: "result-out",
    target: "results-1",
    targetHandle: "result-in",
  },
];

interface PipelineBuilderProps {
  onRunRequested: (
    presign: PresignResponse,
    filename: string,
    fileType: string,
    pipelineId: string | null
  ) => void;
  confirmingState: null | { presign: PresignResponse; filename: string };
  TierConfirmComponent: React.ComponentType<TierConfirmProps>;
  onConfirm: (tier: import("../types/job").Tier, cost: number) => void;
  onCancelConfirm: () => void;
}

export function PipelineBuilder({
  onRunRequested,
  confirmingState,
  TierConfirmComponent,
  onConfirm,
  onCancelConfirm,
}: PipelineBuilderProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(DEFAULT_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(DEFAULT_EDGES);
  const [pipelineName, setPipelineName] = useState("My HLA Pipeline");
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const reactFlowWrapperRef = useRef<HTMLDivElement>(null);
  // Typed minimally to avoid ReactFlowInstance generic mismatch
  const reactFlowRef = useRef<{
    screenToFlowPosition: (pos: { x: number; y: number }) => { x: number; y: number };
  } | null>(null);

  // Stable ref so isValidConnection (a useCallback with no deps) can read
  // the current nodes list without being recreated on every render.
  const nodesRef = useRef(nodes);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);

  const { pipelines, loadPipelines, savePipeline, removePipeline } = usePipelines();

  useEffect(() => {
    loadPipelines();
  }, [loadPipelines]);

  // Build current graph from nodes/edges state
  function getCurrentGraph(): GraphData {
    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type ?? "",
        position: n.position,
        data: n.data as Record<string, unknown>,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        sourceHandle: e.sourceHandle ?? "",
        target: e.target,
        targetHandle: e.targetHandle ?? "",
      })),
    };
  }

  const graph = getCurrentGraph();
  const { valid, errors } = validatePipeline(graph);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const isValidConnection = useCallback((connection: Connection | Edge) => {
    const sh = connection.sourceHandle ?? "";
    const th = connection.targetHandle ?? "";

    // nf-core port-to-port: validate file format compatibility via pattern overlap
    if (sh.startsWith("nfc-out-") && th.startsWith("nfc-in-")) {
      const srcNode = nodesRef.current.find((n) => n.id === connection.source);
      const tgtNode = nodesRef.current.find((n) => n.id === connection.target);

      type Port = { name: string; pattern: string };
      const outName = sh.slice("nfc-out-".length);
      const inName  = th.slice("nfc-in-".length);

      const srcData = srcNode?.data as Record<string, unknown> | undefined;
      const tgtData = tgtNode?.data as Record<string, unknown> | undefined;
      const srcPort = ((srcData?.outputs ?? []) as Port[]).find(
        (p) => p.name === outName
      );
      const tgtPort = ((tgtData?.inputs ?? []) as Port[]).find(
        (p) => p.name === inName
      );

      // If both ports have patterns, require overlap; otherwise be permissive
      if (srcPort?.pattern && tgtPort?.pattern) {
        return patternsOverlap(srcPort.pattern, tgtPort.pattern);
      }
      return true;
    }

    // Other nf-core handle combinations (e.g. nfc-out → built-in, or
    // nfc-in from built-in source) — allow freely
    if (sh.startsWith("nfc-") || th.startsWith("nfc-")) return true;

    // Strict rules for built-in-only connections
    const validPairs = [
      { source: "file-out",   target: "file-in"   }, // Input → HLA (direct)
      { source: "file-out",   target: "fastq-in"  }, // Input → Converter
      { source: "bam-out",    target: "file-in"   }, // Converter → HLA
      { source: "result-out", target: "result-in" }, // HLA → Results
    ];
    return validPairs.some((p) => p.source === sh && p.target === th);
  }, []); // stable reference — reads current nodes via nodesRef

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const nodeType = e.dataTransfer.getData("nodeType");
    if (!nodeType || !reactFlowRef.current) return;

    const position = reactFlowRef.current.screenToFlowPosition({
      x: e.clientX,
      y: e.clientY,
    });

    const nodeDataStr = e.dataTransfer.getData("nodeData");
    const extraData = nodeDataStr ? JSON.parse(nodeDataStr) : {};

    const defaultData: Record<string, unknown> =
      nodeType === "nfcoreModule" || nodeType === "nfcorePipeline"
        ? extraData
        : nodeType === "inputFile"
        ? { label: "Input File", fileType: "fastq" }
        : nodeType === "fastqToBam"
        ? { label: "FASTQ → BAM" }
        : nodeType === "hlaTyping"
        ? { label: "HLA-HD Typing", tier: "medium" }
        : { label: "Results" };

    const prefix =
      nodeType === "nfcoreModule"
        ? "nfmod"
        : nodeType === "nfcorePipeline"
        ? "nfpipe"
        : nodeType === "inputFile"
        ? "input"
        : nodeType === "fastqToBam"
        ? "converter"
        : nodeType === "hlaTyping"
        ? "hlatyping"
        : "results";

    setNodes((nds) => [
      ...nds,
      { id: makeId(prefix), type: nodeType, position, data: defaultData },
    ]);
  }

  async function handleSave() {
    if (!pipelineName.trim()) return;
    setSaving(true);
    try {
      const saved = await savePipeline(pipelineName, getCurrentGraph(), activePipelineId);
      setActivePipelineId(saved.pipeline_id);
      await loadPipelines();
    } finally {
      setSaving(false);
    }
  }

  async function handleLoad(pipelineId: string) {
    const p = await getPipeline(pipelineId);
    setPipelineName(p.name);
    setActivePipelineId(p.pipeline_id);
    setNodes(
      p.graph.nodes.map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data,
      }))
    );
    setEdges(
      p.graph.edges.map((e) => ({
        id: e.id,
        source: e.source,
        sourceHandle: e.sourceHandle,
        target: e.target,
        targetHandle: e.targetHandle,
      }))
    );
  }

  function handleNew() {
    setPipelineName("New Pipeline");
    setActivePipelineId(null);
    setNodes([]);
    setEdges([]);
  }

  async function handleDelete() {
    if (!activePipelineId) return;
    await removePipeline(activePipelineId);
    handleNew();
  }

  async function handleExpandPipeline(pipelineId: string): Promise<void> {
    let mods: NfCoreModule[];
    try {
      mods = await fetchPipelineModules(pipelineId);
    } catch {
      return;
    }
    if (mods.length === 0) return;

    // Place below and aligned with the leftmost existing node
    const currentNodes = nodesRef.current;
    const startX = currentNodes.length > 0
      ? Math.min(...currentNodes.map((n) => n.position.x))
      : 100;
    const startY = currentNodes.length > 0
      ? Math.max(...currentNodes.map((n) => n.position.y)) + 260
      : 100;

    // 1. Compute which ports can be auto-wired (greedy, cycle-free)
    const autoEdges = computeAutoEdges(mods);

    // 2. Compute topological layout based on the edge DAG
    const positions = computeLevelLayout(mods.length, autoEdges, startX, startY);

    // 3. Generate stable IDs before building edges
    const nodeIds = mods.map(() => makeId("nfmod"));

    const newNodes: Node[] = mods.map((mod, i) => ({
      id: nodeIds[i],
      type: "nfcoreModule",
      position: positions[i],
      data: {
        label: mod.id,
        tool: mod.tool,
        subcommand: mod.subcommand,
        description: mod.description,
        category: mod.category,
        inputs: mod.inputs,
        outputs: mod.outputs,
      },
    }));

    const newEdges: Edge[] = autoEdges.map((ae) => ({
      id: `ae-${nodeIds[ae.srcIdx]}-${ae.srcPort}-${nodeIds[ae.tgtIdx]}-${ae.tgtPort}`,
      source: nodeIds[ae.srcIdx],
      sourceHandle: `nfc-out-${ae.srcPort}`,
      target: nodeIds[ae.tgtIdx],
      targetHandle: `nfc-in-${ae.tgtPort}`,
    }));

    setNodes((prev) => [...prev, ...newNodes]);
    setEdges((prev) => [...prev, ...newEdges]);
  }

  function handleRun() {
    if (!valid) return;
    fileInputRef.current?.click();
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    const inputNode = nodes.find((n) => n.type === "inputFile");
    const fileType = (inputNode?.data as { fileType?: string })?.fileType ?? "fastq";

    try {
      const presign = await presignUpload(file.name, file.size);
      await uploadFile(presign.upload_url, file);
      onRunRequested(presign, file.name, fileType, activePipelineId);
    } catch {
      // upload errors surface via App error phase
    }
  }

  return (
    <div style={styles.root}>
      <div style={styles.layout}>
        <NodePalette onExpandPipeline={handleExpandPipeline} />
        <div style={styles.canvasArea}>
          <PipelineToolbar
            pipelineName={pipelineName}
            onNameChange={setPipelineName}
            savedPipelines={pipelines}
            activePipelineId={activePipelineId}
            onSave={handleSave}
            onLoad={handleLoad}
            onNew={handleNew}
            onDelete={handleDelete}
            onRun={handleRun}
            canRun={valid}
            saving={saving}
            validationErrors={errors}
          />
          <div ref={reactFlowWrapperRef} style={styles.canvas}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              isValidConnection={isValidConnection}
              nodeTypes={nodeTypes}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onInit={(instance) => {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                reactFlowRef.current = instance as any;
              }}
              fitView
            >
              <Background />
              <Controls />
            </ReactFlow>
          </div>
        </div>
      </div>

      {confirmingState && (
        <div style={styles.overlay}>
          <TierConfirmComponent
            presign={confirmingState.presign}
            filename={confirmingState.filename}
            onConfirm={onConfirm}
            onCancel={onCancelConfirm}
          />
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".fastq,.fastq.gz,.bam"
        style={{ display: "none" }}
        onChange={handleFileSelected}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  root: {
    position: "relative",
    height: "calc(100vh - 60px)",
    display: "flex",
    flexDirection: "column",
  },
  layout: {
    flex: 1,
    display: "flex",
    overflow: "hidden",
  },
  canvasArea: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  canvas: {
    flex: 1,
    overflow: "hidden",
  },
  overlay: {
    position: "absolute",
    inset: 0,
    background: "rgba(0,0,0,0.4)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 50,
  },
};
