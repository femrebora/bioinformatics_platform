"""
Real assessment runner.

Annotation order per variant:
  1. ClinVar        — pathogenicity + gene + HGVS
  2. gnomAD         — population AF + popmax AF
  3. Ensembl VEP    — SIFT, PolyPhen-2, consequence, transcript
  4. CADD           — phred-scaled pathogenicity score
  5. CancerHotspots — cancer driver hotspot flag
  6. dbSNP          — rsID fallback
  7. UniProt        — protein name + function (gene-level, cached)
  8. OMIM           — gene-disease + inheritance (optional, needs API key)
  9. Orphanet       — rare disease associations (optional, needs API key)
"""
import logging
import os
import time
from typing import Any

from app.config import settings
from app.services.assessment.base import AssessmentResult, AssessmentRunner
from app.services.assessment.databases import (
    query_cancer_hotspots,
    query_cadd,
    query_clinvar,
    query_dbsnp,
    query_ensembl_vep,
    query_gnomad,
    query_omim,
    query_orphanet,
    query_uniprot,
)
from app.services.assessment.report import generate_pdf
from app.services.log_streamer import append_log

logger = logging.getLogger(__name__)

_GNOMAD_DATASET = {
    "hg38":   "gnomad_r4",
    "hg19":   "gnomad_r2_1",
    "grch38": "gnomad_r4",
    "grch37": "gnomad_r2_1",
}
_VEP_ASSEMBLY = {
    "hg38":   "GRCh38",
    "hg19":   "GRCh37",
    "grch38": "GRCh38",
    "grch37": "GRCh37",
}
_CADD_GENOME = {
    "gnomad_r4":   "GRCh38-v1.7",
    "gnomad_r2_1": "GRCh37-v1.6",
}


class RealAssessmentRunner(AssessmentRunner):
    def run(
        self,
        job_id: str,
        variants: list[dict],
        workflow_config: dict | None = None,
    ) -> AssessmentResult:
        genome        = (workflow_config or {}).get("genome", settings.ASSESSMENT_GENOME).lower()
        gnomad_ds     = _GNOMAD_DATASET.get(genome, "gnomad_r4")
        vep_assembly  = _VEP_ASSEMBLY.get(genome, "GRCh38")
        cadd_genome   = _CADD_GENOME.get(gnomad_ds, "GRCh38-v1.7")

        has_omim     = bool(settings.OMIM_API_KEY)
        has_orphanet = bool(settings.ORPHANET_API_KEY)

        append_log(
            job_id,
            f"Starting annotation of {len(variants)} variant(s) "
            f"[genome={genome}, gnomAD={gnomad_ds}, OMIM={'yes' if has_omim else 'no key'}, "
            f"Orphanet={'yes' if has_orphanet else 'no key'}]",
        )

        # Gene-level cache — UniProt / OMIM / Orphanet lookups are per-gene not per-variant
        _gene_cache: dict[str, dict[str, Any]] = {}

        annotated: list[dict] = []

        for i, v in enumerate(variants):
            ann = dict(v)
            chrom = v.get("chrom", "")
            pos   = v.get("pos", 0)
            ref   = v.get("ref", "")
            alt   = v.get("alt", "")
            label = f"[{i+1}/{len(variants)}] {chrom}:{pos} {ref}>{alt}"

            # 1. ClinVar
            append_log(job_id, f"  {label} → ClinVar")
            cv = query_clinvar(chrom, pos, ref, alt)
            ann["significance"] = cv.get("significance", "Unknown")
            ann["gene"]         = cv.get("gene", v.get("gene", ""))
            ann["hgvs"]         = cv.get("hgvs", "")
            ann["rsid"]         = cv.get("rsid", v.get("id", "."))
            time.sleep(0.35)

            # 2. gnomAD
            append_log(job_id, f"  {label} → gnomAD")
            gn = query_gnomad(chrom, pos, ref, alt, dataset=gnomad_ds)
            if gn.get("af") is not None:
                ann["af"] = gn["af"]
            if gn.get("af_popmax") is not None:
                ann["af_popmax"] = gn["af_popmax"]
            if not ann["gene"] and gn.get("gene"):
                ann["gene"] = gn["gene"]
            if ann["rsid"] in (".", "", None) and gn.get("rsids"):
                ann["rsid"] = gn["rsids"][0]
            if not ann.get("hgvs"):
                ann["hgvs"] = gn.get("hgvsc") or gn.get("hgvsp") or ""

            # 3. Ensembl VEP — SIFT / PolyPhen / consequence
            append_log(job_id, f"  {label} → Ensembl VEP")
            vep = query_ensembl_vep(chrom, pos, ref, alt, assembly=vep_assembly)
            ann["sift_score"]     = vep.get("sift_score")
            ann["sift_pred"]      = vep.get("sift_pred", "")
            ann["polyphen_score"] = vep.get("polyphen_score")
            ann["polyphen_pred"]  = vep.get("polyphen_pred", "")
            ann["consequence"]    = vep.get("consequence", "")
            ann["transcript"]     = vep.get("transcript", "")
            if not ann["gene"] and vep.get("gene"):
                ann["gene"] = vep["gene"]
            if not ann.get("hgvs") and vep.get("hgvsc"):
                ann["hgvs"] = vep["hgvsc"]

            # 4. CADD
            append_log(job_id, f"  {label} → CADD")
            cadd = query_cadd(chrom, pos, ref, alt, genome=cadd_genome)
            ann["cadd_phred"] = cadd.get("cadd_phred")
            ann["cadd_raw"]   = cadd.get("cadd_raw")

            # 5. CancerHotspots
            if ann["gene"]:
                hs = query_cancer_hotspots(ann["gene"])
                ann["hotspot"]      = hs.get("is_hotspot", False)
                ann["hotspot_type"] = hs.get("hotspot_type")
                time.sleep(0.35)
            else:
                ann["hotspot"] = False

            # 6. dbSNP — rsID last resort
            if ann["rsid"] in (".", "", None):
                snp = query_dbsnp(chrom, pos)
                ann["rsid"] = snp.get("rsid", ".")
                time.sleep(0.35)

            # 7-9. Gene-level lookups (cached across variants with the same gene)
            gene = ann.get("gene", "")
            if gene and gene not in _gene_cache:
                append_log(job_id, f"  gene={gene} → UniProt / OMIM / Orphanet")
                gene_data: dict[str, Any] = {}

                uni = query_uniprot(gene)
                gene_data.update(uni)

                if has_omim:
                    omim = query_omim(gene)
                    gene_data.update(omim)

                if has_orphanet:
                    orpha = query_orphanet(gene)
                    gene_data.update(orpha)

                _gene_cache[gene] = gene_data

            if gene and gene in _gene_cache:
                for k, val in _gene_cache[gene].items():
                    ann.setdefault(k, val)

            # AF from VCF INFO field if gnomAD returned nothing
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
