"""Real assessment runner — ClinVar + gnomAD + CancerHotspots + dbSNP."""
import logging
import os
import time

from app.config import settings
from app.services.assessment.base import AssessmentResult, AssessmentRunner
from app.services.assessment.databases import (
    query_cancer_hotspots,
    query_clinvar,
    query_dbsnp,
    query_gnomad,
)
from app.services.assessment.report import generate_pdf
from app.services.log_streamer import append_log

logger = logging.getLogger(__name__)

# gnomAD dataset to use based on genome version
_GNOMAD_DATASET = {
    "hg38": "gnomad_r4",
    "hg19": "gnomad_r2_1",
    "grch38": "gnomad_r4",
    "grch37": "gnomad_r2_1",
}


class RealAssessmentRunner(AssessmentRunner):
    def run(
        self,
        job_id: str,
        variants: list[dict],
        workflow_config: dict | None = None,
    ) -> AssessmentResult:
        genome = (workflow_config or {}).get("genome", settings.ASSESSMENT_GENOME).lower()
        gnomad_dataset = _GNOMAD_DATASET.get(genome, "gnomad_r4")

        append_log(
            job_id,
            f"Starting annotation of {len(variants)} variant(s) "
            f"[genome: {genome}, gnomAD dataset: {gnomad_dataset}]",
        )
        annotated: list[dict] = []

        for i, v in enumerate(variants):
            ann = dict(v)
            chrom = v.get("chrom", "")
            pos   = v.get("pos", 0)
            ref   = v.get("ref", "")
            alt   = v.get("alt", "")

            # 1. ClinVar — clinical significance + gene + HGVS
            append_log(job_id, f"  [{i+1}/{len(variants)}] ClinVar {chrom}:{pos} {ref}>{alt}")
            cv = query_clinvar(chrom, pos, ref, alt)
            ann["significance"] = cv.get("significance", "Unknown")
            ann["gene"]         = cv.get("gene", v.get("gene", ""))
            ann["hgvs"]         = cv.get("hgvs", "")
            ann["rsid"]         = cv.get("rsid", v.get("id", "."))
            time.sleep(0.35)  # NCBI rate limit: 3 req/s

            # 2. gnomAD — population allele frequency + gene fallback + HGVS supplement
            append_log(job_id, f"  [{i+1}/{len(variants)}] gnomAD {chrom}:{pos}")
            gn = query_gnomad(chrom, pos, ref, alt, dataset=gnomad_dataset)
            if gn.get("af") is not None:
                ann["af"] = gn["af"]
            if gn.get("af_popmax") is not None:
                ann["af_popmax"] = gn["af_popmax"]
            if not ann["gene"] and gn.get("gene"):
                ann["gene"] = gn["gene"]
            # gnomAD rsids take priority if ClinVar didn't find one
            if ann["rsid"] in (".", "", None) and gn.get("rsids"):
                ann["rsid"] = gn["rsids"][0]
            if not ann["hgvs"]:
                ann["hgvs"] = gn.get("hgvsc") or gn.get("hgvsp") or ""

            # 3. dbSNP — rsID last resort
            if ann["rsid"] in (".", "", None):
                snp = query_dbsnp(chrom, pos)
                ann["rsid"] = snp.get("rsid", ".")
                time.sleep(0.35)

            # 4. CancerHotspots — cancer driver overlay
            if ann["gene"]:
                hs = query_cancer_hotspots(ann["gene"])
                ann["hotspot"]      = hs.get("is_hotspot", False)
                ann["hotspot_type"] = hs.get("hotspot_type")
                time.sleep(0.35)
            else:
                ann["hotspot"] = False

            # 5. AF from VCF INFO field if gnomAD returned nothing
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

        pathogenic    = sum(1 for a in annotated if "pathogenic" in a.get("significance", "").lower())
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
