from abc import ABC, abstractmethod


class NextflowRunner(ABC):
    @abstractmethod
    def run(self, pipeline_id: str, storage_key: str, file_type: str) -> dict:
        """Run the specified nf-core pipeline and return the result dict."""


def get_nextflow_runner() -> NextflowRunner:
    from app.config import settings

    if settings.NEXTFLOW_BACKEND == "mock":
        from app.services.nextflow.mock import MockNextflowRunner
        return MockNextflowRunner()

    raise NotImplementedError(
        f"Nextflow backend '{settings.NEXTFLOW_BACKEND}' is not implemented."
    )
