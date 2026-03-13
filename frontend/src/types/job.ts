export type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type JobStage = "ec2_starting" | "pipeline_running" | "snakemake_running" | "done" | null;
export type Tier = "small" | "medium" | "large";

export interface VcfVariant {
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  qual?: string;
  filter?: string;
}

export interface ResultFile {
  name: string;
  path: string;
  size_bytes?: number;
  url?: string;
  mime_type?: string;
  description?: string;
}

export interface Provenance {
  pipeline?: string;
  pipeline_version?: string;
  genome?: string;
  params?: Record<string, unknown>;
  n_samples?: number;
  completed_at: string;
  instance_type: string;
  runtime_seconds: number;
}

export interface JobResult {
  type?: "table" | "vcf" | "html_report" | "text" | "files";
  _mock?: boolean;
  provenance?: Provenance;
  // table
  columns?: string[];
  rows?: Record<string, string | number>[];
  // vcf
  variants?: VcfVariant[];
  // html_report
  html?: string;
  // text
  content?: string;
  // files
  files?: ResultFile[];
  // always present
  instance_type: string;
  runtime_seconds: number;
}

export interface JobListItem {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  tier: Tier;
  estimated_cost_usd: number;
  pipeline_id?: string | null;
  job_name?: string | null;
  created_at: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  tier: Tier;
  estimated_cost_usd: number;
  pipeline_id?: string | null;
  job_name?: string | null;
  created_at?: string;
  result: JobResult | null;
  error: string | null;
}

export interface EstimateResponse {
  tier: Tier;
  instance_type: string;
  estimated_cost_usd: number;
  rationale: string;
  estimated_hours: number;
  pipeline_description: string;
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface CheckoutRequest {
  storage_key: string;
  file_type: string;
  tier: Tier;
  pipeline_id: string | null;
  estimated_cost_usd: number;
  n_samples: number;
  storage_key_r2?: string | null;
  workflow_config?: unknown | null;
}

export interface PresignResponse {
  upload_url: string;
  storage_key: string;
  recommended_tier: Tier;
  estimated_cost_usd: number;
  tier_rationale: string;
}
