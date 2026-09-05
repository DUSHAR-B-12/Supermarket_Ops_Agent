from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = "placeholder_bot_token"
    LLM_API_KEY: str = "placeholder_llm_key"
    GEMINI_API_KEY: str = "placeholder_gemini_key"
    GEMINI_MODEL: str = "gemini-3.6-flash"
    LLM_MODEL: str = "gemini-3.6-flash"
    DATABASE_URL: str = "sqlite:///./data/supermarket.db"

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
