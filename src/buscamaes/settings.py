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

        # Plate search allowlist: comma-separated Telegram user IDs.
        # Empty = nobody allowed (fail-closed).
        allowed_raw = os.getenv("PLATE_ALLOWED_USER_IDS", "")
        self.plate_allowed_user_ids: frozenset[int] = frozenset(
            int(x.strip()) for x in allowed_raw.split(",") if x.strip().isdigit()
        )

        # Admin user IDs for /stats access: comma-separated Telegram user IDs.
        # Empty = nobody allowed (fail-closed).
        admin_raw = os.getenv("ADMIN_USER_IDS", "")
        self.admin_user_ids: frozenset[int] = frozenset(
            int(x.strip()) for x in admin_raw.split(",") if x.strip().isdigit()
        )

        # RNP (plate search) credentials
        self.rnp_email = os.getenv("RNP_EMAIL", "")
        self.rnp_password = os.getenv("RNP_PASSWORD", "")
        self.rnp_base_url: str = os.getenv("RNP_BASE_URL", "https://www.rnpdigital.com")
        self.rnp_timeout: int = int(os.getenv("RNP_TIMEOUT", "30"))

        # RNP credential pool: comma-separated email:password pairs.
        # If set, takes precedence over RNP_EMAIL/RNP_PASSWORD.
        # e.g. RNP_ACCOUNTS=user1@example.com:pass1,user2@example.com:pass2
        accounts_raw = os.getenv("RNP_ACCOUNTS", "")
        if accounts_raw.strip():
            pairs: list[tuple[str, str]] = []
            for pair in accounts_raw.split(","):
                pair = pair.strip()
                if ":" in pair:
                    email, password = pair.split(":", 1)
                    pairs.append((email.strip(), password.strip()))
            self.rnp_accounts: list[tuple[str, str]] = pairs
        else:
            self.rnp_accounts = [(self.rnp_email, self.rnp_password)] if self.rnp_email else []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
