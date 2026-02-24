from abc import ABC, abstractmethod


class HLARunner(ABC):
    @abstractmethod
    def run(self, file_path: str, file_type: str) -> dict:
        """Run HLA typing and return the result dict."""


def get_hla_runner() -> HLARunner:
    from app.config import settings

    if settings.HLA_BACKEND == "mock":
        from app.services.hla.mock import MockHLARunner
        return MockHLARunner()

    raise NotImplementedError(f"HLA backend '{settings.HLA_BACKEND}' is not implemented.")
