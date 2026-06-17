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
    # parallel discovery: number of (comuna, tipo) units scraped concurrently, each
    # with its own PortalClient. Pages WITHIN a comuna stay sequential (VIEWSTATE).
    discovery_concurrency: int = 8
    max_retries: int = 3
    # polite delay (seconds) between PDF downloads during queue draining/backfill,
    # to avoid hammering / rate-limiting the MINVU portal at ~156K scale.
    download_delay: float = 1.5

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

    # DB connect resilience (Fase 13): retry the connection on transient outages
    # (Zeabur Postgres restart / "system is in recovery mode") with expo backoff.
    db_connect_retries: int = 6
    db_connect_backoff: float = 2.0  # seconds; doubles each attempt (2,4,8,16,32,64)

    # admin endpoints: shared-secret token gate for /admin/* (empty = open, but a
    # value is strongly recommended in prod since the Zeabur URL is public).
    admin_token: str = ""


settings = Settings()
