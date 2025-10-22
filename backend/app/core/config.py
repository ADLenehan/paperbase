from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Keys
    REDUCTO_API_KEY: str
    ANTHROPIC_API_KEY: str

    # Database
    DATABASE_URL: str = "sqlite:///./paperbase.db"

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = "./uploads"

    # Processing
    REDUCTO_TIMEOUT: int = 300

    # Note: Confidence thresholds moved to database settings (app/models/settings.py)
    # - review_threshold: Fields below this need human review (default: 0.6)
    # - auto_match_threshold: Min confidence for auto-matching templates (default: 0.70)
    # - enable_claude_fallback: Use Claude when ES confidence is low (default: True)

    # Development
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore old environment variables that are no longer defined


settings = Settings()
