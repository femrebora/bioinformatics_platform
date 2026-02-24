import os
from app.services.storage.base import StorageBackend
from app.config import settings


class LocalStorageBackend(StorageBackend):
    def __init__(self):
        os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

    def generate_upload_url(self, storage_key: str) -> str:
        filename = os.path.basename(storage_key)
        return f"{settings.PUBLIC_BASE_URL}/api/v1/uploads/local/{filename}"

    def file_path(self, storage_key: str) -> str:
        return os.path.join(settings.UPLOADS_DIR, os.path.basename(storage_key))
