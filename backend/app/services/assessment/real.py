"""Real assessment runner — queries ClinVar, CancerHotspots, and dbSNP."""
import logging
import os
import time

from app.config import settings
from app.services.assessment.base import AssessmentResult, AssessmentRunner
from app.services.assessment.databases import (
    query_cancer_hotspots,
    query_clinvar,
    query_dbsnp,
)
from app.services.assessment.report import generate_pdf
from app.services.log_streamer import append_log

logger = logging.getLogger(__name__)


class RealAssessmentRunner(AssessmentRunner):
    def run(
        self,
        job_id: str,
        variants: list[dict],
        workflow_config: dict | None = None,
    ) -> AssessmentResult:
        append_log(job_id, f"Starting annotation of {len(variants)} variant(s)")
        annotated: list[dict] = []

        for i, v in enumerate(variants):
            ann = dict(v)

            # 1. ClinVar — clinical significance + gene name
            append_log(job_id, f"  [{i+1}/{len(variants)}] ClinVar: {v.get('chrom')}:{v.get('pos')}")
            cv = query_clinvar(v.get("chrom", ""), v.get("pos", 0), v.get("ref", ""), v.get("alt", ""))
            ann["significance"] = cv.get("significance", "Unknown")
            ann["gene"]         = cv.get("gene", v.get("gene", ""))
            ann["rsid"]         = cv.get("rsid", v.get("id", "."))
            time.sleep(0.35)   # NCBI rate limit: 3 req/s

            # 2. dbSNP — rsID fallback if ClinVar didn't provide one
            if ann["rsid"] in (".", ""):
                snp = query_dbsnp(v.get("chrom", ""), v.get("pos", 0))
                ann["rsid"] = snp.get("rsid", ".")
                time.sleep(0.35)

            # 3. CancerHotspots — only if gene is known
            if ann["gene"]:
                hs = query_cancer_hotspots(ann["gene"])
                ann["hotspot"]      = hs.get("is_hotspot", False)
                ann["hotspot_type"] = hs.get("hotspot_type")
                time.sleep(0.35)
            else:
                ann["hotspot"] = False

            # 4. Population AF from VCF INFO field if present
            ann.setdefault("af", _parse_af(str(v.get("info", ""))))

            annotated.append(ann)

        # Generate PDF report
        output_path = os.path.join(settings.UPLOADS_DIR, f"assessment-{job_id}.pdf")
        append_log(job_id, f"Generating PDF report → {output_path}")
        try:
            generate_pdf(job_id, annotated, output_path)
            report_path: str | None = output_path
        except Exception as exc:
            logger.error("[assessment] PDF generation failed for %s: %s", job_id, exc)
            append_log(job_id, f"WARNING: PDF generation failed — {exc}")
            report_path = None

        pathogenic = sum(1 for a in annotated if "pathogenic" in a.get("significance", "").lower())
        hotspot_count = sum(1 for a in annotated if a.get("hotspot"))

        summary = (
            f"{len(annotated)} variants assessed. "
            f"{pathogenic} pathogenic/likely pathogenic. "
            f"{hotspot_count} cancer hotspot(s) found."
        )
        append_log(job_id, f"Assessment complete: {summary}")

        return AssessmentResult(
            summary=summary,
            variants=annotated,
            report_path=report_path,
        )


def _parse_af(info: str) -> float | None:
    for part in info.split(";"):
        if part.upper().startswith("AF="):
            try:
                return float(part.split("=", 1)[1])
            except ValueError:
                pass
    return None
