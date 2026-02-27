# ── Outputs ─────────────────────────────────────────────────────────────────
# Copy these values into your .env or CI/CD secrets.

output "s3_bucket_name" {
  description = "Name of the S3 uploads/results bucket"
  value       = aws_s3_bucket.uploads.id
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "backend_access_key_id" {
  description = "AWS Access Key ID for the backend application user"
  value       = aws_iam_access_key.backend.id
  sensitive   = true
}

output "backend_secret_access_key" {
  description = "AWS Secret Access Key for the backend application user"
  value       = aws_iam_access_key.backend.secret
  sensitive   = true
}

output "batch_job_queue" {
  description = "Default AWS Batch job queue ARN"
  value       = aws_batch_job_queue.default.arn
}

output "batch_job_queue_high_priority" {
  description = "High-priority AWS Batch job queue ARN"
  value       = aws_batch_job_queue.high_priority.arn
}

output "batch_job_role_arn" {
  description = "IAM role ARN assumed by each Batch job container (BATCH_JOB_ROLE_ARN)"
  value       = aws_iam_role.batch_job.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL for the tools image (BIOSCRIPT_DOCKER_IMAGE)"
  value       = "${aws_ecr_repository.tools.repository_url}:latest"
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for Batch job logs"
  value       = aws_cloudwatch_log_group.batch.name
}
