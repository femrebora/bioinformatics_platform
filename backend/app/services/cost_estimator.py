from dataclasses import dataclass

MB = 1024 * 1024
GB = 1024 * MB

TIER_CONFIG = {
    "small":  {"instance_type": "t3.small",   "cost_usd": 0.25, "rationale": "Files under 200 MB use a small tier."},
    "medium": {"instance_type": "t3.medium",  "cost_usd": 0.85, "rationale": "Files 200 MB–2 GB use a medium tier."},
    "large":  {"instance_type": "c5.2xlarge", "cost_usd": 3.50, "rationale": "Files over 2 GB use a large tier."},
}


@dataclass
class TierEstimate:
    tier: str
    instance_type: str
    cost_usd: float
    rationale: str


def estimate(file_size_bytes: int) -> TierEstimate:
    if file_size_bytes < 200 * MB:
        key = "small"
    elif file_size_bytes <= 2 * GB:
        key = "medium"
    else:
        key = "large"

    cfg = TIER_CONFIG[key]
    return TierEstimate(
        tier=key,
        instance_type=cfg["instance_type"],
        cost_usd=cfg["cost_usd"],
        rationale=cfg["rationale"],
    )
