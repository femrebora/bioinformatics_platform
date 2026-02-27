"""Unit tests for the cost estimator service."""
import pytest
from app.services.cost_estimator import (
    estimate,
    TierEstimate,
    PIPELINE_PRICING,
    MARGIN_MULTIPLIER,
    MB,
    GB,
)


class TestEstimateKnownPipeline:
    """Tests for pipelines listed in PIPELINE_PRICING."""

    def test_rnaseq_1_sample_returns_tier_estimate(self):
        result = estimate(file_size_bytes=500 * MB, pipeline_id="rnaseq", n_samples=1)
        assert isinstance(result, TierEstimate)
        assert result.instance_type == "c5.2xlarge"
        assert result.cost_usd > 0
        assert result.estimated_hours > 0
        assert "RNA-seq" in result.pipeline_description

    def test_rnaseq_cost_increases_with_samples(self):
        one = estimate(500 * MB, "rnaseq", n_samples=1)
        ten = estimate(500 * MB, "rnaseq", n_samples=10)
        assert ten.cost_usd > one.cost_usd

    def test_sarek_is_more_expensive_than_rnaseq(self):
        rnaseq = estimate(500 * MB, "rnaseq", n_samples=1)
        sarek  = estimate(500 * MB, "sarek",  n_samples=1)
        assert sarek.cost_usd > rnaseq.cost_usd

    def test_all_known_pipelines_return_positive_cost(self):
        for pid in PIPELINE_PRICING:
            result = estimate(100 * MB, pipeline_id=pid, n_samples=1)
            assert result.cost_usd > 0, f"Pipeline {pid!r} returned non-positive cost"
            assert result.instance_type != ""
            assert result.rationale != ""

    def test_pipeline_id_case_insensitive(self):
        lower = estimate(100 * MB, "rnaseq")
        upper = estimate(100 * MB, "RNASEQ")
        assert lower.cost_usd == upper.cost_usd

    def test_nf_core_prefix_stripped(self):
        with_prefix    = estimate(100 * MB, "nf-core/rnaseq")
        without_prefix = estimate(100 * MB, "rnaseq")
        assert with_prefix.cost_usd == without_prefix.cost_usd

    def test_n_samples_clamped_to_minimum_1(self):
        zero = estimate(100 * MB, "rnaseq", n_samples=0)
        one  = estimate(100 * MB, "rnaseq", n_samples=1)
        assert zero.cost_usd == one.cost_usd

    def test_margin_applied(self):
        """Cost should reflect MARGIN_MULTIPLIER."""
        cfg   = PIPELINE_PRICING["rnaseq"]
        hours = cfg["base_hours"] + 1 * cfg["per_sample_hours"]
        raw   = hours * cfg["instance_rate"] * cfg["overhead"]
        expected = round(raw * MARGIN_MULTIPLIER, 2)
        result = estimate(100 * MB, "rnaseq", n_samples=1)
        assert result.cost_usd == expected

    def test_tier_small_when_cost_below_1_50(self):
        # fetchngs with 1 sample should be cheap (small tier)
        result = estimate(1 * MB, "fetchngs", n_samples=1)
        # cost < 1.50 → "small"
        if result.cost_usd < 1.50:
            assert result.tier == "small"

    def test_tier_large_for_sarek_many_samples(self):
        result = estimate(5 * GB, "sarek", n_samples=10)
        assert result.tier == "large"


class TestEstimateFallback:
    """Tests for null/unknown pipeline_id — file-size fallback."""

    def test_none_pipeline_uses_fallback(self):
        result = estimate(10 * MB, pipeline_id=None)
        assert isinstance(result, TierEstimate)
        assert result.cost_usd > 0

    def test_unknown_pipeline_uses_fallback(self):
        result = estimate(10 * MB, pipeline_id="not-a-real-pipeline")
        assert isinstance(result, TierEstimate)
        assert result.cost_usd > 0

    def test_small_file_gets_small_tier(self):
        result = estimate(50 * MB, pipeline_id=None)
        assert result.tier == "small"
        assert result.instance_type == "t3.medium"

    def test_medium_file_gets_medium_tier(self):
        result = estimate(500 * MB, pipeline_id=None)
        assert result.tier == "medium"

    def test_large_file_gets_large_tier(self):
        result = estimate(5 * GB, pipeline_id=None)
        assert result.tier == "large"
        assert result.instance_type == "c5.4xlarge"

    def test_fallback_rationale_mentions_pipeline(self):
        result = estimate(10 * MB, pipeline_id=None)
        assert "pipeline" in result.rationale.lower()

    def test_fallback_costs_include_margin(self):
        """Fallback costs should also include MARGIN_MULTIPLIER."""
        from app.services.cost_estimator import _FALLBACK_BASE_COST
        result = estimate(10 * MB, pipeline_id=None)  # small tier
        expected = round(_FALLBACK_BASE_COST["small"] * MARGIN_MULTIPLIER, 2)
        assert result.cost_usd == expected


class TestNegativeAndZeroSamples:
    """n_samples ≤ 0 must clamp to 1 for both known and fallback paths."""

    def test_zero_samples_clamps_to_1_known_pipeline(self):
        zero = estimate(100 * MB, "rnaseq", n_samples=0)
        one  = estimate(100 * MB, "rnaseq", n_samples=1)
        assert zero.cost_usd == one.cost_usd
        assert zero.estimated_hours == one.estimated_hours

    def test_negative_samples_clamps_to_1_known_pipeline(self):
        neg = estimate(100 * MB, "rnaseq", n_samples=-5)
        one = estimate(100 * MB, "rnaseq", n_samples=1)
        assert neg.cost_usd == one.cost_usd

    def test_negative_samples_clamps_to_1_fallback(self):
        neg = estimate(10 * MB, pipeline_id=None, n_samples=-99)
        one = estimate(10 * MB, pipeline_id=None, n_samples=1)
        assert neg.cost_usd == one.cost_usd

    def test_zero_samples_clamps_to_1_fallback(self):
        zero = estimate(10 * MB, pipeline_id=None, n_samples=0)
        one  = estimate(10 * MB, pipeline_id=None, n_samples=1)
        assert zero.cost_usd == one.cost_usd

    def test_rationale_shows_singular_sample_when_clamped(self):
        result = estimate(100 * MB, "rnaseq", n_samples=0)
        assert "1 sample" in result.rationale


class TestPipelineIdEdgeCases:
    """Unknown, null, empty, and prefixed pipeline_id inputs."""

    def test_null_pipeline_id_uses_fallback(self):
        result = estimate(50 * MB, pipeline_id=None)
        assert result.pipeline_description == "Generic bioinformatics job"

    def test_empty_string_pipeline_id_uses_fallback(self):
        result = estimate(50 * MB, pipeline_id="")
        assert result.pipeline_description == "Generic bioinformatics job"

    def test_unknown_pipeline_id_uses_fallback(self):
        result = estimate(50 * MB, pipeline_id="totally-unknown-xyz")
        assert result.pipeline_description == "Generic bioinformatics job"
        assert result.cost_usd > 0

    def test_nf_core_prefix_lowercase_stripped(self):
        prefixed   = estimate(100 * MB, "nf-core/rnaseq")
        plain      = estimate(100 * MB, "rnaseq")
        assert prefixed.cost_usd == plain.cost_usd
        assert prefixed.instance_type == plain.instance_type

    def test_nf_core_prefix_mixed_case_stripped(self):
        # pipeline_id is lowercased before prefix removal
        result = estimate(100 * MB, "nf-core/RNASEQ")
        plain  = estimate(100 * MB, "rnaseq")
        assert result.cost_usd == plain.cost_usd

    def test_case_insensitive_sarek(self):
        lower = estimate(100 * MB, "sarek")
        upper = estimate(100 * MB, "SAREK")
        mixed = estimate(100 * MB, "SaReK")
        assert lower.cost_usd == upper.cost_usd == mixed.cost_usd

    def test_nf_core_only_prefix_not_valid_pipeline(self):
        # "nf-core/" without a pipeline name → empty key → fallback
        result = estimate(50 * MB, pipeline_id="nf-core/")
        assert result.pipeline_description == "Generic bioinformatics job"


class TestFileSizeTierBoundaries:
    """Exact boundary values for the fallback file-size tiers."""

    # Boundary 1: 200 MB  (≤ 200 MB → small, > 200 MB → medium)

    def test_exactly_200_mb_is_small(self):
        result = estimate(200 * MB, pipeline_id=None)
        assert result.tier == "small"
        assert result.instance_type == "t3.medium"

    def test_200_mb_plus_1_byte_is_medium(self):
        result = estimate(200 * MB + 1, pipeline_id=None)
        assert result.tier == "medium"
        assert result.instance_type == "c5.2xlarge"

    # Boundary 2: 2 GB  (≤ 2 GB → medium, > 2 GB → large)

    def test_exactly_2_gb_is_medium(self):
        result = estimate(2 * GB, pipeline_id=None)
        assert result.tier == "medium"

    def test_2_gb_plus_1_byte_is_large(self):
        result = estimate(2 * GB + 1, pipeline_id=None)
        assert result.tier == "large"
        assert result.instance_type == "c5.4xlarge"

    def test_zero_bytes_is_small(self):
        result = estimate(0, pipeline_id=None)
        assert result.tier == "small"

    def test_1_byte_is_small(self):
        result = estimate(1, pipeline_id=None)
        assert result.tier == "small"


class TestTierCostBoundaries:
    """_tier_from_cost thresholds: <1.50 → small, <6.00 → medium, else large."""

    def test_cost_just_below_1_50_is_small(self):
        # fetchngs 1 sample should land in small territory; verify tier logic
        result = estimate(1 * MB, "fetchngs", n_samples=1)
        if result.cost_usd < 1.50:
            assert result.tier == "small"
        else:
            assert result.tier in ("medium", "large")

    def test_tier_small_boundary_is_exclusive_at_150(self):
        """Anything costing exactly $1.50 should be medium, not small."""
        # We can't easily force exactly 1.50 through the formula, but we can
        # verify the boundary condition directly via _tier_from_cost.
        from app.services.cost_estimator import _tier_from_cost
        assert _tier_from_cost(1.499) == "small"
        assert _tier_from_cost(1.50)  == "medium"
        assert _tier_from_cost(5.999) == "medium"
        assert _tier_from_cost(6.00)  == "large"
        assert _tier_from_cost(100.0) == "large"


class TestReturnStructure:
    """TierEstimate fields are always fully populated."""

    @pytest.mark.parametrize("pid", list(PIPELINE_PRICING.keys()))
    def test_known_pipeline_all_fields_populated(self, pid):
        result = estimate(100 * MB, pipeline_id=pid, n_samples=2)
        assert result.tier in ("small", "medium", "large")
        assert result.instance_type
        assert result.cost_usd > 0
        assert result.rationale
        assert result.estimated_hours > 0
        assert result.pipeline_description

    @pytest.mark.parametrize("pid", [None, "", "unknown-xyz"])
    def test_fallback_all_fields_populated(self, pid):
        result = estimate(100 * MB, pipeline_id=pid)
        assert result.tier in ("small", "medium", "large")
        assert result.instance_type
        assert result.cost_usd > 0
        assert result.rationale
        assert result.estimated_hours > 0
        assert result.pipeline_description

    def test_rationale_pluralises_for_multiple_samples(self):
        result = estimate(100 * MB, "rnaseq", n_samples=3)
        assert "3 samples" in result.rationale

    def test_rationale_singular_for_one_sample(self):
        result = estimate(100 * MB, "rnaseq", n_samples=1)
        assert "1 sample" in result.rationale
