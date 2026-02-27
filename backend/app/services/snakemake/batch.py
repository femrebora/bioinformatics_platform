"""
Real Snakemake runner — submits workflows to AWS Batch using
snakemake-executor-plugin-aws-batch.

How it works:
1. Generates a minimal Snakefile that wraps the requested wrappers / workflow.
2. Spawns a Snakemake subprocess with --executor aws-batch and
   --default-storage-provider s3.
3. Each Snakemake rule runs in its own Batch job using the Snakemake Docker
   image (or a custom bio tools image).
4. On completion scans the S3 output prefix and returns a result dict.
"""
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.services.snakemake.base import SnakemakeRunner

logger = logging.getLogger(__name__)

# Subprocess timeout — see nextflow/batch.py for rationale.
_PROC_TIMEOUT = 13_500  # 3 h 45 m

# File extensions to surface to the user
_KEEP_EXTS = {
    "html", "txt", "csv", "tsv", "json",
    "gz", "bam", "bai", "vcf", "bed",
    "bigwig", "bw", "log",
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
    "bigwig": "application/octet-stream",
    "bw":   "application/octet-stream",
    "log":  "text/plain",
}


def _s3():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def _generate_snakefile(
    workflow_config: Optional[dict[str, Any]],
    input_s3_uri: str,
    output_s3_prefix: str,
) -> str:
    """Generate a Snakefile for the given workflow configuration.

    If workflow_config contains wrappers, generates individual rules for each.
    If it contains a workflow ID (community workflow), generates a minimal
    passthrough rule.
    Falls back to a generic QC pipeline if no config is provided.
    """
    wrappers: list[str] = []
    workflow_id: str | None = None

    if workflow_config:
        wrappers = workflow_config.get("wrappers", [])
        workflows = workflow_config.get("workflows", [])
        if workflows:
            workflow_id = workflows[0]

    if workflow_id:
        # Community workflow execution is not yet implemented in production.
        # Raising here ensures the job fails fast (with a clear message) rather
        # than succeeding with a useless done.txt and billing the user for nothing.
        raise NotImplementedError(
            f"Community workflow '{workflow_id}' execution is not yet available. "
            "Use individual Snakemake wrappers instead. "
            "Full community workflow support is coming soon."
        )

    if wrappers:
        # Generate a rule for each requested wrapper
        rules = []
        prev_output = input_s3_uri
        for i, wrapper_id in enumerate(wrappers):
            rule_name = f"step_{i}_{wrapper_id.replace('/', '_').replace('-', '_')}"
            this_output = f"{output_s3_prefix}/{rule_name}/output"
            rules.append(f"""
rule {rule_name}:
    input: "{prev_output}"
    output: directory("{this_output}")
    wrapper:
        "{wrapper_id}"
""")
            prev_output = f"{this_output}"

        all_rule = f'rule all:\n    input: "{prev_output}"\n'
        return all_rule + "\n".join(rules)

    # Default: generic QC + alignment Snakefile
    return f"""
# Auto-generated generic Snakefile
rule all:
    input:
        "{output_s3_prefix}/multiqc_report.html",
        "{output_s3_prefix}/aligned.bam"

rule fastp_qc:
    input: "{input_s3_uri}"
    output:
        html="{output_s3_prefix}/multiqc_report.html",
        json="{output_s3_prefix}/fastp.json"
    wrapper:
        "v3.13.0/bio/fastp"

rule bwa_mem:
    input:
        reads="{input_s3_uri}"
    output:
        "{output_s3_prefix}/aligned.bam"
    wrapper:
        "v3.13.0/bio/bwa/mem"
"""


def _drain(pipe, log_fn) -> None:
    """Read all lines from a pipe, forwarding to log_fn. Prevents deadlock."""
    try:
        for line in pipe:
            log_fn(line.rstrip())
    except Exception:
        pass


def _collect_results(output_prefix: str, runtime: int) -> dict:
    """Scan S3 output prefix and return a result dict."""
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

    logger.info("[snakemake/batch] collected %d output files", len(files))
    return {
        "type":            "files",
        "files":           files,
        "instance_type":   settings.SNAKEMAKE_CONTAINER_IMAGE.split(":")[0].split("/")[-1],
        "runtime_seconds": runtime,
    }


class AWSBatchSnakemakeRunner(SnakemakeRunner):
    """Runs Snakemake workflows on AWS Batch."""

    def run(
        self,
        pipeline_id: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        workflow_config: Optional[dict[str, Any]] = None,
    ) -> dict:
        start = time.time()

        input_s3      = f"s3://{settings.S3_BUCKET}/{storage_key}"
        output_prefix = f"smk-output/{job_id}"
        output_s3     = f"s3://{settings.S3_BUCKET}/{output_prefix}"
        work_s3       = f"s3://{settings.S3_BUCKET}/smk-work/{job_id}"

        batch_queue = settings.SNAKEMAKE_BATCH_QUEUE or settings.BATCH_JOB_QUEUE

        snakefile = _generate_snakefile(workflow_config, input_s3, output_s3)

        with tempfile.TemporaryDirectory() as run_dir:
            # Write Snakefile to temp dir
            snakefile_path = Path(run_dir) / "Snakefile"
            snakefile_path.write_text(snakefile)

            # Write minimal config
            config_path = Path(run_dir) / "config.yaml"
            config_path.write_text(json.dumps({
                "input": input_s3,
                "output": output_s3,
            }))

            cmd = [
                "snakemake",
                "--snakefile",       str(snakefile_path),
                "--executor",        "aws-batch",
                "--default-storage-provider", "s3",
                "--default-storage-prefix",   work_s3,
                "--jobs",            "4",
                "--rerun-incomplete",
                "--configfile",      str(config_path),
                "--aws-batch-queue", batch_queue,
                "--container-image", settings.SNAKEMAKE_CONTAINER_IMAGE,
            ]

            env = {
                **os.environ,
                "AWS_REGION":            settings.AWS_REGION,
                "AWS_DEFAULT_REGION":    settings.AWS_REGION,
                "AWS_ACCESS_KEY_ID":     settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            }

            logger.info("[snakemake/batch] starting job=%s queue=%s wrappers=%s",
                        job_id, batch_queue,
                        workflow_config.get("wrappers", []) if workflow_config else [])
            logger.info("[snakemake/batch] cmd: %s", " ".join(cmd))

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=run_dir,
                    env=env,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "snakemake executable not found in PATH; ensure the worker "
                    "image has Snakemake installed (see Dockerfile.worker)"
                )
            drain_thread = threading.Thread(
                target=_drain,
                args=(proc.stdout, logger.info),
                daemon=True,
            )
            drain_thread.start()
            try:
                returncode = proc.wait(timeout=_PROC_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise RuntimeError(
                    f"Snakemake process timed out after {_PROC_TIMEOUT}s "
                    f"(job={job_id})"
                )
            finally:
                drain_thread.join(timeout=10)

        runtime = int(time.time() - start)

        if returncode != 0:
            raise RuntimeError(
                f"Snakemake exited {returncode} after {runtime}s "
                f"(job={job_id})"
            )

        logger.info("[snakemake/batch] finished in %ds", runtime)
        try:
            return _collect_results(output_prefix, runtime)
        except ClientError as exc:
            logger.error(
                "[snakemake/batch] S3 listing failed after workflow completion "
                "(results exist but cannot be listed): %s",
                exc,
            )
            return {
                "type": "files",
                "files": [],
                "instance_type": settings.SNAKEMAKE_CONTAINER_IMAGE.split(":")[0].split("/")[-1],
                "runtime_seconds": runtime,
                "warning": (
                    f"Workflow completed but result listing failed: "
                    f"{exc.response['Error']['Code']} — check S3 prefix {output_prefix}"
                ),
            }
