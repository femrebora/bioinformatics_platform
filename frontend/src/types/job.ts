export type JobStatus = "pending" | "running" | "completed" | "failed";
export type JobStage = "ec2_starting" | "hla_running" | "done" | null;
export type Tier = "small" | "medium" | "large";

export interface HLAAllele {
  gene: string;
  allele_1: string;
  allele_2: string;
}

export interface JobResult {
  hla_alleles: HLAAllele[];
  instance_type: string;
  runtime_seconds: number;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  tier: Tier;
  estimated_cost_usd: number;
  result: JobResult | null;
  error: string | null;
}

export interface PresignResponse {
  upload_url: string;
  storage_key: string;
  recommended_tier: Tier;
  estimated_cost_usd: number;
  tier_rationale: string;
}
