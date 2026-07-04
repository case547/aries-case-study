import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.database_url = os.environ["DATABASE_URL"]
        self.gnews_api_key = os.environ["GNEWS_API_KEY"]
        self.openai_api_key = os.environ["OPENAI_API_KEY"]


settings = Settings()
