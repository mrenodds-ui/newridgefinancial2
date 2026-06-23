from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedUser, require_roles
from .hal import command_registry


router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


class MCPToolCall(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.get("/tools")
async def list_tools(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return {
        "tools": [
            {
                "name": "backend.refresh_and_verify",
                "description": "Refreshes system state and verifies data consistency across financial models.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "backend.ci_gates",
                "description": "Runs local integration test suites and gating checks.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "backend.smoke_tests",
                "description": "Executes rapid system smoke tests across the approved API surface.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "backend.rebuild_receipt",
                "description": "Runs the rebuild receipt workflow and emits a structured receipt payload.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
    }


@router.post("/tools/call")
async def call_tool(payload: MCPToolCall, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    if payload.arguments:
        raise HTTPException(status_code=400, detail="These MCP tools do not accept arguments yet.")
    try:
        result = command_registry.execute(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "content": [
            {
                "type": "text",
                "text": f"Execution status: {result['status']}. Output: {result.get('output', result.get('error'))}",
            }
        ],
        "isError": result["status"] == "failed",
    }