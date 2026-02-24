import axios from "axios";
import type { Pipeline, PipelineListItem, PipelineCreate, PipelineUpdate } from "../types/pipeline";

const http = axios.create({ baseURL: "/api/v1" });

export async function createPipeline(body: PipelineCreate): Promise<Pipeline> {
  const { data } = await http.post<Pipeline>("/pipelines", body);
  return data;
}

export async function listPipelines(): Promise<PipelineListItem[]> {
  const { data } = await http.get<PipelineListItem[]>("/pipelines");
  return data;
}

export async function getPipeline(pipelineId: string): Promise<Pipeline> {
  const { data } = await http.get<Pipeline>(`/pipelines/${pipelineId}`);
  return data;
}

export async function updatePipeline(
  pipelineId: string,
  body: PipelineUpdate
): Promise<Pipeline> {
  const { data } = await http.put<Pipeline>(`/pipelines/${pipelineId}`, body);
  return data;
}

export async function deletePipeline(pipelineId: string): Promise<void> {
  await http.delete(`/pipelines/${pipelineId}`);
}
