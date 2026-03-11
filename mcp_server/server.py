"""MCP Protocol Server for Agentic Cure Graph.

This server exposes Cure Graph tools using the official MCP SDK.
Can run over stdio (for local AI tools) or HTTP (for remote clients).
"""

from __future__ import annotations

import logging

import uvicorn

from mcp_server.tools import create_mcp_server

logger = logging.getLogger(__name__)


def create_mcp_app():
    """Create FastAPI-compatible app with MCP over SSE."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from starlette.routing import Route
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from mcp.server.sse import SseServerTransport

    mcp_server = create_mcp_server()
    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request):
        await sse_transport.handle(request, mcp_server)

    async def handle_messages(request):
        await sse_transport.handle(request, mcp_server)

    starlette_app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages/", endpoint=handle_messages, methods=["POST"]),
        ],
    )

    app = FastAPI(
        title="Agentic Cure Graph - MCP Server",
        version="1.0.0",
        description="Model Context Protocol server for Cure Graph tools",
    )

    @app.get("/")
    def root():
        return {
            "name": "Agentic Cure Graph MCP Server",
            "version": "1.0.0",
            "protocol": "mcp",
            "endpoints": {
                "sse": "/sse",
                "messages": "/messages/",
            },
            "description": "Connect MCP clients to /sse for tool access",
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "mcp": "available"}

    app.mount("/mcp", starlette_app)

    return app


def run_mcp_stdio():
    """Run MCP server over stdio (for local AI tool integration)."""
    from mcp_server.tools import run_mcp_server
    import asyncio

    asyncio.run(run_mcp_server())


def run_mcp_http(host: str = "127.0.0.1", port: int = 8001):
    """Run MCP server over HTTP with SSE."""
    app = create_mcp_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        run_mcp_http()
    else:
        run_mcp_stdio()
