import axios from "axios";
import type { Job, PresignResponse, Tier } from "../types/job";

const http = axios.create({ baseURL: "/api/v1" });

export async function presignUpload(
  filename: string,
  fileSizeBytes: number
): Promise<PresignResponse> {
  const { data } = await http.post<PresignResponse>("/uploads/presign", {
    filename,
    file_size_bytes: fileSizeBytes,
  });
  return data;
}

export async function uploadFile(uploadUrl: string, file: File): Promise<void> {
  await axios.put(uploadUrl, file, {
    headers: { "Content-Type": "application/octet-stream" },
  });
}

export async function createJob(
  storageKey: string,
  fileType: string,
  tier: Tier,
  estimatedCostUsd: number,
  pipelineId?: string | null
): Promise<Job> {
  const { data } = await http.post<Job>("/jobs", {
    storage_key: storageKey,
    file_type: fileType,
    tier,
    estimated_cost_usd: estimatedCostUsd,
    ...(pipelineId ? { pipeline_id: pipelineId } : {}),
  });
  return data;
}

export async function getJob(jobId: string): Promise<Job> {
  const { data } = await http.get<Job>(`/jobs/${jobId}`);
  return data;
}
