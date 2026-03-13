"""Real assessment runner — Franklin (primary) + ClinVar / dbSNP / CancerHotspots."""
import logging
import os
import time

from app.config import settings
from app.services.assessment.base import AssessmentResult, AssessmentRunner
from app.services.assessment.databases import (
    query_cancer_hotspots,
    query_clinvar,
    query_dbsnp,
    query_franklin,
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
        use_franklin = bool(settings.FRANKLIN_API_KEY)
        append_log(
            job_id,
            f"Starting annotation of {len(variants)} variant(s) "
            f"[primary source: {'Franklin by Genoox' if use_franklin else 'ClinVar (no Franklin key)'}]",
        )
        annotated: list[dict] = []

        for i, v in enumerate(variants):
            ann = dict(v)
            chrom = v.get("chrom", "")
            pos   = v.get("pos", 0)
            ref   = v.get("ref", "")
            alt   = v.get("alt", "")

            # 1. Franklin by Genoox — primary source (ACMG classification, gene, gnomAD AF)
            if use_franklin:
                append_log(job_id, f"  [{i+1}/{len(variants)}] Franklin: {chrom}:{pos} {ref}>{alt}")
                fr = query_franklin(chrom, pos, ref, alt)
                ann["significance"] = fr.get("classification") or "Unknown"
                ann["gene"]         = fr.get("gene") or v.get("gene", "")
                ann["hgvs"]         = fr.get("hgvs", "")
                ann["condition"]    = fr.get("condition", "")
                ann["acmg_criteria"] = fr.get("acmg_criteria", [])
                if fr.get("gnomad_af") is not None:
                    ann["af"] = fr["gnomad_af"]

            # 2. ClinVar — fallback classification when Franklin key absent, or supplement
            if not use_franklin or ann["significance"] == "Unknown":
                append_log(job_id, f"  [{i+1}/{len(variants)}] ClinVar: {chrom}:{pos}")
                cv = query_clinvar(chrom, pos, ref, alt)
                if not use_franklin:
                    ann["significance"] = cv.get("significance", "Unknown")
                    ann["gene"]         = cv.get("gene", v.get("gene", ""))
                    ann["rsid"]         = cv.get("rsid", v.get("id", "."))
                elif cv.get("significance") and cv["significance"] != "Unknown":
                    # Franklin returned Unknown — use ClinVar as fallback
                    ann["significance"] = cv["significance"]
                    if not ann["gene"]:
                        ann["gene"] = cv.get("gene", "")
                time.sleep(0.35)  # NCBI rate limit

            # 3. dbSNP — rsID if not already set
            if ann.get("rsid", ".") in (".", "", None):
                snp = query_dbsnp(chrom, pos)
                ann["rsid"] = snp.get("rsid", ".")
                time.sleep(0.35)

            # 4. CancerHotspots — cancer driver overlay (gene-level)
            if ann.get("gene"):
                hs = query_cancer_hotspots(ann["gene"])
                ann["hotspot"]      = hs.get("is_hotspot", False)
                ann["hotspot_type"] = hs.get("hotspot_type")
                time.sleep(0.35)
            else:
                ann["hotspot"] = False

            # 5. Population AF from VCF INFO field if not set by Franklin
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
