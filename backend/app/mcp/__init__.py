"""
Paperbase MCP (Model Context Protocol) Integration

This package exposes Paperbase functionality to AI assistants like Claude
through the Model Context Protocol (MCP).

Components:
    - server.py: MCP server with tools and resources
    - (future) config.py: MCP configuration and settings

Usage:
    # Run standalone
    python -m app.mcp.server

    # Or integrated with FastAPI (see main.py)
    from app.mcp.server import app as mcp_server
"""

from .server import app

__all__ = ["app"]
