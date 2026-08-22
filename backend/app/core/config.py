import logging

from pydantic_settings import BaseSettings

from app.core.constants import Defaults

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """ Application settings """

    # Base
    APP_NAME: str = Defaults.APP_NAME
    API_V1_STR: str = Defaults.API_V1_STR

    # App Metadata
    APP_VERSION: str = Defaults.APP_VERSION
    APP_DESCRIPTION: str = Defaults.APP_DESCRIPTION

    # CORS Settings
    CORS_ORIGINS: list[str] = Defaults.CORS_ORIGINS

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_ADMIN_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Google Client
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Gemini
    GEMINI_API_KEY: str = ""

    # Application Settings
    LOG_LEVEL: str = Defaults.LOG_LEVEL

    model_config = {"env_file": ".env", "case_sensitive": True}

def get_settings() -> Settings:
    return Settings()

settings = get_settings()

LOG_LEVEL = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)