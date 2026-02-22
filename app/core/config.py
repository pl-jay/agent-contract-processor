from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vendor Contract Compliance Agent"
    environment: str = "development"
    log_level: str = "INFO"

    # Required integration/security settings.
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    database_url: str = Field(default="", alias="DATABASE_URL")
    webhook_secret: str = Field(default="", alias="WEBHOOK_SECRET")
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")
    allowed_origins_raw: str = Field(default="", alias="ALLOWED_ORIGINS")

    # Model identifiers.
    extraction_model: str = Field(default="", alias="EXTRACTION_MODEL")
    validation_model: str = Field(default="", alias="VALIDATION_MODEL")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")

    # Backward-compatible alias support.
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")

    llm_timeout_seconds: int = 60
    extraction_max_retries: int = 3
    validation_max_retries: int = 3
    extraction_max_input_chars: int = Field(default=24000, alias="EXTRACTION_MAX_INPUT_CHARS")

    max_upload_size_bytes: int = Field(default=10485760, alias="MAX_UPLOAD_SIZE_BYTES")
    webhook_sync_timeout_seconds: int = Field(default=30, alias="WEBHOOK_SYNC_TIMEOUT_SECONDS")
    pipeline_workers: int = Field(default=4, alias="PIPELINE_WORKERS")
    webhook_idempotency_enabled: bool = Field(default=True, alias="WEBHOOK_IDEMPOTENCY_ENABLED")

    embedding_device: str = "cpu"
    embedding_cache_dir: Path = Path("./.cache/huggingface")
    embedding_local_files_only: bool = False

    chroma_persist_dir: Path = Path("./chroma_db")
    chroma_collection: str = "vendor_contract_policies"
    policy_dir: Path = Path("./data/policies")
    upload_dir: Path = Path("./tmp_uploads")

    retrieval_k: int = 4
    policy_threshold: float = Field(default=500000.0, alias="POLICY_THRESHOLD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def resolved_database_url(self) -> str:
        return self.database_url.strip()

    @property
    def resolved_llm_api_key(self) -> str:
        if self.llm_api_key.strip():
            return self.llm_api_key.strip()
        return self.anthropic_api_key.strip()

    @property
    def resolved_admin_api_key(self) -> str:
        if self.admin_api_key.strip():
            return self.admin_api_key.strip()
        return self.webhook_secret.strip()

    @property
    def resolved_extraction_model(self) -> str:
        if self.extraction_model.strip():
            return self.extraction_model.strip()
        return self.llm_model.strip()

    @property
    def resolved_validation_model(self) -> str:
        if self.validation_model.strip():
            return self.validation_model.strip()
        return self.resolved_extraction_model

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins_raw.split(",")
            if origin.strip()
        ]

    def missing_required_env_vars(self) -> list[str]:
        missing: list[str] = []

        checks = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "DATABASE_URL": self.database_url,
            "WEBHOOK_SECRET": self.webhook_secret,
            "ALLOWED_ORIGINS": self.allowed_origins_raw,
            "EXTRACTION_MODEL": self.resolved_extraction_model,
            "VALIDATION_MODEL": self.resolved_validation_model,
            "EMBEDDING_MODEL": self.embedding_model,
        }

        for key, value in checks.items():
            if not str(value).strip():
                missing.append(key)

        return missing

    def validate_required(self) -> None:
        missing = self.missing_required_env_vars()
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"Missing required environment variables: {joined}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
