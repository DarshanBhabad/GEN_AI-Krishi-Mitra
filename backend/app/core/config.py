from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("API_KEY", "API_Key")
    )
    base_url: str | None = Field(default=None, validation_alias=AliasChoices("BASE_URL", "URL"))
    model_id: str | None = Field(default=None, validation_alias="MODEL_ID")
    embedding_model_id: str | None = Field(default=None, validation_alias="EMBEDDING_MODEL_ID")
    transcription_model_id: str | None = Field(default=None, validation_alias="TRANSCRIPTION_MODEL_ID")
    tts_model_id: str | None = Field(default=None, validation_alias="TTS_MODEL_ID")
    tts_voice: str | None = Field(default=None, validation_alias="TTS_VOICE")
    database_url: str = Field(
        default=f"sqlite:///{PROJECT_ROOT / 'agri_assistant.db'}",
        validation_alias="DATABASE_URL",
    )
    qdrant_url: str | None = Field(default=None, validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="agri_knowledge", validation_alias="QDRANT_COLLECTION")
    mandi_api_url: str | None = Field(default=None, validation_alias="MANDI_API_URL")
    mandi_api_key: str | None = Field(default=None, validation_alias="MANDI_API_KEY")
    admin_token: str | None = Field(default=None, validation_alias="ADMIN_TOKEN")
    demo_mode: bool = Field(default=True, validation_alias="DEMO_MODE")
    max_upload_mb: int = Field(default=15, validation_alias="MAX_UPLOAD_MB")
    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("max_upload_mb")
    @classmethod
    def validate_upload_size(cls, value: int) -> int:
        if not 1 <= value <= 100:
            raise ValueError("MAX_UPLOAD_MB must be between 1 and 100.")
        return value

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.api_key and self.normalized_base_url and self.model_id)

    @property
    def effective_demo_mode(self) -> bool:
        return self.demo_mode or not self.ai_configured

    @property
    def has_embeddings(self) -> bool:
        return bool(self.api_key and self.normalized_base_url and self.embedding_model_id)

    @property
    def has_asr(self) -> bool:
        return bool(self.api_key and self.normalized_base_url and self.transcription_model_id)

    @property
    def has_tts(self) -> bool:
        return bool(self.api_key and self.normalized_base_url and self.tts_model_id and self.tts_voice)

    @property
    def normalized_base_url(self) -> str | None:
        if not self.base_url:
            return None
        parsed = urlsplit(self.base_url.strip())
        if not parsed.hostname:
            return None
        is_loopback = parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
            return None
        path = parsed.path.rstrip("/")
        suffix = "/chat/completions"
        if path.lower().endswith(suffix):
            path = path[: -len(suffix)]
        return urlunsplit(parsed._replace(path=path))

    def public_capabilities(self) -> dict[str, Any]:
        return {
            "mode": "demo" if self.effective_demo_mode else "live",
            "chat_model_configured": self.ai_configured,
            "embeddings_configured": self.has_embeddings,
            "speech_recognition_configured": self.has_asr,
            "speech_synthesis_configured": self.has_tts,
            "qdrant_configured": bool(self.qdrant_url),
            "mandi_api_configured": bool(self.mandi_api_url),
            "weather_provider": "Open-Meteo",
            "supported_languages": ["hi", "mr"],
            "admin_auth_required": bool(self.admin_token),
        }


def load_settings() -> Settings:
    return Settings()


settings = load_settings()
