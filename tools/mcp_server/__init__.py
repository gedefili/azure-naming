"""Model Context Protocol server exposing azure-naming operations."""

from .server import NamingMCPServer, run_stdio_server

__all__ = ["NamingMCPServer", "run_stdio_server"]
