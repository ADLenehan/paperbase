#!/usr/bin/env python3
"""
MCP Server Health Check

Quick diagnostic tool to verify MCP server setup.

Usage:
    python -m mcp_server.health_check
"""

import sys
from pathlib import Path

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_item(name: str, check_func) -> bool:
    """Run a check and print result"""
    try:
        result, message = check_func()
        if result:
            print(f"{GREEN}✓{RESET} {name}: {message}")
        else:
            print(f"{RED}✗{RESET} {name}: {message}")
        return result
    except Exception as e:
        print(f"{RED}✗{RESET} {name}: {e}")
        return False


def check_dependencies() -> tuple:
    """Check Python dependencies"""
    missing = []

    try:
        import fastmcp
        fastmcp_version = fastmcp.__version__
    except ImportError:
        missing.append("fastmcp")
        fastmcp_version = None

    try:
        import cachetools
    except ImportError:
        missing.append("cachetools")

    try:
        import mcp
    except ImportError:
        missing.append("mcp")

    if missing:
        return False, f"Missing: {', '.join(missing)}"

    return True, f"All installed (fastmcp {fastmcp_version})"


def check_database() -> tuple:
    """Check database connection"""
    try:
        from mcp_server.services.db_service import db_service
        from sqlalchemy import text
        import asyncio

        # Try to connect (using async)
        async def test_connection():
            session = await db_service.get_session()
            try:
                result = await session.execute(text("SELECT 1"))
                return True
            finally:
                await session.close()

        asyncio.run(test_connection())

        # Get database URL info
        db_url = str(db_service.engine.url)
        return True, f"Connected to {db_url}"
    except Exception as e:
        return False, str(e)


def check_elasticsearch() -> tuple:
    """Check Elasticsearch connection"""
    try:
        from mcp_server.services.es_service import es_mcp_service
        import asyncio

        # Try async health check
        async def test_es():
            return await es_mcp_service.health_check()

        if asyncio.run(test_es()):
            return True, "Connected successfully"
        else:
            return False, "Cannot ping Elasticsearch"
    except Exception as e:
        return False, str(e)


def check_server_load() -> tuple:
    """Check if server module loads"""
    try:
        from mcp_server.server import mcp
        from mcp_server.config import config

        # FastMCP 2.x doesn't expose _tools, just verify it loaded
        # Count tools by inspecting the registered handlers
        tool_count = 0
        if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, 'tools'):
            tool_count = len(mcp._tool_manager.tools)
        else:
            # Fallback: just verify mcp loaded successfully
            tool_count = "unknown"

        return True, f"{config.SERVER_NAME} v{config.VERSION} (loaded successfully)"
    except Exception as e:
        return False, str(e)


def check_templates() -> tuple:
    """Check if templates exist"""
    try:
        from mcp_server.services.db_service import db_service
        from app.models.schema import Schema
        from sqlalchemy import select, func
        import asyncio

        # Use async session to query templates
        async def count_templates():
            session = await db_service.get_session()
            try:
                stmt = select(func.count()).select_from(Schema)
                result = await session.execute(stmt)
                return result.scalar()
            finally:
                await session.close()

        count = asyncio.run(count_templates())

        if count > 0:
            return True, f"{count} templates found"
        else:
            return False, "No templates in database"
    except Exception as e:
        return False, str(e)


def check_claude_config() -> tuple:
    """Check if Claude Desktop is configured"""
    try:
        import json
        from pathlib import Path

        # Try to find config
        home = Path.home()
        config_path = home / "Library/Application Support/Claude/claude_desktop_config.json"

        if not config_path.exists():
            return False, "Config file not found"

        with open(config_path) as f:
            config = json.load(f)

        if "mcpServers" in config and "paperbase" in config["mcpServers"]:
            return True, "Paperbase MCP configured"
        else:
            return False, "Paperbase not in config"
    except Exception as e:
        return False, str(e)


def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  Paperbase MCP Server Health Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    checks = [
        ("Python Dependencies", check_dependencies),
        ("MCP Server Module", check_server_load),
        ("Database Connection", check_database),
        ("Elasticsearch Connection", check_elasticsearch),
        ("Templates Available", check_templates),
        ("Claude Desktop Config", check_claude_config),
    ]

    results = []
    for name, check_func in checks:
        results.append(check_item(name, check_func))

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n{BLUE}{'='*60}{RESET}")

    if passed == total:
        print(f"{GREEN}  All checks passed! ({passed}/{total}){RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        print("Your MCP server is ready to use!\n")
        print("Next steps:")
        print("  1. Restart Claude Desktop")
        print("  2. Try: \"List all document templates in Paperbase\"\n")
        return 0
    else:
        print(f"{YELLOW}  Passed: {passed}/{total}{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")

        if not results[0]:  # Dependencies
            print("Fix: pip install fastmcp>=2.0.0 cachetools mcp>=1.0.0\n")
        elif not results[5]:  # Claude config
            print("Fix: python -m mcp_server.setup\n")
        else:
            print("Some checks failed. Review errors above.\n")

        return 1


if __name__ == "__main__":
    sys.exit(main())
