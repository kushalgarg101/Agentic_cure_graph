"""MCP Protocol Server — serves Cure Graph tools over HTTP.

This is a lightweight JSON-RPC–style server that exposes the MCP
tool definitions from ``tools.py``. AI agents connect to this
server to call Cure Graph tools.
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from mcp_server.tools import MCP_TOOLS

logger = logging.getLogger(__name__)


def create_mcp_app() -> FastAPI:
    """Create the MCP FastAPI application."""

    app = FastAPI(
        title="Agentic Cure Graph — MCP Server",
        version="0.4.0",
        description="Model Context Protocol server exposing Cure Graph tools for AI agents.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {
            "name": "Agentic Cure Graph MCP Server",
            "version": "0.4.0",
            "protocol": "mcp",
            "tools": [
                {"name": t["name"], "description": t["description"]}
                for t in MCP_TOOLS
            ],
        }

    @app.get("/tools")
    def list_tools():
        """List available MCP tools with their schemas."""
        return {
            "tools": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                }
                for t in MCP_TOOLS
            ]
        }

    @app.post("/call")
    async def call_tool(request: Request):
        """Call an MCP tool by name with given arguments.

        Request body:
            { "tool": "tool_name", "arguments": { ... } }
        """
        body = await request.json()
        tool_name = body.get("tool")
        arguments = body.get("arguments", {})

        if not tool_name:
            raise HTTPException(status_code=400, detail="Missing 'tool' field")

        # Find the tool
        tool_def = next((t for t in MCP_TOOLS if t["name"] == tool_name), None)
        if tool_def is None:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{tool_name}' not found. Available: {[t['name'] for t in MCP_TOOLS]}",
            )

        handler = tool_def["handler"]

        try:
            logger.info("MCP call: %s(%s)", tool_name, json.dumps(arguments)[:200])
            result = handler(**arguments)
            return {"tool": tool_name, "status": "success", "result": result}
        except Exception as exc:
            logger.exception("MCP tool call failed: %s", tool_name)
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/health")
    def health():
        return {"status": "ok", "protocol": "mcp", "tools_count": len(MCP_TOOLS)}

    return app
