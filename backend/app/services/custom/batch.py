"""
Real custom pipeline runner — AWS Batch using the bioplatform/tools Docker image.

Each tool is implemented as a self-contained shell script sourced from
bioplatform_helpers.sh.  The script is uploaded to S3, then run as a
single-container AWS Batch job (same pattern as BioScriptRunner).
"""
import logging
import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.services.batch_tracker import set_batch_job_id, delete_batch_job_id
from app.services.custom.base import CustomPipelineRunner

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
                    "[custom/batch] throttled (attempt %d/%d), retrying in %ds",
                    attempt + 1,
                    _MAX_SUBMIT_RETRIES,
                    wait,
                )
                time.sleep(wait)
            else:
                raise


# Maximum time (seconds) to wait for a Batch job to complete
_POLL_DEADLINE = 7200  # 2 hours
_POLL_INTERVAL = 15

_KEEP_EXTS = {
    "html", "txt", "tsv", "csv", "json", "log",
    "gz", "bam", "bai", "vcf", "bed",
    "fasta", "fa", "faa", "ffn", "fastg", "gfa", "gff", "gbk", "nwk", "svg",
}

_MIME_MAP = {
    "html":  "text/html",
    "txt":   "text/plain",
    "tsv":   "text/tab-separated-values",
    "csv":   "text/csv",
    "json":  "application/json",
    "log":   "text/plain",
    "gz":    "application/gzip",
    "bam":   "application/octet-stream",
    "bai":   "application/octet-stream",
    "vcf":   "text/plain",
    "bed":   "text/plain",
    "fasta": "text/plain",
    "fa":    "text/plain",
    "faa":   "text/plain",
    "ffn":   "text/plain",
    "fastg": "text/plain",
    "gfa":   "text/plain",
    "gff":   "text/plain",
    "gbk":   "text/plain",
    "nwk":   "text/plain",
    "svg":   "image/svg+xml",
}

# Tool-specific shell script snippets.
# Each script receives the helpers library already sourced, and these env vars:
#   INPUT_FILE   — s3:// URI of primary input
#   INPUT_R2     — s3:// URI of R2 (may be empty)
#   OUTPUT_DIR   — s3:// prefix for outputs
#   JOB_ID       — unique job identifier
_TOOL_SCRIPTS: dict[str, str] = {
    "spades": """
set -euo pipefail
THREADS=$(bp_threads)
MEM=$(bp_mem_gb)
WORKDIR=/tmp/spades_${JOB_ID}
mkdir -p ${WORKDIR}/input ${WORKDIR}/output

bp_log "Downloading input reads…"
bp_s3_get "${INPUT_FILE}" ${WORKDIR}/input/reads_R1.fastq.gz
R2_FLAG=""
if [ -n "${INPUT_R2:-}" ]; then
    bp_s3_get "${INPUT_R2}" ${WORKDIR}/input/reads_R2.fastq.gz
    R2_FLAG="-2 ${WORKDIR}/input/reads_R2.fastq.gz"
fi

bp_step "Running SPAdes assembly"
spades.py -1 ${WORKDIR}/input/reads_R1.fastq.gz ${R2_FLAG} \\
    -o ${WORKDIR}/output \\
    --threads ${THREADS} \\
    --memory ${MEM}

bp_step "Running QUAST quality assessment"
QUAST_OUT=${WORKDIR}/quast
quast.py ${WORKDIR}/output/contigs.fasta \\
    -o ${QUAST_OUT} \\
    --threads ${THREADS}

cp ${QUAST_OUT}/report.html ${WORKDIR}/output/quast_report.html 2>/dev/null || true
cp ${QUAST_OUT}/report.txt  ${WORKDIR}/output/assembly_stats.txt 2>/dev/null || true

bp_step "Syncing results to S3"
bp_s3_sync_out ${WORKDIR}/output "${OUTPUT_DIR}"
bp_done "Assembly complete"
""",

    "kraken2": """
set -euo pipefail
THREADS=$(bp_threads)
WORKDIR=/tmp/kraken2_${JOB_ID}
mkdir -p ${WORKDIR}/input ${WORKDIR}/output

bp_log "Downloading input reads…"
bp_s3_get "${INPUT_FILE}" ${WORKDIR}/input/reads.fastq.gz
R2_FLAG=""
if [ -n "${INPUT_R2:-}" ]; then
    bp_s3_get "${INPUT_R2}" ${WORKDIR}/input/reads_R2.fastq.gz
    R2_FLAG="${WORKDIR}/input/reads_R2.fastq.gz"
fi

KRAKEN_DB=${KRAKEN2_DB:-/opt/kraken2_standard_db}

bp_step "Running Kraken2 classification"
if [ -n "${R2_FLAG}" ]; then
    kraken2 --db ${KRAKEN_DB} --threads ${THREADS} \\
        --paired ${WORKDIR}/input/reads.fastq.gz ${R2_FLAG} \\
        --report ${WORKDIR}/output/taxonomy_report.tsv \\
        --classified-out ${WORKDIR}/output/classified#.fastq \\
        --unclassified-out ${WORKDIR}/output/unclassified#.fastq \\
        --gzip-compressed
else
    kraken2 --db ${KRAKEN_DB} --threads ${THREADS} \\
        ${WORKDIR}/input/reads.fastq.gz \\
        --report ${WORKDIR}/output/taxonomy_report.tsv \\
        --classified-out ${WORKDIR}/output/classified.fastq \\
        --gzip-compressed
fi

bp_step "Running Bracken abundance estimation"
bracken -d ${KRAKEN_DB} \\
    -i ${WORKDIR}/output/taxonomy_report.tsv \\
    -o ${WORKDIR}/output/bracken_report.tsv \\
    -l S  # Species-level

bp_step "Generating Krona chart"
ktImportTaxonomy -t 5 -m 3 \\
    ${WORKDIR}/output/taxonomy_report.tsv \\
    -o ${WORKDIR}/output/krona.html

# Compress FASTQ outputs
pigz -p ${THREADS} ${WORKDIR}/output/*.fastq 2>/dev/null || true

bp_step "Syncing results to S3"
bp_s3_sync_out ${WORKDIR}/output "${OUTPUT_DIR}"
bp_done "Metagenome profiling complete"
""",

    "prokka": """
set -euo pipefail
THREADS=$(bp_threads)
WORKDIR=/tmp/prokka_${JOB_ID}
mkdir -p ${WORKDIR}/input ${WORKDIR}/output

bp_log "Downloading assembly…"
bp_s3_get "${INPUT_FILE}" ${WORKDIR}/input/assembly.fasta

bp_step "Running Prokka annotation"
prokka --outdir ${WORKDIR}/output \\
    --prefix genome \\
    --cpus ${THREADS} \\
    --force \\
    ${WORKDIR}/input/assembly.fasta

# Standardise output names
cp ${WORKDIR}/output/genome.faa ${WORKDIR}/output/proteins.faa 2>/dev/null || true
cp ${WORKDIR}/output/genome.ffn ${WORKDIR}/output/genes.ffn 2>/dev/null || true
cp ${WORKDIR}/output/genome.log ${WORKDIR}/output/prokka.log 2>/dev/null || true

# Summary stats
echo "=== Prokka annotation summary ===" > ${WORKDIR}/output/stats.txt
grep -c ">" ${WORKDIR}/output/genome.faa >> ${WORKDIR}/output/stats.txt 2>/dev/null || echo "proteins: N/A" >> ${WORKDIR}/output/stats.txt

bp_step "Syncing results to S3"
bp_s3_sync_out ${WORKDIR}/output "${OUTPUT_DIR}"
bp_done "Annotation complete"
""",

    "iqtree": """
set -euo pipefail
THREADS=$(bp_threads)
WORKDIR=/tmp/iqtree_${JOB_ID}
mkdir -p ${WORKDIR}/input ${WORKDIR}/output

bp_log "Downloading sequences…"
bp_s3_get "${INPUT_FILE}" ${WORKDIR}/input/sequences.fasta

bp_step "Running MAFFT multiple sequence alignment"
mafft --auto \\
    --thread ${THREADS} \\
    ${WORKDIR}/input/sequences.fasta \\
    > ${WORKDIR}/output/aligned.fasta

bp_step "Running IQ-TREE 2 maximum-likelihood tree"
iqtree2 -s ${WORKDIR}/output/aligned.fasta \\
    -m MFP \\
    -B 1000 \\
    --prefix ${WORKDIR}/output/iqtree \\
    -T ${THREADS} \\
    -redo

# Rename main tree output for clarity
cp ${WORKDIR}/output/iqtree.treefile ${WORKDIR}/output/tree.nwk 2>/dev/null || true

bp_step "Syncing results to S3"
bp_s3_sync_out ${WORKDIR}/output "${OUTPUT_DIR}"
bp_done "Phylogenomics complete"
""",

    "flye": """
set -euo pipefail
THREADS=$(bp_threads)
WORKDIR=/tmp/flye_${JOB_ID}
mkdir -p ${WORKDIR}/input ${WORKDIR}/output

bp_log "Downloading long reads…"
bp_s3_get "${INPUT_FILE}" ${WORKDIR}/input/reads.fastq.gz

bp_step "Running NanoStat QC"
NanoStat --fastq ${WORKDIR}/input/reads.fastq.gz \\
    --threads ${THREADS} \\
    > ${WORKDIR}/output/nanostat.txt

bp_step "Running Flye long-read assembly"
# Auto-detect read type from filename; default to --nano-raw
READ_TYPE=${FLYE_READ_TYPE:-nano-raw}
flye --${READ_TYPE} ${WORKDIR}/input/reads.fastq.gz \\
    --out-dir ${WORKDIR}/flye_out \\
    --threads ${THREADS}

cp ${WORKDIR}/flye_out/assembly.fasta         ${WORKDIR}/output/assembly.fasta
cp ${WORKDIR}/flye_out/assembly_info.txt      ${WORKDIR}/output/assembly_info.txt
cp ${WORKDIR}/flye_out/assembly_graph.gfa     ${WORKDIR}/output/assembly_graph.gfa 2>/dev/null || true
cp ${WORKDIR}/flye_out/flye.log               ${WORKDIR}/output/flye.log

bp_step "Syncing results to S3"
bp_s3_sync_out ${WORKDIR}/output "${OUTPUT_DIR}"
bp_done "Long-read assembly complete"
""",
}


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
    key = f"custom-jobs/{job_id}/pipeline.sh"
    _s3().put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=script.encode(),
        ContentType="text/x-shellscript",
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
        "instance_type":   settings.BIOSCRIPT_DOCKER_IMAGE,
        "runtime_seconds": runtime,
    }


class AWSBatchCustomRunner(CustomPipelineRunner):
    def run(
        self,
        tool: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        storage_key_r2: Optional[str] = None,
    ) -> dict:
        start = time.time()

        script_body = _TOOL_SCRIPTS.get(tool)
        if not script_body:
            raise ValueError(f"Unknown custom pipeline tool: {tool!r}")

        # Wrap with helpers source
        full_script = (
            "#!/usr/bin/env bash\n"
            ". /usr/local/lib/bio_helpers.sh\n"
            + script_body
        )

        input_s3      = f"s3://{settings.S3_BUCKET}/{storage_key}"
        input_r2_s3   = f"s3://{settings.S3_BUCKET}/{storage_key_r2}" if storage_key_r2 else ""
        output_prefix = f"custom-output/{job_id}/"
        output_s3     = f"s3://{settings.S3_BUCKET}/{output_prefix}"
        script_s3     = _upload_script(full_script, job_id)

        batch = _batch()

        job_definition = f"bioplatform-custom-{tool}-{job_id[:8]}"
        batch_job_id: str | None = None
        try:
            try:
                _with_backoff(
                    batch.register_job_definition,
                    jobDefinitionName=job_definition,
                    type="container",
                    containerProperties={
                        "image":   settings.BIOSCRIPT_DOCKER_IMAGE,
                        "vcpus":   4,
                        "memory":  16384,
                        "jobRoleArn": settings.BATCH_JOB_ROLE_ARN,
                        "command": [
                            "bash", "-c",
                            f"aws s3 cp '{script_s3}' /tmp/pipeline.sh && "
                            "chmod +x /tmp/pipeline.sh && "
                            ". /usr/local/lib/bio_helpers.sh && "
                            "/tmp/pipeline.sh",
                        ],
                        "environment": [
                            {"name": "INPUT_FILE",  "value": input_s3},
                            {"name": "INPUT_R2",    "value": input_r2_s3},
                            {"name": "OUTPUT_DIR",  "value": output_s3},
                            {"name": "JOB_ID",      "value": job_id},
                            {"name": "AWS_REGION",  "value": settings.AWS_REGION},
                        ],
                    },
                )
            except ClientError as exc:
                raise RuntimeError(
                    f"[custom] register_job_definition failed for tool {tool!r} "
                    f"job {job_id}: "
                    f"{exc.response['Error']['Code']} — {exc.response['Error']['Message']}"
                ) from exc

            try:
                response = _with_backoff(
                    batch.submit_job,
                    jobName=f"bioplatform-custom-{tool}-{job_id[:8]}",
                    jobQueue=settings.BATCH_JOB_QUEUE,
                    jobDefinition=job_definition,
                )
            except ClientError as exc:
                raise RuntimeError(
                    f"[custom] submit_job failed for tool {tool!r} job {job_id}: "
                    f"{exc.response['Error']['Code']} — {exc.response['Error']['Message']}"
                ) from exc
            batch_job_id = response["jobId"]
            logger.info(
                "[custom/batch] submitted tool=%s batch_job_id=%s", tool, batch_job_id
            )
            if job_id:
                try:
                    set_batch_job_id(job_id, batch_job_id)
                except Exception as redis_exc:
                    # Non-fatal: the job is already running on Batch.  The cancel
                    # endpoint won't be able to terminate it, but the job itself
                    # will still complete and results will be collected.
                    logger.warning(
                        "[custom/batch] could not store batch tracking key "
                        "for job %s: %s",
                        job_id,
                        redis_exc,
                    )

            # Poll until done
            deadline = time.time() + _POLL_DEADLINE
            succeeded = False
            while time.time() < deadline:
                time.sleep(_POLL_INTERVAL)
                try:
                    resp = batch.describe_jobs(jobs=[batch_job_id])
                    job_info = resp["jobs"][0]
                except ClientError as poll_exc:
                    logger.warning(
                        "[custom/batch] transient error polling %s: %s — retrying",
                        batch_job_id,
                        poll_exc,
                    )
                    continue
                status = job_info["status"]
                logger.info("[custom/batch] %s status=%s", batch_job_id, status)
                if status == "SUCCEEDED":
                    succeeded = True
                    break
                if status == "FAILED":
                    reason = job_info.get("statusReason", "unknown")
                    raise RuntimeError(
                        f"AWS Batch job {batch_job_id} failed for tool {tool!r}: {reason}"
                    )

            if not succeeded:
                raise TimeoutError(
                    f"AWS Batch job {batch_job_id} did not complete within "
                    f"{_POLL_DEADLINE}s (tool={tool!r}, platform job={job_id})"
                )

        finally:
            # Always deregister the job definition and clean up the tracking key
            # so we don't leak resources on failure or cancellation.
            try:
                batch.deregister_job_definition(jobDefinition=job_definition)
            except Exception:
                pass
            if job_id:
                try:
                    delete_batch_job_id(job_id)
                except Exception:
                    pass

        runtime = int(time.time() - start)
        logger.info("[custom/batch] tool=%s done in %ds", tool, runtime)
        try:
            return _collect_results(output_prefix, runtime)
        except ClientError as exc:
            logger.error(
                "[custom/batch] S3 listing failed after job completion "
                "(results exist but cannot be listed): %s",
                exc,
            )
            return {
                "type": "files",
                "files": [],
                "instance_type": settings.BIOSCRIPT_DOCKER_IMAGE,
                "runtime_seconds": runtime,
                "warning": (
                    f"Job completed but result listing failed: "
                    f"{exc.response['Error']['Code']} — check S3 prefix {output_prefix}"
                ),
            }
