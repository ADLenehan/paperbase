"""
MCP Server Entry Point

Run the Paperbase MCP server via stdio transport for Claude Desktop integration.

Usage:
    python -m mcp_server              # Start server (stdio mode)
    python -m mcp_server setup        # Configure Claude Desktop
    python -m mcp_server health       # Health check
    python -m mcp_server --help       # Show help
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Only import config for basic setup (defer server import)
from mcp_server.config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Log to stderr so stdout is clean for MCP protocol
)

logger = logging.getLogger(__name__)


def show_help():
    """Show help message"""
    print("""
Paperbase MCP Server

Usage:
  python -m mcp_server              Start MCP server (stdio mode)
  python -m mcp_server setup        Configure Claude Desktop
  python -m mcp_server health       Run health check
  python -m mcp_server --help       Show this help

Quick Start:
  1. Run: python -m mcp_server setup
  2. Restart Claude Desktop
  3. Start chatting!

Documentation:
  - MCP_SETUP_SIMPLE.md - Simple setup guide
  - docs/MCP_QUICK_START.md - Quick start
  - docs/MCP_SERVER_GUIDE.md - Full API reference
    """)


def run_setup():
    """Run setup wizard"""
    from mcp_server.setup import main as setup_main
    setup_main()


def run_health_check():
    """Run health check"""
    from mcp_server.health_check import main as health_main
    return health_main()


def run_server():
    """Run MCP server"""
    logger.info(f"Starting {config.SERVER_NAME} v{config.VERSION}")
    logger.info(f"Transport: stdio (Claude Desktop mode)")

    try:
        # Import server here (deferred to allow setup/health without full dependencies)
        from mcp_server.server import mcp

        # Run FastMCP server with stdio transport
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point for MCP server"""
    # Parse command
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command in ("--help", "-h", "help"):
            show_help()
            sys.exit(0)
        elif command == "setup":
            run_setup()
            sys.exit(0)
        elif command in ("health", "check"):
            sys.exit(run_health_check())
        elif command == "version":
            print(f"{config.SERVER_NAME} v{config.VERSION}")
            sys.exit(0)
        else:
            print(f"Unknown command: {command}")
            print("Run: python -m mcp_server --help")
            sys.exit(1)

    # No command = run server
    run_server()


if __name__ == "__main__":
    main()
