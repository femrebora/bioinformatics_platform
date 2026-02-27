"""
Real Nextflow runner — submits nf-core pipelines to AWS Batch.

How it works:
1. Generates a minimal samplesheet CSV and uploads it to S3.
2. Spawns a Nextflow subprocess (blocking) that talks to AWS Batch.
   Each pipeline step runs in its own Batch job container pulled from
   Biocontainers / quay.io — no packages need to be installed manually.
3. Nextflow uses its native nf-amazon S3 client to stage files, so no
   aws-cli is required inside Batch job containers.
4. On completion, scans the S3 output prefix and returns a result dict.

Paired-end support:
  Pass storage_key_r2 to run() for paired-end FASTQ. The samplesheet
  fastq_2 column is filled when storage_key_r2 is provided.
"""

import logging
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.services.nextflow.base import NextflowRunner

logger = logging.getLogger(__name__)

# Subprocess timeout: slightly under the Celery soft_time_limit (13 800 s) so
# the RuntimeError propagates and the task can write status="failed" before
# Celery's hard SIGKILL fires at 14 400 s.
_PROC_TIMEOUT = 13_500  # 3 h 45 m

# Pinned nf-core pipeline release tags.
# Update these when you want to adopt a newer pipeline version.
PIPELINE_VERSIONS: dict[str, str] = {
    "rnaseq":    "3.14.0",
    "sarek":     "3.4.4",
    "atacseq":   "2.1.2",
    "chipseq":   "2.0.0",
    "methylseq": "2.7.1",
    "ampliseq":  "2.11.0",
    "fetchngs":  "1.12.0",
}

# Required pipeline-specific parameters (genome, aligner, etc.)
PIPELINE_EXTRA_PARAMS: dict[str, list[str]] = {
    "rnaseq":    ["--genome", "GRCh38", "--aligner", "star_salmon"],
    "sarek":     ["--genome", "GATK.GRCh38"],
    "atacseq":   ["--genome", "GRCh38"],
    "chipseq":   ["--genome", "GRCh38"],
    "methylseq": ["--genome", "GRCh38"],
    "ampliseq":  [
        "--FW_primer", "GTGYCAGCMGCCGCGGTAA",
        "--RV_primer", "GGACTACNVGGGTWTCTAAT",
    ],
}

# File extensions to surface to the user (skip Nextflow work-dir cache files)
_KEEP_EXTS = {
    "html", "txt", "csv", "tsv", "json",
    "gz", "bam", "bai", "vcf", "bed",
    "bigwig", "bw", "narrowpeak", "broadpeak",
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
}


def _s3():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def _generate_samplesheet(
    pid: str,
    input_s3_uri: str,
    job_id: str,
    input_r2_s3_uri: str = "",
) -> str:
    """Build a samplesheet CSV (paired- or single-end), upload to S3, return URI."""
    sample = f"sample_{job_id[:8]}"
    r2 = input_r2_s3_uri  # empty string → single-end

    if pid in ("rnaseq", "methylseq"):
        csv = (
            "sample,fastq_1,fastq_2,strandedness\n"
            f"{sample},{input_s3_uri},{r2},auto\n"
        )
    elif pid == "atacseq":
        csv = f"sample,fastq_1,fastq_2\n{sample},{input_s3_uri},{r2}\n"
    elif pid == "sarek":
        csv = (
            "patient,sex,status,sample,lane,fastq_1,fastq_2\n"
            f"patient1,XX,0,{sample},1,{input_s3_uri},{r2}\n"
        )
    elif pid == "chipseq":
        csv = (
            "sample,fastq_1,fastq_2,antibody,control\n"
            f"{sample},{input_s3_uri},{r2},H3K27AC,\n"
        )
    elif pid == "ampliseq":
        csv = (
            "sampleID,forwardPrimer,reversePrimer,fastq_1,fastq_2\n"
            f"{sample},GTGYCAGCMGCCGCGGTAA,GGACTACNVGGGTWTCTAAT,{input_s3_uri},{r2}\n"
        )
    elif pid == "fetchngs":
        # fetchngs expects SRA IDs, not a FASTQ path
        csv = f"id\n{input_s3_uri}\n"
    else:
        csv = f"sample,fastq_1,fastq_2\n{sample},{input_s3_uri},{r2}\n"

    key = f"samplesheets/{job_id}/samplesheet.csv"
    try:
        _s3().put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=csv.encode(),
            ContentType="text/csv",
        )
    except ClientError as exc:
        raise RuntimeError(
            f"[nextflow] S3 upload of samplesheet failed for job {job_id}: "
            f"{exc.response['Error']['Code']} — {exc.response['Error']['Message']}"
        ) from exc
    uri = f"s3://{settings.S3_BUCKET}/{key}"
    logger.info("[nextflow/batch] samplesheet uploaded → %s", uri)
    return uri


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

    logger.info("[nextflow/batch] collected %d output files", len(files))
    return {
        "type":            "files",
        "files":           files,
        "instance_type":   settings.BATCH_INSTANCE_TYPE,
        "runtime_seconds": runtime,
    }


class AWSBatchNextflowRunner(NextflowRunner):
    """Runs nf-core pipelines on AWS Batch via a Nextflow subprocess."""

    def run(
        self,
        pipeline_id: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        storage_key_r2: str | None = None,
        workflow_config: dict | None = None,
    ) -> dict:
        start = time.time()
        pid     = pipeline_id.lower().removeprefix("nf-core/")
        version = PIPELINE_VERSIONS.get(pid, "main")

        input_s3      = f"s3://{settings.S3_BUCKET}/{storage_key}"
        input_r2_s3   = f"s3://{settings.S3_BUCKET}/{storage_key_r2}" if storage_key_r2 else ""
        output_prefix = f"nf-output/{job_id}/"
        output_s3     = f"s3://{settings.S3_BUCKET}/{output_prefix}"
        work_s3       = f"s3://{settings.S3_BUCKET}/nf-work/{job_id}/"

        samplesheet_s3 = _generate_samplesheet(pid, input_s3, job_id, input_r2_s3)

        config_path = (
            Path(__file__).resolve().parents[3] / "nextflow_aws.config"
        )

        cmd = [
            "nextflow", "run", f"nf-core/{pid}",
            "-r",         version,
            "-c",         str(config_path),
            "--input",    samplesheet_s3,
            "--outdir",   output_s3,
            "-work-dir",  work_s3,
            "-resume",
        ]
        cmd += PIPELINE_EXTRA_PARAMS.get(pid, [])

        logger.info("[nextflow/batch] starting job=%s pipeline=%s version=%s",
                    job_id, pid, version)
        logger.info("[nextflow/batch] cmd: %s", " ".join(cmd))

        # Use a fresh temp dir as cwd so Nextflow does not auto-load any
        # stray nextflow.config file that might exist in /app.
        # NXF_HOME is set to a sub-directory of the temp dir so that
        # concurrent Nextflow workers on the same host do not share plugin
        # caches or metadata directories and cannot corrupt each other.
        with tempfile.TemporaryDirectory() as run_dir:
            env = {
                **os.environ,
                "NXF_HOME":             os.path.join(run_dir, ".nxf_home"),
                "NF_BATCH_QUEUE":       settings.BATCH_JOB_QUEUE,
                "NF_BATCH_JOB_ROLE":    settings.BATCH_JOB_ROLE_ARN,
                "AWS_REGION":           settings.AWS_REGION,
                "AWS_DEFAULT_REGION":   settings.AWS_REGION,
                "AWS_ACCESS_KEY_ID":    settings.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
                "NXF_OPTS":             "-Xms512m -Xmx2g",
            }
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
                    "nextflow executable not found in PATH; ensure the worker "
                    "image has Nextflow installed (see Dockerfile.worker)"
                )
            # Drain output in a background thread to prevent OS pipe buffer
            # deadlock (Nextflow is very verbose — easily exceeds 64 KB).
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
                    f"Nextflow process timed out after {_PROC_TIMEOUT}s "
                    f"(job={job_id}, pipeline={pid})"
                )
            finally:
                drain_thread.join(timeout=10)

        runtime = int(time.time() - start)

        if returncode != 0:
            raise RuntimeError(
                f"Nextflow exited {returncode} after {runtime}s "
                f"(job={job_id}, pipeline={pid})"
            )

        logger.info("[nextflow/batch] finished in %ds", runtime)
        try:
            return _collect_results(output_prefix, runtime)
        except ClientError as exc:
            logger.error(
                "[nextflow/batch] S3 listing failed after pipeline completion "
                "(results exist but cannot be listed): %s",
                exc,
            )
            return {
                "type": "files",
                "files": [],
                "instance_type": settings.BATCH_INSTANCE_TYPE,
                "runtime_seconds": runtime,
                "warning": (
                    f"Pipeline completed but result listing failed: "
                    f"{exc.response['Error']['Code']} — check S3 prefix {output_prefix}"
                ),
            }
