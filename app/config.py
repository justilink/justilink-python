import os
from pydantic_settings import BaseSettings
from functools import lru_cache


def build_database_url() -> str:
    # Priorité 1 : variables PG individuelles (Railway)
    pguser = os.environ.get("PGUSER")
    pgpassword = os.environ.get("PGPASSWORD")
    pghost = os.environ.get("PGHOST")
    pgport = os.environ.get("PGPORT", "5432")
    pgdatabase = os.environ.get("PGDATABASE")

    if all([pguser, pgpassword, pghost, pgdatabase]):
        return f"postgresql://{pguser}:{pgpassword}@{pghost}:{pgport}/{pgdatabase}"

    # Priorité 2 : DATABASE_URL directe
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url.replace("postgres://", "postgresql://")

    # Fallback : SQLite local
    return "sqlite:///./justlink.db"


class Settings(BaseSettings):
    APP_NAME: str = "JustiLink"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = "JustiLink_Secret_Pilote_2026_Quebec"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    DATABASE_URL: str = build_database_url()
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

