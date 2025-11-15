from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.core.error_handlers import register_error_handlers
from app.api import onboarding, documents, search, verification, analytics, templates, bulk_upload, rematch, extractions, folders, nl_query, audit, files, settings as settings_api, export, aggregations, mcp_search, auth, users, roles, sharing, query_suggestions, oauth, organizations
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable DEBUG logging for reducto_service to see chunk structure
logging.getLogger('app.services.reducto_service').setLevel(logging.DEBUG)

# Create FastAPI app
app = FastAPI(
    title="Paperbase API",
    description="Intelligent document processing with AI extraction and HITL verification",
    version="0.1.0",
    debug=settings.DEBUG
)

# Configure CORS - MUST be before routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Include routers
# Authentication & User Management
app.include_router(auth.router)  # Login, logout, API keys
app.include_router(oauth.router)  # OAuth (Google, Microsoft)
app.include_router(users.router)  # User management
app.include_router(roles.router)  # Role & permission management
app.include_router(sharing.router)  # Document sharing
app.include_router(organizations.router)  # Organization management

# Core functionality
app.include_router(settings_api.router)  # Settings management
app.include_router(templates.router)
app.include_router(bulk_upload.router)  # New bulk upload flow
app.include_router(rematch.router)  # Retroactive template matching
app.include_router(extractions.router, prefix="/api/extractions", tags=["extractions"])  # Multi-template extraction
app.include_router(folders.router, prefix="/api/folders", tags=["folders"])  # Virtual folder browsing
app.include_router(nl_query.router)  # Natural language query interface
app.include_router(audit.router)  # HITL audit interface
app.include_router(files.router)  # File serving for PDF preview
app.include_router(export.router)  # Export functionality (CSV, Excel, JSON)
app.include_router(aggregations.router)  # Comprehensive aggregations API
app.include_router(mcp_search.router)  # MCP server search interface
app.include_router(query_suggestions.router)  # Smart query suggestions
app.include_router(onboarding.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(verification.router)  # Legacy - to be removed
app.include_router(analytics.router)


# Create database tables, seed templates, and setup Elasticsearch
@app.on_event("startup")
async def startup_event():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Create Elasticsearch template signatures index
    from app.services.elastic_service import ElasticsearchService

    try:
        elastic_service = ElasticsearchService()
        await elastic_service.create_template_signatures_index()
        logger.info("Template signatures index created/verified")
    except Exception as e:
        logger.error(f"Error creating template signatures index: {e}")

    # Initialize settings with defaults
    from app.core.database import SessionLocal
    from app.services.settings_service import SettingsService

    try:
        db = SessionLocal()
        settings_service = SettingsService(db)
        settings_service.initialize_defaults()
        logger.info("Settings initialized with defaults")
        db.close()
    except Exception as e:
        logger.error(f"Error initializing settings: {e}")

    # Initialize permissions and roles
    from app.services.permission_service import PermissionService

    try:
        db = SessionLocal()
        permission_service = PermissionService(db)
        permission_service.initialize_default_permissions()
        logger.info("Permissions and roles initialized")
        db.close()
    except Exception as e:
        logger.error(f"Error initializing permissions: {e}")

    # Seed built-in templates
    from app.api.templates import seed_builtin_templates

    try:
        db = SessionLocal()
        templates = seed_builtin_templates(db)
        logger.info(f"Seeded {len(templates)} built-in templates")

        # Index template signatures for built-in templates
        elastic_service = ElasticsearchService()
        for template in templates:
            try:
                field_names = [f["name"] for f in template.fields]
                await elastic_service.index_template_signature(
                    template_id=template.id,
                    template_name=template.name,
                    field_names=field_names,
                    sample_text="",  # Built-in templates don't have sample text
                    category=template.category
                )
                logger.info(f"Indexed signature for template: {template.name}")
            except Exception as e:
                logger.error(f"Error indexing template {template.name}: {e}")

        db.close()
        await elastic_service.close()
    except Exception as e:
        logger.error(f"Error seeding templates: {e}")

    # MCP Server availability notice
    logger.info("=" * 50)
    logger.info("Paperbase API started successfully!")
    logger.info("=" * 50)
    logger.info("MCP Integration: Available")
    logger.info("To use with Claude Desktop, configure:")
    logger.info('  ~/.config/Claude/claude_desktop_config.json')
    logger.info('  Add: {"mcpServers": {"paperbase": {"command": "python", "args": ["-m", "app.mcp.server"]}}}')
    logger.info("=" * 50)


# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "paperbase-api"
    }


# MCP (Model Context Protocol) Endpoints

@app.get("/api/mcp/status")
async def mcp_status():
    """
    Get MCP server status.
    Used by frontend to show Claude connection indicator.
    """
    # Check if MCP server module is available
    try:
        from app.mcp import server as mcp_server
        tools = await mcp_server.app.list_tools()
        resources = await mcp_server.app.list_resources()

        return {
            "enabled": True,
            "status": "connected",  # Assume connected if server is running
            "tools_count": len(tools),
            "resources_count": len(resources),
            "message": "MCP server is running and ready for Claude"
        }
    except Exception as e:
        logger.debug(f"MCP not available: {e}")
        return {
            "enabled": False,
            "status": "disconnected",
            "message": "MCP server not configured. Install: pip install mcp"
        }


@app.post("/api/mcp/toggle")
async def toggle_mcp(request: dict):
    """
    Enable/disable MCP integration.
    For MVP, this just returns current status.
    In production, this would update configuration.
    """
    enabled = request.get("enabled", False)

    return {
        "enabled": enabled,
        "status": "connected" if enabled else "disconnected",
        "message": f"MCP {'enabled' if enabled else 'disabled'}"
    }


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Paperbase API",
        "docs": "/docs",
        "health": "/health"
    }
