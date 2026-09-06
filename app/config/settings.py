import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = "placeholder_bot_token"
    LLM_API_KEY: str = "placeholder_llm_key"
    GEMINI_API_KEY: str = "placeholder_gemini_key"
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_FALLBACK_MODELS: str = "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash"
    GROQ_API_KEY: str = "placeholder_groq_key"
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    LLM_MODEL: str = "gemini-3.8-flash"
    DATABASE_URL: str = "sqlite:///./data/supermarket.db"
    SHOP_NAME: str = "GreenBasket Supermart"

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def resolved_database_path(self) -> str:
        """Return the absolute filesystem path to the SQLite database file."""
        if not self.DATABASE_URL.startswith("sqlite:///"):
            return self.DATABASE_URL
        raw_path = self.DATABASE_URL.replace("sqlite:///", "")
        return os.path.abspath(raw_path)

    @property
    def resolved_database_url(self) -> str:
        """Return a DATABASE_URL with an absolute path for SQLAlchemy."""
        if not self.DATABASE_URL.startswith("sqlite:///"):
            return self.DATABASE_URL
        abs_path = self.resolved_database_path
        return f"sqlite:///{abs_path}"

    @property
    def data_dir(self) -> str:
        """Return the directory containing the database (used for invoices, artifacts)."""
        return os.path.dirname(self.resolved_database_path)


settings = Settings()
