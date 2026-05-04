import os
from functools import lru_cache

from dotenv import load_dotenv


class Settings:
    def __init__(self) -> None:
        load_dotenv()
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN not set. Create a .env file with BOT_TOKEN=...")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        # Rate limit: N requests per WINDOW seconds, per user.
        self.rate_limit_max: int = int(os.getenv("RATE_LIMIT_MAX", "10"))
        self.rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

        # Abuse detection: auto-deny if user exceeds threshold requests per day (UTC).
        self.daily_abuse_threshold: int = int(os.getenv("DAILY_ABUSE_THRESHOLD", "20"))

        # Audit DB path. /data is the docker volume mount.
        self.audit_db_path: str = os.getenv("AUDIT_DB_PATH", "/data/audit.db")
        self.audit_retention_days: int = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))

        # RNP (plate search) credentials
        self.rnp_email = os.getenv("RNP_EMAIL", "")
        self.rnp_password = os.getenv("RNP_PASSWORD", "")
        self.rnp_base_url: str = os.getenv("RNP_BASE_URL", "https://www.rnpdigital.com")
        self.rnp_timeout: int = int(os.getenv("RNP_TIMEOUT", "30"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
