"""
MCP Server Entry Point

Run the Paperbase MCP server via stdio transport for Claude Desktop integration.

Usage:
    python -m mcp_server
    or
    uvx paperbase-mcp-server
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import mcp
from mcp_server.config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Log to stderr so stdout is clean for MCP protocol
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for MCP server"""
    logger.info(f"Starting {config.SERVER_NAME} v{config.VERSION}")
    logger.info(f"Transport: stdio (Claude Desktop mode)")

    try:
        # Run FastMCP server with stdio transport
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
