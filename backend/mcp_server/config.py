"""
MCP Server Configuration

Manages configuration for the Paperbase MCP server including
database connections, caching, security, and transport settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class MCPConfig(BaseSettings):
    """MCP Server Configuration"""

    # Server Information
    SERVER_NAME: str = "paperbase-mcp"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = """Paperbase document extraction and search MCP server.

IMPORTANT: When displaying extracted document fields, ALWAYS show confidence scores AND audit links.

Confidence scoring:
- High (≥80%): Reliable, rarely needs verification
- Medium (60-80%): May need review
- Low (<60%): Requires human verification - INCLUDE AUDIT LINK

Format field values as:
- High/Medium confidence: "field_name: value (confidence: X%)"
- Low confidence: "field_name: value (confidence: X% - [Verify in Audit]({audit_link}))"

Example response format:
"Based on the document, here are the extracted fields:
- Invoice Number: INV-2024-001 (confidence: 95%)
- Total Amount: $1,250.00 (confidence: 88%)
- Vendor Name: Acme Corp (confidence: 58% - [Verify in Audit](http://localhost:3000/audit?field_id=123&document_id=45&highlight=true&source=mcp_query))"

Each field includes an 'audit_link' property if confidence is low. Display it as a clickable link!
Never display field values without their confidence scores unless explicitly asked."""

    # Frontend URL for web UI access links
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Transports
    ENABLE_STDIO: bool = True
    ENABLE_HTTP: bool = False  # Future enhancement
    HTTP_PORT: int = 8100
    HTTP_HOST: str = "0.0.0.0"

    # Database Configuration (from main app)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./paperbase.db")
    SQLITE_POOL_SIZE: int = 5
    SQLITE_TIMEOUT: int = 30

    # Elasticsearch Configuration
    ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    ES_TIMEOUT: int = 30
    ES_MAX_RETRIES: int = 3

    # Caching Configuration
    CACHE_ENABLED: bool = True
    CACHE_MAX_SIZE: int = 1000  # Max items in LRU cache
    CACHE_DEFAULT_TTL: int = 300  # 5 minutes
    CACHE_TEMPLATES_TTL: int = 300  # 5 minutes
    CACHE_STATS_TTL: int = 60  # 1 minute
    CACHE_DOCUMENTS_TTL: int = 30  # 30 seconds

    # Query Configuration
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    MAX_SEARCH_RESULTS: int = 100

    # Performance Settings
    ENABLE_QUERY_OPTIMIZATION: bool = True
    ENABLE_RESPONSE_COMPRESSION: bool = True
    MAX_CONCURRENT_QUERIES: int = 10

    # Rate Limiting (for HTTP mode)
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_PER_MIN: int = 100
    RATE_LIMIT_BURST: int = 20

    # Security (for HTTP mode)
    ENABLE_AUTH: bool = False
    API_KEY_ROTATION_DAYS: int = 90
    REQUIRE_HTTPS: bool = False

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_MCP_REQUESTS: bool = True
    LOG_MCP_RESPONSES: bool = False  # Can be verbose

    # Feature Flags
    ENABLE_ADVANCED_ES_QUERIES: bool = True
    ENABLE_ANALYTICS_TOOLS: bool = True
    ENABLE_AUDIT_TOOLS: bool = True

    class Config:
        env_prefix = "MCP_"
        case_sensitive = False


# Global config instance
config = MCPConfig()
