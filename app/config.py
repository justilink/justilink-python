import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,   # ← NE PAS lire .env en production
        extra="ignore",
    )

    # Base de données — Railway injecte DATABASE_URL automatiquement
    DATABASE_URL: str = "sqlite:///./justlink.db"

    # Application
    APP_NAME: str = "JustiLink"
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str = "changez-moi-en-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10_485_760

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    def model_post_init(self, __context):
        # Convertir postgres:// → postgresql:// (Railway utilise l'ancien format)
        if self.DATABASE_URL.startswith("postgres://"):
            object.__setattr__(
                self,
                "DATABASE_URL",
                self.DATABASE_URL.replace("postgres://", "postgresql://", 1),
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

