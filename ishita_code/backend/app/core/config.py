from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

_INSECURE_SECRET_MARKERS = {
    "",
    "sentinel-super-secret-key-change-in-production-2026-sih",
    "change-me",
}

class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    PROJECT_NAME: str = "SENTINEL Cybersecurity Content Intelligence"
    API_V1_STR: str = "/api"
    # A production key is deliberately never embedded in source. Development
    # deployments should set this in backend/.env too, so sessions survive a restart.
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # SQLite default, or PostgreSQL if configured
    DATABASE_URL: str = f"sqlite:///{DATA_DIR.as_posix()}/sentinel.db"
    
    # Ollama Instance Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gpt-oss:120b-cloud"
    OLLAMA_TIMEOUT_SECONDS: float = 180.0
    # Bounded retries for transient transport/gateway errors
    OLLAMA_MAX_RETRIES: int = 2

    # Max upload size: 10 MiB unless a deployment explicitly opts into more.
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024

    # Production settings are intentionally explicit. Comma-separated values
    # keep .env files readable without relying on JSON environment values.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True
    PUBLIC_APP_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", ".env"),
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY in _INSECURE_SECRET_MARKERS or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be an explicitly configured, high-entropy value of at least 32 characters in production.")
            origins = self.cors_origins
            if not origins or any(origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1") for origin in origins):
                raise ValueError("CORS_ORIGINS must list explicit production origins when ENVIRONMENT=production.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)

settings = Settings()
