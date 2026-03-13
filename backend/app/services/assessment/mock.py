import time

from app.services.assessment.base import AssessmentResult, AssessmentRunner


class MockAssessmentRunner(AssessmentRunner):
    """Placeholder assessment runner — returns dummy variant annotations."""

    def run(self, job_id: str, vcf_path: str) -> AssessmentResult:
        time.sleep(1)

        variants = [
            {
                "chrom": "chr17",
                "pos": 7674220,
                "gene": "TP53",
                "hgvs": "p.Arg175His",
                "significance": "Pathogenic",
                "database": "ClinVar",
                "frequency": 0.0001,
            },
            {
                "chrom": "chr13",
                "pos": 32340300,
                "gene": "BRCA2",
                "hgvs": "p.Lys3326Ter",
                "significance": "Likely benign",
                "database": "ClinVar",
                "frequency": 0.014,
            },
            {
                "chrom": "chr7",
                "pos": 55191822,
                "gene": "EGFR",
                "hgvs": "p.Leu858Arg",
                "significance": "Pathogenic",
                "database": "OncoKB",
                "frequency": 0.0003,
            },
        ]

        return AssessmentResult(
            summary=(
                f"Assessment complete for job {job_id}: "
                f"{len(variants)} variants annotated (mock data)."
            ),
            variants=variants,
            report_path=None,
        )
