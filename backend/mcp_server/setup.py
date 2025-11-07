#!/usr/bin/env python3
"""
Automated MCP Server Setup for Claude Desktop

This script automatically configures Claude Desktop to use the Paperbase MCP server.

Usage:
    python -m mcp_server.setup
    or
    ./backend/mcp_server/setup.py
"""

import json
import os
import sys
import shutil
from pathlib import Path
from typing import Optional

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_success(msg: str):
    print(f"{GREEN}✓{RESET} {msg}")


def print_warning(msg: str):
    print(f"{YELLOW}⚠{RESET} {msg}")


def print_error(msg: str):
    print(f"{RED}✗{RESET} {msg}")


def print_info(msg: str):
    print(f"{BLUE}ℹ{RESET} {msg}")


def check_dependencies() -> bool:
    """Check if required dependencies are installed"""
    print_info("Checking dependencies...")

    missing = []

    try:
        import fastmcp
        print_success(f"fastmcp found (version {fastmcp.__version__})")
    except ImportError:
        missing.append("fastmcp>=2.0.0")

    try:
        import cachetools
        print_success("cachetools found")
    except ImportError:
        missing.append("cachetools")

    try:
        import mcp
        print_success("mcp found")
    except ImportError:
        missing.append("mcp>=1.0.0")

    if missing:
        print_error("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print_info("\nInstall with: pip install " + " ".join(missing))
        return False

    return True


def get_claude_config_path() -> Optional[Path]:
    """Get the Claude Desktop config file path"""
    home = Path.home()

    # macOS
    mac_path = home / "Library/Application Support/Claude/claude_desktop_config.json"
    if mac_path.parent.exists():
        return mac_path

    # Linux
    linux_path = home / ".config/Claude/claude_desktop_config.json"
    if linux_path.parent.exists():
        return linux_path

    # Windows
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            win_path = Path(appdata) / "Claude/claude_desktop_config.json"
            if win_path.parent.exists():
                return win_path

    return None


def get_project_paths() -> dict:
    """Auto-detect project paths"""
    # Get the backend directory (where this script is running from)
    backend_dir = Path(__file__).parent.parent.resolve()
    project_dir = backend_dir.parent

    db_path = backend_dir / "paperbase.db"

    return {
        "backend_dir": str(backend_dir),
        "project_dir": str(project_dir),
        "db_path": str(db_path),
        "db_url": f"sqlite:///{db_path}"
    }


def get_python_command() -> str:
    """Detect the correct Python command"""
    import shutil

    # Use the same Python that's running this script (most reliable)
    # This ensures we use the Python that has all the dependencies installed
    current_python = sys.executable
    if current_python and os.path.exists(current_python):
        return current_python

    # Fallback: Try python3 first (preferred on modern systems)
    if shutil.which("python3"):
        return "python3"
    # Fall back to python
    elif shutil.which("python"):
        return "python"
    else:
        return "python3"  # Default, will fail but shows clear error


def create_mcp_config(paths: dict) -> dict:
    """Create the MCP server configuration"""
    python_cmd = get_python_command()

    return {
        "command": python_cmd,
        "args": ["-m", "mcp_server"],
        "cwd": paths["backend_dir"],
        "env": {
            "DATABASE_URL": paths["db_url"],
            "ELASTICSEARCH_URL": os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
            "MCP_LOG_LEVEL": "INFO",
            "MCP_CACHE_ENABLED": "true",
            "FRONTEND_URL": os.getenv("FRONTEND_URL", "http://localhost:3000")
        }
    }


def backup_config(config_path: Path) -> Optional[Path]:
    """Backup existing config file"""
    if not config_path.exists():
        return None

    backup_path = config_path.with_suffix(".json.backup")
    shutil.copy2(config_path, backup_path)
    return backup_path


def update_claude_config(config_path: Path, mcp_config: dict) -> bool:
    """Update Claude Desktop config file"""
    try:
        # Read existing config or create new
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        # Ensure mcpServers exists
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        # Add/update paperbase server
        config["mcpServers"]["paperbase"] = mcp_config

        # Write back
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return True

    except Exception as e:
        print_error(f"Failed to update config: {e}")
        return False


def verify_setup(paths: dict) -> list:
    """Verify setup is correct"""
    issues = []

    # Check database exists
    db_path = Path(paths["db_path"])
    if not db_path.exists():
        issues.append(f"Database not found at {db_path}")

    # Check Elasticsearch
    try:
        import requests
        es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        response = requests.get(f"{es_url}/_cluster/health", timeout=2)
        if response.status_code != 200:
            issues.append(f"Elasticsearch not responding at {es_url}")
    except ImportError:
        pass  # requests not required
    except Exception as e:
        issues.append(f"Cannot connect to Elasticsearch: {e}")

    return issues


def test_mcp_server() -> bool:
    """Test if MCP server can start"""
    print_info("Testing MCP server startup...")

    try:
        # Try to import the server
        from mcp_server.server import mcp
        from mcp_server.config import config
        print_success(f"MCP server loaded: {config.SERVER_NAME} v{config.VERSION}")
        return True
    except ModuleNotFoundError as e:
        missing_module = str(e).split("'")[1] if "'" in str(e) else "unknown"
        print_error(f"Missing dependency: {missing_module}")
        print_info(f"Install with: pip install {missing_module}")
        return False
    except Exception as e:
        print_error(f"Failed to load MCP server: {e}")
        return False


def main():
    """Main setup function"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  Paperbase MCP Server Setup for Claude Desktop{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    # Step 1: Check dependencies
    if not check_dependencies():
        print_error("\nSetup failed: Missing dependencies")
        sys.exit(1)

    print()

    # Step 2: Get paths
    print_info("Detecting project paths...")
    paths = get_project_paths()
    print_success(f"Backend: {paths['backend_dir']}")
    print_success(f"Database: {paths['db_path']}")

    print()

    # Step 3: Test MCP server
    if not test_mcp_server():
        print_error("\nSetup failed: Cannot load MCP server")
        print_info("\nTry installing missing dependencies:")
        print(f"  {YELLOW}cd backend && pip install -r requirements.txt{RESET}")
        print(f"  or run: {YELLOW}./setup-mcp.sh install{RESET}")
        sys.exit(1)

    print()

    # Step 4: Find Claude config
    print_info("Locating Claude Desktop config...")
    config_path = get_claude_config_path()

    if not config_path:
        print_error("Claude Desktop config directory not found")
        print_info("Please install Claude Desktop first")
        sys.exit(1)

    print_success(f"Config: {config_path}")

    print()

    # Step 5: Verify setup
    print_info("Verifying environment...")
    issues = verify_setup(paths)

    if issues:
        print_warning("Found potential issues:")
        for issue in issues:
            print(f"  - {issue}")

        response = input(f"\n{YELLOW}Continue anyway?{RESET} (y/N): ")
        if response.lower() != 'y':
            print_info("Setup cancelled")
            sys.exit(0)
    else:
        print_success("Environment looks good!")

    print()

    # Step 6: Backup existing config
    if config_path.exists():
        print_info("Backing up existing config...")
        backup_path = backup_config(config_path)
        if backup_path:
            print_success(f"Backup saved: {backup_path}")

    # Step 7: Update config
    print_info("Updating Claude Desktop config...")
    mcp_config = create_mcp_config(paths)
    print_success(f"Using Python command: {mcp_config['command']}")

    if update_claude_config(config_path, mcp_config):
        print_success("Config updated successfully!")
    else:
        print_error("Failed to update config")
        sys.exit(1)

    # Success!
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  Setup Complete!{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")

    print("Next steps:\n")
    print(f"  1. {BLUE}Restart Claude Desktop{RESET} (completely quit and relaunch)")
    print(f"  2. Start a new conversation")
    print(f"  3. Try: {YELLOW}\"List all document templates in Paperbase\"{RESET}\n")

    print("Configuration added:")
    print(json.dumps({"paperbase": mcp_config}, indent=2))
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_info("\nSetup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
