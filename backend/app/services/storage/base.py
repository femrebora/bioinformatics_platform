from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def generate_upload_url(self, storage_key: str) -> str:
        """Return a URL the client will PUT the file to."""

    @abstractmethod
    def file_path(self, storage_key: str) -> str:
        """Return the local or remote path/URI where the file lives."""


def get_storage_backend() -> StorageBackend:
    from app.config import settings

    if settings.STORAGE_BACKEND == "local":
        from app.services.storage.local import LocalStorageBackend
        return LocalStorageBackend()

    raise NotImplementedError(f"Storage backend '{settings.STORAGE_BACKEND}' is not implemented.")
