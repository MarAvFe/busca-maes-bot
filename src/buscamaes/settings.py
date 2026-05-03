import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN not set. Create a .env file with BOT_TOKEN=...")


def get_settings() -> Settings:
    return Settings()
