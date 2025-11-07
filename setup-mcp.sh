#!/bin/bash
# Paperbase MCP Server - Easy Setup Script
#
# This script automatically sets up the Paperbase MCP server for Claude Desktop
#
# Usage:
#   ./setup-mcp.sh          # Run setup
#   ./setup-mcp.sh health   # Health check
#   ./setup-mcp.sh test     # Test server

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Change to backend directory
cd "$(dirname "$0")/backend"

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo -e "${RED}Error: Python not found${NC}"
    exit 1
fi

# Check if in virtual environment or suggest using one
if [[ -z "$VIRTUAL_ENV" ]] && [[ -d "venv" ]]; then
    echo -e "${YELLOW}Tip: You have a virtual environment. Activate it with:${NC}"
    echo -e "${YELLOW}  source venv/bin/activate${NC}"
    echo ""
fi

# Default action is setup
ACTION="${1:-setup}"

case "$ACTION" in
    setup)
        echo -e "${BLUE}Starting Paperbase MCP Setup...${NC}\n"
        $PYTHON -m mcp_server.setup
        ;;

    health|check)
        echo -e "${BLUE}Running Health Check...${NC}\n"
        $PYTHON -m mcp_server.health_check
        ;;

    test)
        echo -e "${BLUE}Testing MCP Server...${NC}\n"
        echo "Press Ctrl+C to stop"
        echo ""
        $PYTHON -m mcp_server
        ;;

    install|deps)
        echo -e "${BLUE}Installing MCP dependencies...${NC}\n"
        $PYTHON -m pip install fastmcp>=2.0.0 cachetools mcp>=1.0.0 aiosqlite>=0.19.0
        echo -e "\n${GREEN}Dependencies installed!${NC}"
        echo -e "Run: ${YELLOW}./setup-mcp.sh${NC} to configure Claude Desktop"
        ;;

    help|--help|-h)
        echo "Paperbase MCP Server Setup"
        echo ""
        echo "Usage:"
        echo "  ./setup-mcp.sh          Setup Claude Desktop integration"
        echo "  ./setup-mcp.sh health   Run health check"
        echo "  ./setup-mcp.sh test     Test server startup"
        echo "  ./setup-mcp.sh install  Install dependencies"
        echo "  ./setup-mcp.sh help     Show this help"
        echo ""
        ;;

    *)
        echo -e "${RED}Unknown command: $ACTION${NC}"
        echo "Run: ./setup-mcp.sh help"
        exit 1
        ;;
esac
