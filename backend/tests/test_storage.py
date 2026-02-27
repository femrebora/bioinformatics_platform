"""Unit tests for storage backends.

LocalStorageBackend: tested directly (creates a temp dir to avoid touching /uploads).
StorageBackend base: tests the default generate_download_url returns None.
get_storage_backend: tests factory function routing.
"""
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock


# ── LocalStorageBackend ───────────────────────────────────────────────────


class TestLocalStorageBackend:
    @pytest.fixture
    def backend(self, tmp_path):
        """Create a LocalStorageBackend pointing at a temp directory."""
        from app.services.storage.local import LocalStorageBackend

        with (
            patch("app.services.storage.local.settings") as mock_settings,
        ):
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            backend = LocalStorageBackend()
        # Store mock settings on the backend so generate_upload_url can read them
        # (LocalStorageBackend reads from settings at call time, not at init time)
        yield backend, str(tmp_path)

    def test_init_creates_upload_dir(self, tmp_path):
        from app.services.storage.local import LocalStorageBackend

        upload_dir = tmp_path / "uploads_sub"
        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(upload_dir)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            LocalStorageBackend()
        assert upload_dir.exists()

    def test_generate_upload_url_returns_string(self, tmp_path):
        from app.services.storage.local import LocalStorageBackend

        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            backend = LocalStorageBackend()
            url = backend.generate_upload_url("uploads/user/sample.fastq.gz")

        assert isinstance(url, str)
        assert "sample.fastq.gz" in url

    def test_generate_upload_url_uses_base_url(self, tmp_path):
        from app.services.storage.local import LocalStorageBackend

        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://myserver:9999"
            backend = LocalStorageBackend()
            url = backend.generate_upload_url("uploads/user/file.bam")

        assert url.startswith("http://myserver:9999")

    def test_generate_upload_url_extracts_basename(self, tmp_path):
        from app.services.storage.local import LocalStorageBackend

        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            backend = LocalStorageBackend()
            url = backend.generate_upload_url("some/deep/path/file.vcf")

        # Only the basename should appear in the URL, not the full path
        assert "file.vcf" in url
        assert "some/deep/path" not in url

    def test_file_path_returns_local_path(self, tmp_path):
        from app.services.storage.local import LocalStorageBackend

        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            backend = LocalStorageBackend()
            path = backend.file_path("uploads/user/data.fastq.gz")

        assert path.startswith(str(tmp_path))
        assert path.endswith("data.fastq.gz")

    def test_file_path_strips_directory_components(self, tmp_path):
        from app.services.storage.local import LocalStorageBackend

        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            backend = LocalStorageBackend()
            path = backend.file_path("a/b/c/filename.bam")

        assert os.path.basename(path) == "filename.bam"

    def test_generate_download_url_returns_none(self, tmp_path):
        """Local backend does not support presigned download URLs."""
        from app.services.storage.local import LocalStorageBackend

        with patch("app.services.storage.local.settings") as mock_settings:
            mock_settings.UPLOADS_DIR = str(tmp_path)
            mock_settings.PUBLIC_BASE_URL = "http://testserver:8000"
            backend = LocalStorageBackend()

        result = backend.generate_download_url("some/path/file.bam")
        assert result is None


# ── StorageBackend base (abstract) ────────────────────────────────────────


class TestStorageBackendBase:
    def test_generate_download_url_default_returns_none(self):
        """Base class generate_download_url returns None by default."""
        from app.services.storage.base import StorageBackend

        class ConcreteBackend(StorageBackend):
            def generate_upload_url(self, storage_key: str) -> str:
                return "http://example.com/upload"

            def file_path(self, storage_key: str) -> str:
                return f"/tmp/{storage_key}"

        backend = ConcreteBackend()
        assert backend.generate_download_url("some/path") is None

    def test_generate_download_url_expiry_param_accepted(self):
        from app.services.storage.base import StorageBackend

        class ConcreteBackend(StorageBackend):
            def generate_upload_url(self, storage_key: str) -> str:
                return ""

            def file_path(self, storage_key: str) -> str:
                return ""

        backend = ConcreteBackend()
        # Should not raise
        result = backend.generate_download_url("path", expiry=7200)
        assert result is None


# ── get_storage_backend factory ───────────────────────────────────────────


class TestGetStorageBackend:
    def test_local_backend_returned_by_default(self):
        from app.services.storage.base import get_storage_backend
        from app.services.storage.local import LocalStorageBackend

        # settings is imported inside get_storage_backend(), patch it at source
        with (
            patch("app.config.settings") as mock_settings,
            patch("app.services.storage.local.settings") as mock_local_settings,
        ):
            mock_settings.STORAGE_BACKEND = "local"
            mock_local_settings.UPLOADS_DIR = "/tmp/test_uploads"
            mock_local_settings.PUBLIC_BASE_URL = "http://localhost:8000"
            backend = get_storage_backend()

        assert isinstance(backend, LocalStorageBackend)

    def test_s3_backend_returned_when_configured(self):
        from app.services.storage.base import get_storage_backend
        from app.services.storage.s3 import S3StorageBackend

        with patch("app.config.settings") as mock_settings:
            mock_settings.STORAGE_BACKEND = "s3"
            backend = get_storage_backend()

        assert isinstance(backend, S3StorageBackend)
