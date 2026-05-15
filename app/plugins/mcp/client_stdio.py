from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from loguru import logger

from app.plugins.mcp.errors import MCPClientUnavailableError
from app.plugins.mcp.models import MCPServerConfig, MCPToolDescriptor

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover - 依赖缺失时走运行期提示
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


class StdioMCPClient:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.server_name = config.name
        self._stack = AsyncExitStack()
        self._session = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        if ClientSession is None or StdioServerParameters is None or stdio_client is None:
            raise MCPClientUnavailableError(
                "未安装 Python MCP SDK，请先执行 `pip install mcp` 或安装 requirements.txt 中新增依赖。"
            )

        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env or None,
        )
        read_stream, write_stream = await self._stack.enter_async_context(stdio_client(server_params))
        session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        self._session = session
        self._connected = True
        logger.info("MCP stdio server connected: {}", self.server_name)

    async def list_tools(self) -> list[MCPToolDescriptor]:
        await self.connect()
        result = await self._session.list_tools()
        raw_tools = getattr(result, "tools", []) or []
        tools: list[MCPToolDescriptor] = []
        for raw_tool in raw_tools:
            name = getattr(raw_tool, "name", "") or ""
            description = getattr(raw_tool, "description", "") or ""
            input_schema = getattr(raw_tool, "inputSchema", None) or getattr(raw_tool, "input_schema", None) or {
                "type": "object",
                "properties": {},
            }
            tools.append(MCPToolDescriptor(name=name, description=description, input_schema=input_schema, raw=raw_tool))
        return tools

    async def call_tool(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        await self.connect()
        result = await self._session.call_tool(tool_name, arguments)
        content = getattr(result, "content", None)
        is_error = bool(getattr(result, "isError", False) or getattr(result, "is_error", False))
        return {
            "success": not is_error,
            "tool": tool_name,
            "content": self._serialize_content(content),
            "raw": self._serialize_result(result),
        }

    async def close(self) -> None:
        if not self._connected:
            return
        await self._stack.aclose()
        self._connected = False
        self._session = None
        logger.info("MCP stdio server closed: {}", self.server_name)

    def _serialize_content(self, content: Any) -> list[dict[str, Any]]:
        if content is None:
            return []
        items = content if isinstance(content, list) else [content]
        serialized: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, (str, int, float, bool)) or item is None:
                serialized.append({"type": "text", "text": str(item)})
                continue
            entry = {
                "type": getattr(item, "type", item.__class__.__name__),
            }
            for attr in ("text", "data", "mimeType", "mime_type", "url"):
                value = getattr(item, attr, None)
                if value is not None:
                    entry[attr] = value
            if len(entry) == 1:
                entry["value"] = self._safe_dump(item)
            serialized.append(entry)
        return serialized

    def _serialize_result(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "model_dump"):
            try:
                return result.model_dump()
            except Exception:
                pass
        return {"repr": self._safe_dump(result)}

    def _safe_dump(self, value: Any) -> str:
        try:
            if hasattr(value, "model_dump"):
                return json.dumps(value.model_dump(), ensure_ascii=False)
            if hasattr(value, "dict"):
                return json.dumps(value.dict(), ensure_ascii=False)
            if isinstance(value, (dict, list, tuple)):
                return json.dumps(value, ensure_ascii=False)
        except Exception:
            pass
        return repr(value)
