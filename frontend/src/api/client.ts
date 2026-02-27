import axios from "axios";
import type { Job, JobListItem, PresignResponse, EstimateResponse, CheckoutResponse, Tier } from "../types/job";
import { TOKEN_KEY } from "./authClient";

const http = axios.create({ baseURL: "/api/v1" });

// Attach JWT token to every request if available
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

export async function fetchEstimate(
  pipelineId: string | null,
  nSamples: number,
  fileSizeBytes?: number,
): Promise<EstimateResponse> {
  const params: Record<string, string | number> = { n_samples: nSamples };
  if (pipelineId) params.pipeline_id = pipelineId;
  if (fileSizeBytes) params.file_size_bytes = fileSizeBytes;
  const { data } = await http.get<EstimateResponse>("/uploads/estimate", { params });
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
  pipelineId?: string | null,
  storageKeyR2?: string | null,
  workflowConfig?: unknown | null,
  jobName?: string | null,
): Promise<Job> {
  const { data } = await http.post<Job>("/jobs", {
    storage_key: storageKey,
    file_type: fileType,
    tier,
    estimated_cost_usd: estimatedCostUsd,
    ...(pipelineId ? { pipeline_id: pipelineId } : {}),
    ...(storageKeyR2 ? { storage_key_r2: storageKeyR2 } : {}),
    ...(workflowConfig ? { workflow_config: workflowConfig } : {}),
    ...(jobName ? { job_name: jobName } : {}),
  });
  return data;
}

export async function getJob(jobId: string): Promise<Job> {
  const { data } = await http.get<Job>(`/jobs/${jobId}`);
  return data;
}

export async function listJobs(): Promise<JobListItem[]> {
  const { data } = await http.get<JobListItem[]>("/jobs");
  return data;
}

export async function createCheckoutSession(
  storageKey: string,
  fileType: string,
  tier: Tier,
  estimatedCostUsd: number,
  pipelineId: string | null,
  nSamples: number,
  storageKeyR2?: string | null,
  workflowConfig?: unknown | null,
  jobName?: string | null,
): Promise<CheckoutResponse> {
  const { data } = await http.post<CheckoutResponse>("/payments/checkout", {
    storage_key: storageKey,
    file_type: fileType,
    tier,
    estimated_cost_usd: estimatedCostUsd,
    pipeline_id: pipelineId,
    n_samples: nSamples,
    ...(storageKeyR2 ? { storage_key_r2: storageKeyR2 } : {}),
    ...(workflowConfig ? { workflow_config: workflowConfig } : {}),
    ...(jobName ? { job_name: jobName } : {}),
  });
  return data;
}

export async function getSessionJob(sessionId: string): Promise<{ job_id: string | null }> {
  const { data } = await http.get<{ job_id: string | null }>(`/payments/session/${sessionId}`);
  return data;
}

export async function cancelJob(jobId: string): Promise<void> {
  await http.delete(`/jobs/${jobId}`);
}

export async function getDownloadUrl(jobId: string, path: string): Promise<string> {
  const { data } = await http.get<{ url: string }>(`/jobs/${jobId}/download`, {
    params: { path },
  });
  return data.url;
}

export async function retryJob(jobId: string): Promise<Job> {
  const { data } = await http.post<Job>(`/jobs/${jobId}/retry`);
  return data;
}

export interface JobLogsResponse {
  lines: string[];
  next_offset: number;
  done: boolean;
}

export async function getJobLogs(
  jobId: string,
  offset: number = 0,
): Promise<JobLogsResponse> {
  const { data } = await http.get<JobLogsResponse>(`/jobs/${jobId}/logs`, {
    params: { offset },
  });
  return data;
}

export interface VcfPageResponse {
  variants: import("../types/job").VcfVariant[];
  total: number;
  offset: number;
  limit: number;
  next_offset: number | null;
  chroms: string[];
}

export async function getVcfPage(
  jobId: string,
  offset = 0,
  limit = 100,
  chrom = "",
  filterPass = false,
): Promise<VcfPageResponse> {
  const { data } = await http.get<VcfPageResponse>(`/jobs/${jobId}/vcf`, {
    params: { offset, limit, chrom, filter_pass: filterPass },
  });
  return data;
}

/** Return completed jobs for the dataset library in InputFileNode. */
export async function getCompletedJobs(): Promise<import("../types/job").JobListItem[]> {
  const { data } = await http.get<import("../types/job").JobListItem[]>("/jobs");
  return data.filter((j) => j.status === "completed");
}
