terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment to store state remotely in S3 (recommended for teams):
  # backend "s3" {
  #   bucket = "my-terraform-state-bucket"
  #   key    = "bioplatform/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  prefix      = "${var.project}-${var.environment}"
  bucket_name = var.s3_bucket_name != "" ? var.s3_bucket_name : "${local.prefix}-uploads"
}
