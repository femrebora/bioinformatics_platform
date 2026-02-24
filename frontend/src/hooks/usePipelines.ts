import { useState, useCallback } from "react";
import {
  listPipelines,
  createPipeline,
  updatePipeline,
  deletePipeline,
} from "../api/pipelineClient";
import type { Pipeline, PipelineListItem, GraphData } from "../types/pipeline";

export function usePipelines() {
  const [pipelines, setPipelines] = useState<PipelineListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPipelines = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listPipelines();
      setPipelines(list);
    } catch {
      setError("Failed to load pipelines.");
    } finally {
      setLoading(false);
    }
  }, []);

  const savePipeline = useCallback(
    async (name: string, graph: GraphData, pipelineId: string | null): Promise<Pipeline> => {
      if (pipelineId) {
        return updatePipeline(pipelineId, { name, graph });
      }
      return createPipeline({ name, graph });
    },
    []
  );

  const removePipeline = useCallback(async (pipelineId: string): Promise<void> => {
    await deletePipeline(pipelineId);
    setPipelines((prev) => prev.filter((p) => p.pipeline_id !== pipelineId));
  }, []);

  return { pipelines, loading, error, loadPipelines, savePipeline, removePipeline };
}
