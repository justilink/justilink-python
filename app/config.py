from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "JustiLink"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = "JustiLink_Secret_Pilote_2026_Quebec"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    DATABASE_URL: str = "sqlite:///./justlink.db"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: list = ["pdf", "docx", "xlsx", "png", "jpg", "jpeg"]

    CORS_ORIGINS: list = [
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    SEUIL_REVENU_1_PERSONNE: float = 22000.0
    SEUIL_REVENU_PAR_CHARGE: float = 4500.0
    SEUIL_ACTIF_MAX: float = 15000.0

    GREFFE_EMAIL: str = "greffe@tribunal-longueuil.gouv.qc.ca"
    DELAI_TRANSMISSION_HEURES: int = 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
