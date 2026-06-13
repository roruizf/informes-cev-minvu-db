"""Settings loaded from environment (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # database
    database_url: str = "postgresql+psycopg://cev:cev@localhost:5432/cev"

    # MINVU portal (HTTPS — Phase-0: legacy http:// now 404s)
    minvu_base_url: str = "https://calificacionenergeticaweb.minvu.cl"

    # scraping concurrency
    download_concurrency: int = 8
    max_retries: int = 3

    # PDF cleanup
    pdf_dir: str = "/tmp/cev_pdfs"
    pdf_cleanup_days: int = 7

    # NoCodeBackend mirror (Phase-5)
    nocodebackend_api_url: str = "https://api.nocodebackend.com"
    nocodebackend_instance: str = ""
    nocodebackend_secret_key: str = ""
    nocodebackend_access_token: str = ""

    # scheduler
    daily_scrape_hour: int = 3


settings = Settings()
