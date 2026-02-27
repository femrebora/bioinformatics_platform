# ── VPC: use default or supply your own subnet/SG IDs ─────────────────────
# For production, replace the data sources below with your VPC resources
# or add a full VPC module.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "batch" {
  name        = "${local.prefix}-batch"
  description = "Security group for Batch compute instances"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── Compute environment ────────────────────────────────────────────────────

resource "aws_batch_compute_environment" "main" {
  compute_environment_name = "${local.prefix}-compute"
  type                     = "MANAGED"
  service_role             = aws_iam_role.batch_service.arn

  compute_resources {
    type               = "SPOT"   # Change to "EC2" if you prefer on-demand
    allocation_strategy = "SPOT_CAPACITY_OPTIMIZED"
    min_vcpus          = var.batch_compute_min_vcpus
    max_vcpus          = var.batch_compute_max_vcpus
    instance_type      = var.batch_instance_types
    instance_role      = aws_iam_instance_profile.batch_instance.arn
    subnets            = data.aws_subnets.default.ids
    security_group_ids = [aws_security_group.batch.id]
    spot_iam_fleet_role = aws_iam_role.spot_fleet.arn
  }

  depends_on = [aws_iam_role_policy_attachment.batch_service]
}

# Instance profile for EC2 nodes in the compute environment
resource "aws_iam_instance_profile" "batch_instance" {
  name = "${local.prefix}-batch-instance-profile"
  role = aws_iam_role.batch_instance.name
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "batch_instance" {
  name               = "${local.prefix}-batch-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "batch_instance_container_service" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "batch_instance_s3" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"  # Tighten in production
}

# Spot fleet role — required for SPOT compute environments
data "aws_iam_policy_document" "spot_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["spotfleet.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "spot_fleet" {
  name               = "${local.prefix}-spot-fleet"
  assume_role_policy = data.aws_iam_policy_document.spot_assume.json
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  role       = aws_iam_role.spot_fleet.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

# ── Job queues ─────────────────────────────────────────────────────────────

resource "aws_batch_job_queue" "default" {
  name     = "${local.prefix}-default"
  state    = "ENABLED"
  priority = 10

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.main.arn
  }
}

# High-priority queue for interactive/foreground jobs
resource "aws_batch_job_queue" "high_priority" {
  name     = "${local.prefix}-high"
  state    = "ENABLED"
  priority = 100

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.main.arn
  }
}

# ── CloudWatch log group ────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "batch" {
  name              = "/aws/batch/${local.prefix}"
  retention_in_days = 30
}
