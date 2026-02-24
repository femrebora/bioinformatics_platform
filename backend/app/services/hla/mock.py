import hashlib
import random
import time

from app.services.hla.base import HLARunner

# Deterministic allele pools — seeded from filename hash so same file → same result
HLA_A_ALLELES = ["A*01:01", "A*02:01", "A*03:01", "A*11:01", "A*24:02", "A*29:02", "A*31:01", "A*33:01"]
HLA_B_ALLELES = ["B*07:02", "B*08:01", "B*15:01", "B*27:05", "B*35:01", "B*40:01", "B*44:02", "B*51:01"]
HLA_C_ALLELES = ["C*01:02", "C*03:04", "C*04:01", "C*05:01", "C*06:02", "C*07:01", "C*07:02", "C*08:02"]

TIER_INSTANCE_MAP = {
    "small":  "t3.small",
    "medium": "t3.medium",
    "large":  "c5.2xlarge",
}


def _seed_from_filename(filename: str) -> int:
    digest = hashlib.md5(filename.encode()).hexdigest()
    return int(digest[:8], 16)


class MockHLARunner(HLARunner):
    def run(self, file_path: str, file_type: str) -> dict:
        start = time.time()
        delay = random.uniform(3.0, 8.0)
        time.sleep(delay)
        runtime = int(time.time() - start)

        seed = _seed_from_filename(file_path)
        rng = random.Random(seed)

        def pick2(pool):
            idxs = rng.sample(range(len(pool)), 2)
            return pool[idxs[0]], pool[idxs[1]]

        a1, a2 = pick2(HLA_A_ALLELES)
        b1, b2 = pick2(HLA_B_ALLELES)
        c1, c2 = pick2(HLA_C_ALLELES)

        return {
            "hla_alleles": [
                {"gene": "HLA-A", "allele_1": a1, "allele_2": a2},
                {"gene": "HLA-B", "allele_1": b1, "allele_2": b2},
                {"gene": "HLA-C", "allele_1": c1, "allele_2": c2},
            ],
            "instance_type": "t3.medium",
            "runtime_seconds": runtime,
        }
