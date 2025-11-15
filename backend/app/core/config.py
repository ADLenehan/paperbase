import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Keys
    REDUCTO_API_KEY: str
    ANTHROPIC_API_KEY: str

    # Database (PostgreSQL by default, SQLite for legacy/testing)
    DATABASE_URL: str = "postgresql://paperbase:paperbase@localhost:5432/paperbase"

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"  # For MCP web UI links

    # Authentication & Security
    SECRET_KEY: str = secrets.token_urlsafe(32)  # Generated if not provided
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24  # JWT tokens expire after 24 hours

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
