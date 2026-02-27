"""Mock Snakemake runner.

Simulates a Snakemake workflow execution with a realistic delay and
returns representative bioinformatics output files.
"""
import hashlib
import random
import time

from app.services.snakemake.base import SnakemakeRunner

TIER_INSTANCE_MAP = {
    "small":  "t3.small",
    "medium": "t3.medium",
    "large":  "c5.2xlarge",
}


def _seed(storage_key: str) -> random.Random:
    digest = hashlib.md5(storage_key.encode()).hexdigest()
    return random.Random(int(digest[:8], 16))


class MockSnakemakeRunner(SnakemakeRunner):
    """Simulates a Snakemake run with a 5–12 s delay and representative output files."""

    def run(
        self,
        pipeline_id: str,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        workflow_config: dict | None = None,
    ) -> dict:
        start = time.time()

        rng = _seed(storage_key)
        delay = rng.uniform(5.0, 12.0)
        time.sleep(delay)
        runtime = int(time.time() - start)

        instance = TIER_INSTANCE_MAP.get("medium", "t3.medium")
        sample = f"SAMPLE{rng.randint(1, 9)}"

        files = [
            {
                "name": f"{sample}.sorted.bam",
                "path": f"results/align/{sample}.sorted.bam",
                "size_bytes": rng.randint(200_000_000, 2_000_000_000),
                "mime_type": "application/octet-stream",
                "description": "Sorted alignment (BAM)",
            },
            {
                "name": f"{sample}.sorted.bam.bai",
                "path": f"results/align/{sample}.sorted.bam.bai",
                "size_bytes": rng.randint(100_000, 500_000),
                "mime_type": "application/octet-stream",
                "description": "BAM index",
            },
            {
                "name": f"{sample}.vcf.gz",
                "path": f"results/calls/{sample}.vcf.gz",
                "size_bytes": rng.randint(500_000, 5_000_000),
                "mime_type": "application/gzip",
                "description": "Variant calls (VCF)",
            },
            {
                "name": "multiqc_report.html",
                "path": "results/qc/multiqc_report.html",
                "size_bytes": rng.randint(2_000_000, 8_000_000),
                "mime_type": "text/html",
                "description": "MultiQC quality report",
            },
            {
                "name": f"{sample}.snakemake.log",
                "path": f"logs/{sample}.log",
                "size_bytes": rng.randint(5_000, 50_000),
                "mime_type": "text/plain",
                "description": "Snakemake execution log",
            },
        ]

        return {
            "type": "files",
            "files": files,
            "instance_type": instance,
            "runtime_seconds": runtime,
            "_mock": True,
        }
