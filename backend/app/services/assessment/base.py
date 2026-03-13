from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AssessmentResult:
    summary: str
    variants: list[dict] = field(default_factory=list)
    report_path: str | None = None


class AssessmentRunner(ABC):
    @abstractmethod
    def run(self, job_id: str, vcf_path: str) -> AssessmentResult:
        """Cross-reference VCF variants against mutation databases."""


def get_assessment_runner() -> AssessmentRunner:
    from .mock import MockAssessmentRunner
    return MockAssessmentRunner()
