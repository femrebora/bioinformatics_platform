variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Short project name used as a prefix on all resource names"
  type        = string
  default     = "bioplatform"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "prod"
}

# ── S3 ────────────────────────────────────────────────────────────────────

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for uploads and pipeline results"
  type        = string
  # Override with: terraform apply -var 's3_bucket_name=my-unique-bucket-name'
  default     = ""
}

# ── AWS Batch ─────────────────────────────────────────────────────────────

variable "batch_compute_min_vcpus" {
  description = "Minimum vCPUs kept warm in the Batch managed compute environment (0 = scale-to-zero)"
  type        = number
  default     = 0
}

variable "batch_compute_max_vcpus" {
  description = "Maximum vCPUs the Batch compute environment may scale to"
  type        = number
  default     = 256
}

variable "batch_instance_types" {
  description = "EC2 instance types allowed in the Batch compute environment"
  type        = list(string)
  default     = ["c5", "m5", "r5"]
}

# ── ECR ───────────────────────────────────────────────────────────────────

variable "ecr_image_tag_mutability" {
  description = "Image tag mutability for the ECR repository (MUTABLE | IMMUTABLE)"
  type        = string
  default     = "MUTABLE"
}
