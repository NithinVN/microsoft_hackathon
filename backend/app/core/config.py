from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration for IncidentMind application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application settings
    APP_NAME: str = "IncidentMind"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    FRONTEND_PORT: int = 5173
    LOG_LEVEL: str = "INFO"

    # CORS configuration
    ALLOWED_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Groq LLM Configuration
    GROQ_API_KEY: str = Field(default="", description="API Key for Groq cloud API")
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-120b",
        description="Configurable LLM model, preferring openai/gpt-oss-120b per architectural requirement",
    )
    GROQ_TEMPERATURE: float = 0.1
    GROQ_MAX_RETRIES: int = 3

    # Hindsight Cloud Configuration (Persistent Organizational Memory Layer)
    HINDSIGHT_BASE_URL: str = Field(
        default="https://api.hindsight.cloud",
        description="Base URL for Hindsight Cloud API",
    )
    HINDSIGHT_API_URL: str = Field(
        default="https://api.hindsight.cloud",
        description="Alias for HINDSIGHT_BASE_URL for backward compatibility",
    )
    HINDSIGHT_API_KEY: str = Field(
        default="",
        description="API Key for Hindsight Cloud",
    )
    HINDSIGHT_BANK_ID: str = Field(
        default="incidentmind-memory",
        description="Memory bank identifier in Hindsight",
    )
    HINDSIGHT_WORKSPACE_ID: str = "incidentmind-org"
    HINDSIGHT_TIMEOUT_SECONDS: float = 10.0
    HINDSIGHT_MAX_RETRIES: int = 3

    # Database Configuration (PostgreSQL state storage)
    DATABASE_URL: str = "postgresql+asyncpg://incidentmind:incidentmind@localhost:5432/incidentmind_db"
    POSTGRES_USER: str = "incidentmind"
    POSTGRES_PASSWORD: str = "incidentmind"
    POSTGRES_DB: str = "incidentmind_db"
    POSTGRES_PORT: int = 5432

    # RAG Reference Documentation Configuration
    RAG_DATA_DIR: str = "./data/runbooks"

    # Incident Simulator Configuration
    SIMULATOR_DETERMINISTIC: bool = True


settings = Settings()
