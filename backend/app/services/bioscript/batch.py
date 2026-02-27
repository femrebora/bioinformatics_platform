"""
BioScript runner — executes user bash scripts on AWS Batch using
the bioplatform/tools Docker image with pre-installed bioinformatics tools.

The user provides a bash script in workflow_config.script.  The runner:
1. Uploads the script to S3.
2. Submits a single AWS Batch job that downloads the input file, sources
   bio_helpers.sh, and runs the user script.
3. Polls until the Batch job completes.
4. Scans the S3 output prefix and returns a result dict.
"""
import json
import logging
import time
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.services.batch_tracker import set_batch_job_id, delete_batch_job_id
from app.services.bioscript.base import BioScriptRunner

logger = logging.getLogger(__name__)

_MAX_SUBMIT_RETRIES = 5


def _with_backoff(fn, *args, **kwargs):
    """Call fn, retrying with exponential backoff on AWS throttling errors."""
    for attempt in range(_MAX_SUBMIT_RETRIES):
        try:
            return fn(*args, **kwargs)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in (
                "ThrottlingException",
                "TooManyRequestsException",
                "RequestLimitExceeded",
                "ServiceUnavailableException",
                "InternalFailure",
                "InternalServerError",
            ) and attempt < _MAX_SUBMIT_RETRIES - 1:
                wait = 2 ** attempt  # 1, 2, 4, 8 s
                logger.warning(
                    "[bioscript/batch] throttled (attempt %d/%d), retrying in %ds",
                    attempt + 1,
                    _MAX_SUBMIT_RETRIES,
                    wait,
                )
                time.sleep(wait)
            else:
                raise


# File extensions to surface in results
_KEEP_EXTS = {
    "html", "txt", "csv", "tsv", "json",
    "gz", "bam", "bai", "vcf", "bed",
    "bigwig", "bw", "log", "sh",
}

_MIME_MAP = {
    "html": "text/html",
    "txt":  "text/plain",
    "csv":  "text/csv",
    "tsv":  "text/tab-separated-values",
    "json": "application/json",
    "gz":   "application/gzip",
    "bam":  "application/octet-stream",
    "bai":  "application/octet-stream",
    "vcf":  "text/plain",
    "bed":  "text/plain",
    "log":  "text/plain",
    "sh":   "text/plain",
}

_DEFAULT_SCRIPT = """\
#!/usr/bin/env bash
# Default BioScript — QC + alignment
. /usr/local/lib/bio_helpers.sh

INPUT_FILE="$INPUT_FILE"
OUTPUT_DIR="$OUTPUT_DIR"

bioplatform_qc "$INPUT_FILE" "$OUTPUT_DIR/qc"
echo "QC complete" > "$OUTPUT_DIR/done.txt"
"""


def _s3():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def _batch():
    return boto3.client(
        "batch",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def _upload_script(script: str, job_id: str) -> str:
    """Upload the bash script to S3 and return the S3 URI."""
    key = f"bioscript-jobs/{job_id}/script.sh"
    _s3().put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=script.encode(),
        ContentType="text/plain",
    )
    return f"s3://{settings.S3_BUCKET}/{key}"


def _collect_results(output_prefix: str, runtime: int) -> dict:
    paginator = _s3().get_paginator("list_objects_v2")
    files = []
    for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=output_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            name = key.split("/")[-1]
            if not name or name.endswith("/"):
                continue
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in _KEEP_EXTS:
                continue
            files.append({
                "name":       name,
                "path":       f"s3://{settings.S3_BUCKET}/{key}",
                "size_bytes": obj["Size"],
                "mime_type":  _MIME_MAP.get(ext, "application/octet-stream"),
                "description": "",
            })
    return {
        "type":            "files",
        "files":           files,
        "instance_type":   settings.BIOSCRIPT_DOCKER_IMAGE.split(":")[0].split("/")[-1],
        "runtime_seconds": runtime,
    }


class AWSBatchBioScriptRunner(BioScriptRunner):
    """Runs user bash scripts on AWS Batch using the bioplatform/tools image."""

    def run(
        self,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        workflow_config: Optional[dict[str, Any]] = None,
    ) -> dict:
        start = time.time()

        script = (workflow_config or {}).get("script") or _DEFAULT_SCRIPT
        extra_env = (workflow_config or {}).get("env") or {}

        input_s3  = f"s3://{settings.S3_BUCKET}/{storage_key}"
        output_s3 = f"s3://{settings.S3_BUCKET}/bioscript-output/{job_id}"

        script_s3 = _upload_script(script, job_id)
        batch_queue = settings.SNAKEMAKE_BATCH_QUEUE or settings.BATCH_JOB_QUEUE

        # The entrypoint downloads the script, sources helpers, and runs it
        command = [
            "/bin/bash", "-c",
            (
                f"aws s3 cp '{script_s3}' /tmp/user_script.sh && "
                "chmod +x /tmp/user_script.sh && "
                ". /usr/local/lib/bio_helpers.sh && "
                "/tmp/user_script.sh"
            ),
        ]

        env_vars = [
            {"name": "INPUT_FILE",  "value": input_s3},
            {"name": "OUTPUT_DIR",  "value": output_s3},
            {"name": "JOB_ID",      "value": job_id},
            {"name": "AWS_REGION",  "value": settings.AWS_REGION},
        ]
        for k, v in extra_env.items():
            env_vars.append({"name": k, "value": str(v)})

        job_def = {
            "type": "container",
            "containerProperties": {
                "image":      settings.BIOSCRIPT_DOCKER_IMAGE,
                "command":    command,
                "environment": env_vars,
                "jobRoleArn": settings.BATCH_JOB_ROLE_ARN,
                "resourceRequirements": [
                    {"type": "VCPU",   "value": "4"},
                    {"type": "MEMORY", "value": "8192"},
                ],
            },
        }

        logger.info("[bioscript/batch] registering job definition for job=%s", job_id)
        batch = _batch()
        jd_arn: str | None = None
        batch_job_id: str | None = None
        try:
            try:
                reg = _with_backoff(
                    batch.register_job_definition,
                    jobDefinitionName=f"bioscript-{job_id[:8]}",
                    **job_def,
                )
            except ClientError as exc:
                raise RuntimeError(
                    f"[bioscript] register_job_definition failed for job {job_id}: "
                    f"{exc.response['Error']['Code']} — {exc.response['Error']['Message']}"
                ) from exc
            jd_arn = reg["jobDefinitionArn"]

            logger.info("[bioscript/batch] submitting Batch job")
            try:
                resp = _with_backoff(
                    batch.submit_job,
                    jobName=f"bioscript-{job_id[:8]}",
                    jobQueue=batch_queue,
                    jobDefinition=jd_arn,
                )
            except ClientError as exc:
                raise RuntimeError(
                    f"[bioscript] submit_job failed for job {job_id}: "
                    f"{exc.response['Error']['Code']} — {exc.response['Error']['Message']}"
                ) from exc
            batch_job_id = resp["jobId"]
            logger.info("[bioscript/batch] submitted Batch job=%s", batch_job_id)
            if job_id:
                try:
                    set_batch_job_id(job_id, batch_job_id)
                except Exception as redis_exc:
                    # Non-fatal: the job is already running on Batch.  The cancel
                    # endpoint won't be able to terminate it, but the job itself
                    # will still complete and results will be collected.
                    logger.warning(
                        "[bioscript/batch] could not store batch tracking key "
                        "for job %s: %s",
                        job_id,
                        redis_exc,
                    )

            # Poll until the Batch job finishes (up to 2 hours)
            deadline = time.time() + 7200
            succeeded = False
            while time.time() < deadline:
                time.sleep(15)
                try:
                    desc = batch.describe_jobs(jobs=[batch_job_id])
                    job_info = desc["jobs"][0]
                except ClientError as poll_exc:
                    logger.warning(
                        "[bioscript/batch] transient error polling %s: %s — retrying",
                        batch_job_id,
                        poll_exc,
                    )
                    continue
                status = job_info["status"]
                logger.info(
                    "[bioscript/batch] Batch job %s status=%s", batch_job_id, status
                )
                if status == "SUCCEEDED":
                    succeeded = True
                    break
                if status == "FAILED":
                    reason = job_info.get("statusReason", "unknown")
                    raise RuntimeError(
                        f"AWS Batch job {batch_job_id} FAILED: {reason}"
                    )

            if not succeeded:
                raise TimeoutError(
                    f"AWS Batch job {batch_job_id} did not complete within 2 hours "
                    f"(platform job={job_id})"
                )

        finally:
            # Always clean up — even on failure — to avoid leaking job definitions
            # and stale cancel-tracking keys.
            if jd_arn:
                try:
                    batch.deregister_job_definition(jobDefinition=jd_arn)
                except Exception:
                    pass
            if job_id:
                try:
                    delete_batch_job_id(job_id)
                except Exception:
                    pass

        runtime = int(time.time() - start)
        output_prefix = f"bioscript-output/{job_id}"
        logger.info("[bioscript/batch] finished in %ds", runtime)
        try:
            return _collect_results(output_prefix, runtime)
        except ClientError as exc:
            logger.error(
                "[bioscript/batch] S3 listing failed after job completion "
                "(results exist but cannot be listed): %s",
                exc,
            )
            return {
                "type": "files",
                "files": [],
                "instance_type": settings.BIOSCRIPT_DOCKER_IMAGE.split(":")[0].split("/")[-1],
                "runtime_seconds": runtime,
                "warning": (
                    f"Job completed but result listing failed: "
                    f"{exc.response['Error']['Code']} — check S3 prefix {output_prefix}"
                ),
            }
