"""Pipeline-aware cost estimator.

Cost formula:
    raw_compute = (base_hours + n_samples * per_sample_hours) * instance_rate_usd_per_hr
    total       = raw_compute * overhead_multiplier * MARGIN_MULTIPLIER

overhead_multiplier: covers S3, EBS, AWS Batch, app infrastructure (~1.3–1.45×)
MARGIN_MULTIPLIER:   targets ~65% gross margin (≈ 2.86×)

Benchmarks are based on nf-core community reports and AWS on-demand pricing.
Spot instances typically run 60–70% cheaper; on-demand rates are used here as
a conservative upper bound that also buffers against spot interruption retries.
"""
from dataclasses import dataclass

# ── Margin ────────────────────────────────────────────────────────────────

GROSS_MARGIN_TARGET = 0.65          # 65% gross margin
MARGIN_MULTIPLIER   = 1.0 / (1.0 - GROSS_MARGIN_TARGET)   # ≈ 2.857×

# ── Per-pipeline pricing table ────────────────────────────────────────────
# instance_rate: on-demand USD/hr (us-east-1, 2025)
# base_hours:       fixed overhead per job (reference index, pipeline setup)
# per_sample_hours: marginal time per biological sample
# overhead:         multiplier for S3, EBS, Batch, app infra

PIPELINE_PRICING: dict[str, dict] = {
    "rnaseq": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       0.50,
        "per_sample_hours": 0.75,
        "overhead":         1.35,
        "description":      "RNA-seq alignment & quantification (STAR/Salmon)",
    },
    "sarek": {
        "instance_type":    "c5.4xlarge",
        "instance_rate":    0.68,
        "base_hours":       1.00,
        "per_sample_hours": 2.50,
        "overhead":         1.40,
        "description":      "Germline variant calling — WGS/WES (GATK4)",
    },
    "atacseq": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       0.33,
        "per_sample_hours": 0.50,
        "overhead":         1.30,
        "description":      "ATAC-seq peak calling (MACS3)",
    },
    "chipseq": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       0.33,
        "per_sample_hours": 0.50,
        "overhead":         1.30,
        "description":      "ChIP-seq peak calling (MACS3)",
    },
    "methylseq": {
        "instance_type":    "c5.4xlarge",
        "instance_rate":    0.68,
        "base_hours":       0.50,
        "per_sample_hours": 2.00,
        "overhead":         1.35,
        "description":      "Bisulfite methylation sequencing (Bismark)",
    },
    "ampliseq": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       0.25,
        "per_sample_hours": 0.33,
        "overhead":         1.25,
        "description":      "16S/ITS amplicon sequencing (DADA2/QIIME2)",
    },
    "fetchngs": {
        "instance_type":    "t3.large",
        "instance_rate":    0.083,
        "base_hours":       0.17,
        "per_sample_hours": 0.25,
        "overhead":         1.20,
        "description":      "SRA/ENA data download",
    },
    "snakemake": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       0.50,
        "per_sample_hours": 1.00,
        "overhead":         1.35,
        "description":      "Snakemake workflow",
    },
    "mixed": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       1.00,
        "per_sample_hours": 1.50,
        "overhead":         1.40,
        "description":      "Cross-framework pipeline (Nextflow + Snakemake)",
    },
    "nf-core-modules": {
        "instance_type":    "c5.2xlarge",
        "instance_rate":    0.34,
        "base_hours":       0.50,
        "per_sample_hours": 0.50,
        "overhead":         1.30,
        "description":      "Custom nf-core module pipeline",
    },
}

# ── File-size fallback (unknown or null pipeline) ─────────────────────────
# Used when pipeline_id is absent or not in PIPELINE_PRICING.

MB = 1024 * 1024
GB = 1024 * MB

_SIZE_FALLBACK = [
    (200 * MB,  "small",  "t3.medium",  "Small job (<200 MB input)"),
    (2   * GB,  "medium", "c5.2xlarge", "Medium job (200 MB–2 GB input)"),
    (None,      "large",  "c5.4xlarge", "Large job (>2 GB input)"),
]

_FALLBACK_BASE_COST = {"small": 0.49, "medium": 1.99, "large": 5.99}

# ── Tier derivation ───────────────────────────────────────────────────────

def _tier_from_cost(cost: float) -> str:
    if cost < 1.50:
        return "small"
    if cost < 6.00:
        return "medium"
    return "large"


# ── Output dataclass ──────────────────────────────────────────────────────

@dataclass
class TierEstimate:
    tier: str
    instance_type: str
    cost_usd: float
    rationale: str
    estimated_hours: float
    pipeline_description: str


# ── Public API ────────────────────────────────────────────────────────────

def estimate(
    file_size_bytes: int,
    pipeline_id: str | None = None,
    n_samples: int = 1,
) -> TierEstimate:
    """Return a cost estimate with 65% gross margin baked in.

    Args:
        file_size_bytes: Raw input file size (used for fallback only).
        pipeline_id:     nf-core/Snakemake pipeline key, or None for unknown/generic.
        n_samples:       Number of biological samples (biggest cost driver).
    """
    n_samples = max(1, int(n_samples))

    pid = (pipeline_id or "").lower().removeprefix("nf-core/")

    if pid in PIPELINE_PRICING:
        cfg = PIPELINE_PRICING[pid]
        hours = cfg["base_hours"] + n_samples * cfg["per_sample_hours"]
        raw   = hours * cfg["instance_rate"] * cfg["overhead"]
        cost  = round(raw * MARGIN_MULTIPLIER, 2)
        tier  = _tier_from_cost(cost)

        sample_word = "sample" if n_samples == 1 else "samples"
        rationale = (
            f"{cfg['description']}. "
            f"Estimated {hours:.1f} hrs on {cfg['instance_type']} "
            f"for {n_samples} {sample_word} "
            f"(includes compute, storage & platform overhead)."
        )
        return TierEstimate(
            tier=tier,
            instance_type=cfg["instance_type"],
            cost_usd=cost,
            rationale=rationale,
            estimated_hours=round(hours, 1),
            pipeline_description=cfg["description"],
        )

    # Fallback: file-size tiers for null/unknown pipeline_id
    _FALLBACK_HOURS = {"small": 0.5, "medium": 2.0, "large": 6.0}
    for max_bytes, size_key, instance_type, desc in _SIZE_FALLBACK:
        if max_bytes is None or file_size_bytes <= max_bytes:
            base = _FALLBACK_BASE_COST[size_key]
            cost = round(base * MARGIN_MULTIPLIER, 2)
            return TierEstimate(
                tier=size_key,
                instance_type=instance_type,
                cost_usd=cost,
                rationale=f"{desc}. Select a pipeline for a more accurate estimate.",
                estimated_hours=_FALLBACK_HOURS[size_key],
                pipeline_description="Generic bioinformatics job",
            )

    # Should never reach here
    return TierEstimate(
        tier="large",
        instance_type="c5.4xlarge",
        cost_usd=round(_FALLBACK_BASE_COST["large"] * MARGIN_MULTIPLIER, 2),
        rationale="Large job (>2 GB input).",
        estimated_hours=8.0,
        pipeline_description="Generic bioinformatics job",
    )
