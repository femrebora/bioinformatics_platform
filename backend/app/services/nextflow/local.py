"""Local Nextflow runner — runs nf-core/sarek on the host via Docker.

Requires:
  - Docker socket mounted in the worker container (/var/run/docker.sock)
  - Nextflow installed in the worker image (Java 17 + Nextflow 24.10.2)
  - /outputs volume shared between backend and worker

Set NEXTFLOW_BACKEND=local (and optionally NEXTFLOW_PROFILE=docker) to enable.
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from app.config import settings
from app.services.nextflow.base import NextflowRunner
from app.services.log_streamer import append_log

logger = logging.getLogger(__name__)

_PROC_TIMEOUT = 13_500  # 3 h 45 m — slightly under Celery soft_time_limit

PIPELINE_VERSIONS: dict[str, str] = {
    "sarek": "3.4.4",
}

PIPELINE_EXTRA_PARAMS: dict[str, list[str]] = {
    "sarek": ["--genome", "GATK.GRCh38"],
}

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


def _generate_local_samplesheet(
    pid: str,
    fastq_1: str,
    job_id: str,
    fastq_2: str = "",
) -> str:
    """Write samplesheet CSV to /outputs/{job_id}/ and return the path."""
    sample = f"sample_{job_id[:8]}"
    r2 = fastq_2

    if pid == "sarek":
        csv = (
            "patient,sex,status,sample,lane,fastq_1,fastq_2\n"
            f"patient1,XX,0,{sample},1,{fastq_1},{r2}\n"
        )
    elif pid in ("rnaseq", "methylseq"):
        csv = (
            "sample,fastq_1,fastq_2,strandedness\n"
            f"{sample},{fastq_1},{r2},auto\n"
        )
    elif pid == "atacseq":
        csv = f"sample,fastq_1,fastq_2\n{sample},{fastq_1},{r2}\n"
    elif pid == "chipseq":
        csv = (
            "sample,fastq_1,fastq_2,antibody,control\n"
            f"{sample},{fastq_1},{r2},H3K27AC,\n"
        )
    else:
        csv = f"sample,fastq_1,fastq_2\n{sample},{fastq_1},{r2}\n"

    job_dir = Path("/outputs") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = job_dir / "samplesheet.csv"
    sheet_path.write_text(csv)
    logger.info("[nextflow/local] samplesheet written → %s", sheet_path)
    return str(sheet_path)


def _drain(pipe, log_fn) -> None:
    try:
        for line in pipe:
            log_fn(line.rstrip())
    except Exception:
        pass


def _collect_results(outdir: Path, runtime: int) -> dict:
    """Walk the output directory and return a result dict."""
    files = []
    if outdir.exists():
        for fpath in sorted(outdir.rglob("*")):
            if not fpath.is_file():
                continue
            name = fpath.name
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in _KEEP_EXTS:
                continue
            try:
                size = fpath.stat().st_size
            except OSError:
                size = 0
            files.append({
                "name":        name,
                "path":        str(fpath),
                "size_bytes":  size,
                "mime_type":   _MIME_MAP.get(ext, "application/octet-stream"),
                "description": "",
            })

    logger.info("[nextflow/local] collected %d output files", len(files))
    return {
        "type":            "files",
        "files":           files,
        "instance_type":   "local",
        "runtime_seconds": runtime,
    }


class LocalNextflowRunner(NextflowRunner):
    """Runs nf-core/sarek locally via Docker subprocess."""

    def run(
        self,
        pipeline_id: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        storage_key_r2: str | None = None,
        workflow_config: dict | None = None,
    ) -> dict:
        from datetime import datetime, timezone

        start = time.time()
        pid = pipeline_id.lower().removeprefix("nf-core/")
        version = PIPELINE_VERSIONS.get(pid, "latest")
        profile = settings.NEXTFLOW_PROFILE or "docker"

        def _log(msg: str) -> None:
            append_log(job_id, f"[nextflow/local] {msg}")
            logger.info("[nextflow/local][%s] %s", job_id, msg)

        _log(f"Starting nf-core/{pid} v{version} (profile={profile})")

        # Resolve input path — storage_key is either a local /uploads/... path
        # or an s3:// URI. For local runs we expect a local path.
        fastq_1 = storage_key
        fastq_2 = storage_key_r2 or ""

        sheet_path = _generate_local_samplesheet(pid, fastq_1, job_id, fastq_2)
        outdir = Path("/outputs") / job_id / "results"
        workdir = Path("/outputs") / job_id / "work"
        outdir.mkdir(parents=True, exist_ok=True)
        workdir.mkdir(parents=True, exist_ok=True)

        extra = PIPELINE_EXTRA_PARAMS.get(pid, [])

        # Allow workflow_config to override genome / params
        cfg = workflow_config or {}
        genome = cfg.get("genome", "")
        if genome and "--genome" not in extra:
            extra = ["--genome", genome] + extra
        elif genome and "--genome" in extra:
            # Replace the default genome value
            idx = extra.index("--genome")
            extra = extra[:idx + 1] + [genome] + extra[idx + 2:]

        cmd = [
            "nextflow", "run", f"nf-core/{pid}",
            "-r", version,
            "-c", "/app/nextflow_local.config",
            "-profile", profile,
            "--input", sheet_path,
            "--outdir", str(outdir),
            "-work-dir", str(workdir),
            *extra,
        ]

        _log("Command: " + " ".join(cmd))

        env = {**os.environ}

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            # Drain output in background thread so the pipe never blocks
            def _log_line(line: str) -> None:
                _log(line)

            t = threading.Thread(target=_drain, args=(proc.stdout, _log_line), daemon=True)
            t.start()

            try:
                proc.wait(timeout=_PROC_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RuntimeError(
                    f"[nextflow/local] Pipeline timed out after {_PROC_TIMEOUT}s"
                )

            t.join(timeout=5)

            if proc.returncode != 0:
                raise RuntimeError(
                    f"[nextflow/local] nextflow exited with code {proc.returncode}"
                )

        except FileNotFoundError as exc:
            raise RuntimeError(
                "[nextflow/local] 'nextflow' not found in PATH — "
                "is Nextflow installed in the worker image?"
            ) from exc

        runtime = int(time.time() - start)
        _log(f"Pipeline completed in {runtime}s")

        result = _collect_results(outdir, runtime)
        result["provenance"] = {
            "pipeline":         f"nf-core/{pid}",
            "pipeline_version": version,
            "genome":           genome or PIPELINE_EXTRA_PARAMS.get(pid, ["", ""])[1] if "--genome" in (PIPELINE_EXTRA_PARAMS.get(pid) or []) else "(not set)",
            "completed_at":     datetime.now(timezone.utc).isoformat(),
            "instance_type":    "local",
            "runtime_seconds":  runtime,
        }
        return result
