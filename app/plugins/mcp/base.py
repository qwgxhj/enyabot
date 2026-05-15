from __future__ import annotations

from typing import Protocol

from app.plugins.mcp.models import MCPToolDescriptor


class BaseMCPClient(Protocol):
    server_name: str

    async def connect(self) -> None: ...

    async def list_tools(self) -> list[MCPToolDescriptor]: ...

    async def call_tool(self, tool_name: str, arguments: dict) -> dict: ...

    async def close(self) -> None: ...
