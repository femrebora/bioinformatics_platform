export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Pipeline {
  pipeline_id: string;
  name: string;
  graph: GraphData;
  created_at: string;
  updated_at: string;
}

export interface PipelineListItem {
  pipeline_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface PipelineCreate {
  name: string;
  graph: GraphData;
}

export interface PipelineUpdate {
  name?: string;
  graph?: GraphData;
}
