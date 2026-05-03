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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
