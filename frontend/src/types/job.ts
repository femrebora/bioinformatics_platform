export type JobStatus = "pending" | "running" | "completed" | "failed";
export type JobStage = "ec2_starting" | "hla_running" | "pipeline_running" | "done" | null;
export type Tier = "small" | "medium" | "large";

export interface HLAAllele {
  gene: string;
  allele_1: string;
  allele_2: string;
}

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
}

/**
 * Flexible result payload. The `type` field is the discriminator.
 * Absent or "hla_alleles" → HLA allele table (legacy + current backend).
 * Other types are placeholders for future pipeline outputs.
 */
export interface JobResult {
  /** Absent for legacy HLA results; set by future pipeline runners. */
  type?: "hla_alleles" | "table" | "vcf" | "html_report" | "text" | "files";
  // hla_alleles / legacy
  hla_alleles?: HLAAllele[];
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
  created_at: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  tier: Tier;
  estimated_cost_usd: number;
  pipeline_id?: string | null;
  created_at?: string;
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
