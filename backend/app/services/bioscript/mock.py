"""Mock BioScript runner.

Simulates a bash environment pipeline execution with a realistic delay
and returns representative output files.
"""
import hashlib
import random
import time
from typing import Any, Optional

from app.services.bioscript.base import BioScriptRunner


def _seed(storage_key: str) -> random.Random:
    digest = hashlib.md5(storage_key.encode()).hexdigest()
    return random.Random(int(digest[:8], 16))


class MockBioScriptRunner(BioScriptRunner):
    """Simulates a bash script pipeline run with a 5–15 s delay."""

    def run(
        self,
        storage_key: str,
        file_type: str,
        job_id: str = "",
        workflow_config: Optional[dict[str, Any]] = None,
    ) -> dict:
        start = time.time()
        rng = _seed(storage_key)
        delay = rng.uniform(5.0, 15.0)
        time.sleep(delay)
        runtime = int(time.time() - start)

        sample = f"sample_{rng.randint(100, 999)}"
        script = (workflow_config or {}).get("script", "# default QC + alignment")

        # Determine mock outputs based on script content
        outputs = [
            {
                "name": f"{sample}.bam",
                "path": f"results/align/{sample}.bam",
                "size_bytes": rng.randint(100_000_000, 2_000_000_000),
                "mime_type": "application/octet-stream",
                "description": "Aligned reads (BAM)",
            },
            {
                "name": f"{sample}.bam.bai",
                "path": f"results/align/{sample}.bam.bai",
                "size_bytes": rng.randint(100_000, 800_000),
                "mime_type": "application/octet-stream",
                "description": "BAM index",
            },
        ]

        if "call" in script or "variant" in script or "bcftools" in script:
            outputs.append({
                "name": f"{sample}.vcf.gz",
                "path": f"results/variants/{sample}.vcf.gz",
                "size_bytes": rng.randint(200_000, 3_000_000),
                "mime_type": "application/gzip",
                "description": "Variant calls (VCF)",
            })

        if "featurecount" in script or "star" in script or "rnaseq" in script:
            outputs.append({
                "name": "counts.txt",
                "path": "results/counts/counts.txt",
                "size_bytes": rng.randint(50_000, 500_000),
                "mime_type": "text/plain",
                "description": "Gene feature counts",
            })

        outputs.append({
            "name": "multiqc_report.html",
            "path": "results/qc/multiqc_report.html",
            "size_bytes": rng.randint(1_000_000, 8_000_000),
            "mime_type": "text/html",
            "description": "MultiQC quality report",
        })
        outputs.append({
            "name": "script.sh",
            "path": "logs/script.sh",
            "size_bytes": len(script.encode()),
            "mime_type": "text/plain",
            "description": "Executed bash script",
        })

        return {
            "type": "files",
            "files": outputs,
            "instance_type": "c5.2xlarge (mock)",
            "runtime_seconds": runtime,
            "_mock": True,
        }
