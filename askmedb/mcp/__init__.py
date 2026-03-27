"""AskMeDB MCP Server — expose database queries as MCP tools."""

from .server import create_server

__all__ = ["create_server"]
