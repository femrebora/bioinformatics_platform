from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://bioplatform:bioplatform@postgres:5432/bioplatform"

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # Backend injection via env vars
    STORAGE_BACKEND: str = "local"       # local | s3
    EC2_BACKEND: str = "mock"            # mock | aws
    HLA_BACKEND: str = "mock"            # mock | hlahd
    NEXTFLOW_BACKEND: str = "mock"       # mock | nextflow

    # Local uploads directory
    UPLOADS_DIR: str = "/uploads"

    # Public base URL for generating upload URLs
    PUBLIC_BASE_URL: str = "http://localhost:8000"


settings = Settings()
