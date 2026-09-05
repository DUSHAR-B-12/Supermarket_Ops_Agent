from app.config.settings import Settings

def test_default_settings():
    settings = Settings()
    assert settings.DATABASE_URL is not None
    assert "sqlite" in settings.DATABASE_URL
    assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR"]
