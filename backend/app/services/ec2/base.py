from abc import ABC, abstractmethod


class EC2Backend(ABC):
    @abstractmethod
    def spawn_instance(self, tier: str) -> str:
        """Spawn an instance for the given tier. Returns instance ID."""

    @abstractmethod
    def terminate_instance(self, instance_id: str) -> None:
        """Terminate the given instance."""


def get_ec2_backend() -> EC2Backend:
    from app.config import settings

    if settings.EC2_BACKEND == "mock":
        from app.services.ec2.mock import MockEC2Backend
        return MockEC2Backend()

    raise NotImplementedError(f"EC2 backend '{settings.EC2_BACKEND}' is not implemented.")
