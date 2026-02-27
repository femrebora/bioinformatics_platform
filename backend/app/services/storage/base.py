from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def generate_upload_url(self, storage_key: str) -> str:
        """Return a URL the client will PUT the file to."""

    @abstractmethod
    def file_path(self, storage_key: str) -> str:
        """Return the local or remote path/URI where the file lives."""

    def generate_download_url(self, path: str, expiry: int = 3600) -> str | None:
        """Return a presigned download URL, or None if not supported."""
        return None

    def delete(self, storage_key: str) -> None:
        """Delete a stored object. No-op by default (local backend keeps files)."""
        pass


def get_storage_backend() -> StorageBackend:
    from app.config import settings

    if settings.STORAGE_BACKEND == "s3":
        from app.services.storage.s3 import S3StorageBackend
        return S3StorageBackend()

    from app.services.storage.local import LocalStorageBackend
    return LocalStorageBackend()
